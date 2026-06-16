import sentry_sdk
from uuid import uuid4
import sentry_sdk.logger as sentry_logger
from datetime import datetime, timezone, timedelta


from app.api.models.otp import Otp
from app.api.models.user import User
from app.core.config import get_settings
from app.api.repo.otp_repo import OtpRepository
from app.api.repo.user_repo import UserRepository
from app.api.repo.redis_repo import RedisRepository
from app.api.services.user_service import UserService
from app.task.celery_task import send_verification_email
from app.api.repo.unit_of_work import UnitOfWorkRepository
from app.api.schemas.user import UserInDB, EmailUserResponse, GoogleUserResponse
from app.core.security import (
    hash_password,
    prepare_tokens,
    verify_password,
    decode_token,
)
from app.api.schemas.auth import (
    EmailLogin,
    TokenData,
    EmailVerify,
    ResendOtp,
    PasswordUpdate,
    PasswordReset,
    ReactivateUser
)
from app.core.exceptions import (
    UserExistsError,
    InvalidOtpError,
    ServerError,
    CredentialError,
    AuthenticationError,
    PasswordMissingError,
)


class AuthService:
    def __init__(self, otp_repo: OtpRepository, redis_repo: RedisRepository):
        self._uow = None
        self._user_repo = None
        self._otp_repo = otp_repo
        self._redis_repo = redis_repo

    async def _get_tokens(self, email: str, user_type: str):
        token_data: TokenData = TokenData(email=email, user_type=user_type)
        access_token, refresh_token_payload = await prepare_tokens(token_data)

        refresh_token_id: str = refresh_token_payload.get("refresh_token_id")
        key: str = f"tokens:{refresh_token_id}"

        try:
            await self._redis_repo.add_refresh_token(key, refresh_token_payload)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            sentry_logger.error("Error occurred while saving refresh token to redis")
            raise ServerError() from e

        return access_token, refresh_token_payload.get("refresh_token")

    async def _revoke_refresh_token(self, refresh_token: str) -> tuple:
        refresh_token: dict = await decode_token(
            refresh_token, get_settings().REFRESH_TOKEN_SECRET_KEY
        )

        if not refresh_token:
            sentry_logger.error("Inavlid refresh token received during refresh")
            raise AuthenticationError()

        refresh_token_id: str = refresh_token["jti"]
        key: str = f"tokens:{refresh_token_id}"

        refresh_token_db: dict = await self._redis_repo.get_refresh_token(key)

        if not refresh_token_db:
            sentry_logger.error("Inavlid refresh token received during refresh")
            raise AuthenticationError()

        user_email: str = refresh_token_db["email"]
        user_type: str = refresh_token_db["user_type"]

        try:
            await self._redis_repo.delete_refresh_token(key)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            sentry_logger.error("Error occurred while deleting refresh token from redis")
            raise ServerError() from e

        return user_email, user_type

    async def sign_up_with_email(
        self, email_login: EmailLogin, user_service: UserService
    ):
        user_email: str = email_login.email
        hashed_password: str = await hash_password(email_login.password)

        existing_user: User | None = await user_service._get_user_by_email(
            email=user_email
        )

        if existing_user:
            if not existing_user.is_verified:
                existing_user.hashed_password = hashed_password

                await user_service.update_user(existing_user)

                send_verification_email.delay(
                    str(uuid4()),
                    existing_user.email,
                    str(existing_user.id),
                    "email_signup",
                )
            else:
                sentry_logger.error("User exists with email {email}", email=user_email)
                raise UserExistsError(user_email=user_email)
        else:
            user = UserInDB(
                email=user_email, hashed_password=hashed_password, type="email"
            )
            await user_service.create_user(user)

            user: User | None = await user_service._get_user_by_email(email=user_email)

            send_verification_email.delay(
                str(uuid4()), user_email, str(user.id), "email_signup"
            )

        sentry_logger.info(
            "Email and password sign up completed for user {email}",
            email=user_email,
        )

    async def sign_up_with_google(
        self, payload: dict, user_service: UserService
    ) -> tuple[str]:
        user_info: dict = payload.get("userinfo")

        google_id: str = user_info.get("sub")
        user_email: str = user_info.get("email")

        existing_user: User | None = await user_service._get_user_by_email(
            google_email=user_email,
            is_verified=True,
        )

        if existing_user:
            if existing_user.is_deactivated:
                sentry_logger.error(
                    "Invalid credentials received from user {email}", email=user_email
                )
                raise CredentialError()

            existing_user.is_active = True
            await user_service.update_user(existing_user)
        else:
            user = UserInDB(
                google_id=google_id,
                google_email=user_email,
                is_verified=True,
                is_active=True,
                type="google",
            )
            await user_service.create_user(user)

        access_token, refresh_token = await self._get_tokens(user_email, "google")

        sentry_logger.info(
            "Google sign in completed for user {email}",
            email=user_email,
        )

        return access_token, refresh_token

    async def verify_account(
        self,
        refresh_token: str | None,
        uow: UnitOfWorkRepository,
        email_verify: EmailVerify,
    ):
        # close active sessions
        await self._otp_repo.aclose()

        self._uow = uow
        self._user_repo = UserRepository(self._uow._session)
        self._otp_repo._async_session = self._uow._session

        user_email: str = email_verify.email

        existing_user: User | None = await self._user_repo.get_record(email=user_email)

        if not existing_user:
            sentry_logger.error("User not found with email {email}", email=user_email)
            raise InvalidOtpError()

        otp: Otp = await self._otp_repo.get_record(
            otp=email_verify.otp_code, user_id=existing_user.id, status="valid", expires_at=True
        )

        if not otp:
            sentry_logger.error(
                "Invalid otp received from user {email}", email=user_email
            )
            raise InvalidOtpError()

        try:
            if otp.purpose == "email_signup":
                existing_user.is_verified = True
            else:
                # reset password verfication
                if not email_verify.password:
                    sentry_logger.error(
                        (
                            "Password field not set for password reset account verification"
                            "for user {email}"
                        ),
                        email=user_email,
                    )
                    raise PasswordMissingError()

                existing_user.hashed_password = await hash_password(
                    email_verify.password
                )
                existing_user.is_active = False

                if refresh_token:
                    # revoke existing refresh token to prevent usage in refresh
                    _ = await self._revoke_refresh_token(refresh_token)

            otp.status = "used"
            self._otp_repo.add(model=otp)
            self._user_repo.add(model=existing_user)

            await self._uow.commit()

            sentry_logger.info(
                "User {email} account verification completed",
                email=user_email,
            )
        except Exception as e:
            await self._uow.rollback()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while trying to verify user {email} account",
                email=user_email,
            )
            raise ServerError() from e

    async def resend_otp(self, otp_resend: ResendOtp, user_service: UserService):
        user_email: str = otp_resend.email

        existing_user: User | None = await user_service._get_user_by_email(
            email=user_email, is_verified=False
        )

        if not existing_user:
            sentry_logger.error("User with email {email} not found", email=user_email)
            raise CredentialError()

        try:
            # invalidate all existing codes
            await self._otp_repo.update_records(
                {"status": "used"}, user_id=existing_user.id, status="valid"
            )

            send_verification_email.delay(
                str(uuid4()), user_email, str(existing_user.id), otp_resend.purpose
            )

            sentry_logger.info(
                "OTP code resent to user {email}",
                email=user_email,
            )
        except Exception as e:
            await self._otp_repo.rollback()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while resending otp to user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def login(self, email_login: EmailLogin, user_service: UserService):
        user_email: str = email_login.email

        existing_user: User | None = await user_service._get_user_by_email(
            email=user_email, is_verified=True, is_deactivated=False
        )

        if not existing_user:
            sentry_logger.error(
                "Invalid credentials received from user {email}", email=user_email
            )
            raise CredentialError()

        if not await verify_password(
            email_login.password, existing_user.hashed_password
        ):
            sentry_logger.error(
                "Invalid credentials received from user {email}", email=user_email
            )
            raise CredentialError()

        existing_user.is_active = True
        await user_service.update_user(existing_user)

        access_token, refresh_token = await self._get_tokens(user_email, "email")

        sentry_logger.info(
            "Login completed for user {email}",
            email=user_email,
        )

        return access_token, refresh_token

    async def create_auth_tokens(self, refresh_token: str):
        user_email, user_type = await self._revoke_refresh_token(refresh_token)
        access_token, refresh_token = await self._get_tokens(user_email, user_type)

        sentry_logger.info(
            "Access and refresh tokens created for user {email}",
            email=user_email,
        )

        return access_token, refresh_token

    async def get_current_user(
        self, curr_user: User
    ) -> EmailUserResponse | GoogleUserResponse:
        if curr_user.type == "email":
            user_email: str = curr_user.email
            user = EmailUserResponse.model_validate(curr_user)
        else:
            user_email: str = curr_user.google_email
            user = GoogleUserResponse.model_validate(curr_user)

        sentry_logger.info(
            "User {email} account retrieved",
            email=user_email,
        )
        return user

    async def update_password(
        self,
        curr_user: User,
        password_update: PasswordUpdate,
        user_service: UserService,
    ) -> EmailUserResponse:
        if not curr_user.hashed_password:
            sentry_logger.error(
                "Invalid user type for user {email}", email=curr_user.email
            )
            raise AuthenticationError()

        if not await verify_password(
            password_update.curr_password, curr_user.hashed_password
        ):
            sentry_logger.error(
                "Invalid credentials received from user {email}", email=curr_user.email
            )
            raise CredentialError()

        curr_user.hashed_password = await hash_password(password_update.new_password)
        await user_service.update_user(curr_user)

        sentry_logger.info(
            "User {email} password updated",
            email=curr_user.email,
        )

        return EmailUserResponse.model_validate(curr_user)

    async def reset_password(
        self, password_reset: PasswordReset, user_service: UserService
    ):        
        existing_user: User = await user_service.get_user_by_email(
            email=password_reset.email, is_verified=True, is_deactivated=False
        )

        send_verification_email.delay(
            str(uuid4()), existing_user.email, str(existing_user.id), "password_reset"
        )

        sentry_logger.info(
            "Verification code sent to {email} for password reset",
            email=password_reset.email,
        )

    async def logout(self, curr_user: User, user_service: UserService, refresh_token: str):
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        _ = await self._revoke_refresh_token(refresh_token)

        curr_user.is_active = False
        await user_service.update_user(curr_user)

        sentry_logger.info(
            "User {email} account logout completed",
            email=user_email,
        )

    async def deactivate_account(self, curr_user: User, user_service: UserService, refresh_token: str):
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        delete_at = datetime.now(timezone.utc) + timedelta(days=14)

        curr_user.is_active = False
        curr_user.is_deactivated = True
        curr_user.delete_at = delete_at
        curr_user.five_days_before = delete_at - timedelta(days=5)
        curr_user.seven_days_before = delete_at - timedelta(days=7)
        await user_service.update_user(curr_user)

        _ = await self._revoke_refresh_token(refresh_token)

        sentry_logger.info(
            "User {email} account deactivated",
            email=user_email,
        )

    async def reactivate_account(self, reactivate_user: ReactivateUser, user_service: UserService):
        user_email: str = reactivate_user.email

        if reactivate_user.user_type.lower() == "google":
            existing_user: User = await user_service.get_user_by_email(
                google_email=user_email, is_verified=True, is_active=False, is_deactivated=True
            )
        else:
            existing_user: User = await user_service.get_user_by_email(
                email=user_email, is_verified=True, is_active=False, is_deactivated=True
            )

        existing_user.delete_at = None
        existing_user.is_deactivated = False
        existing_user.five_days_before = None
        existing_user.seven_days_before = None
        await user_service.update_user(existing_user)

        sentry_logger.info(
            "User {email} account reactivated",
            email=user_email,
        )

    async def delete_account(self, curr_user: User, user_service: UserService, refresh_token: str):
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        await user_service.delete_user(curr_user)
        _ = await self._revoke_refresh_token(refresh_token)

        sentry_logger.info(
            "User {email} account deleted",
            email=user_email,
        )
