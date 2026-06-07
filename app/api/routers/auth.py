from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Request, Response


from app.limiter import limiter
from app.core.security import oauth
from app.core.config import get_settings
from app.api.schemas.response import SuccessResponse
from app.api.schemas.user import GoogleUserResponse, EmailUserResponse
from app.dependencies import (
    AuthServiceDep,
    UserServiceDep,
    CurrentActiveUser,
    UnitOfWorkRepo,
)
from app.api.schemas.auth import (
    SignUpResponse,
    EmailLogin,
    EmailVerify,
    Token,
    ResendOtp,
    OtpResendResponseV1,
    PasswordUpdate,
    PasswordReset,
    LogoutResponse,
    DeactivateResponse,
    ReactivateUser
)


router = APIRouter()


@router.post(
    "/auth/signup",
    status_code=201,
    response_model=SuccessResponse[SignUpResponse],
    description=(
        "Sign up with email and password."
        "A verification code is sent to the user's email on completion"
    ),
)
@limiter.limit("3/5minute")
async def sign_up_with_email(
    request: Request,
    email_login: EmailLogin,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    await auth_service.sign_up_with_email(email_login, user_service)
    return SuccessResponse(
        message=(
            "Sign up completed successfully."
            "Check your email for verification code and instrcutions"
        )
    )


@router.get(
    "/auth/google",
    status_code=302,
    response_class=RedirectResponse,
    description="Sign in with Google account",
)
@limiter.limit("3/5minute")
async def sign_in_with_google(request: Request):
    redirect_uri = request.url_for("google_callback")
    await oauth.google.authorize_redirect(request, redirect_uri)


@router.get(
    "/auth/google/callback",
    status_code=200,
    response_model=Token,
    description="Google redirect uri",
)
@limiter.limit("3/5minute")
async def google_callback(
    request: Request,
    response: Response,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    payload: dict = await oauth.google.authorize_access_token(request)
    access_token, refresh_token = await auth_service.sign_up_with_google(
        payload, user_service
    )

    expire_time: int = get_settings().REFRESH_TOKEN_EXPIRE_TIME * 24 * 3600

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=expire_time,
        secure=get_settings().ENVIRONMENT == "production",
        samesite="lax",
    )
    return Token(access_token=access_token)


@router.patch(
    "/auth/verify",
    status_code=200,
    response_model=SuccessResponse[EmailUserResponse],
    description="Verify account by submitting the received otp code",
)
@limiter.limit("3/5minute")
async def verify_account(
    request: Request,
    uow: UnitOfWorkRepo,
    email_verify: EmailVerify,
    auth_service: AuthServiceDep,
):
    await auth_service.verify_account(uow, email_verify)
    return SuccessResponse(message="User email verified successfully")


@router.post(
    "/auth/verify/resend",
    status_code=201,
    description="Resend verification code",
    response_model=SuccessResponse[OtpResendResponseV1],
)
@limiter.limit("3/5minute")
async def resend_otp(
    request: Request,
    otp_resend: ResendOtp,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    await auth_service.resend_otp(otp_resend, user_service)
    return SuccessResponse(
        message="OTP sent successfully. Check your email for instructions"
    )


@router.post(
    "/auth/login",
    status_code=201,
    description="Login with email and password",
    response_model=SuccessResponse[Token],
)
@limiter.limit("3/5minute")
async def login(
    request: Request,
    response: Response,
    email_login: EmailLogin,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    access_token, refresh_token = await auth_service.login(email_login, user_service)

    expire_time: int = get_settings().REFRESH_TOKEN_EXPIRE_TIME * 24 * 3600

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=expire_time,
        secure=get_settings().ENVIRONMENT == "production",
        samesite="lax",
    )
    return SuccessResponse(
        message="Login completed successfully", data=Token(access_token=access_token)
    )


@router.post(
    "/auth/refresh",
    status_code=201,
    response_model=SuccessResponse[Token],
    description="Create new access token for user with a valid refresh token",
)
@limiter.limit("3/5minute")
async def create_new_token(
    request: Request,
    response: Response,
    auth_service: AuthServiceDep,
):
    refresh_token: str = request.cookies.get("refresh_token")
    access_token, refresh_token = await auth_service.create_auth_tokens(refresh_token)

    expire_time: int = get_settings().REFRESH_TOKEN_EXPIRE_TIME * 24 * 3600

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=expire_time,
        secure=get_settings().ENVIRONMENT == "production",
        samesite="lax",
    )
    return SuccessResponse(
        message="Token created successfully", data=Token(access_token=access_token)
    )


@router.get(
    "/auth/me",
    status_code=200,
    description="Get current active user",
    response_model=SuccessResponse[EmailUserResponse | GoogleUserResponse],
)
@limiter.limit("3/5minute")
async def get_current_user(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
):
    user: EmailUserResponse | GoogleUserResponse = await auth_service.get_current_user(
        curr_user
    )
    return SuccessResponse(message="User retrieved successfully", data=user)


@router.patch(
    "/auth/password-update",
    status_code=200,
    description="Update current password",
    response_model=SuccessResponse[EmailUserResponse],
)
@limiter.limit("3/5minute")
async def update_password(
    request: Request,
    password_update: PasswordUpdate,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    user: EmailUserResponse = await auth_service.update_password(
        curr_user, password_update, user_service
    )
    return SuccessResponse(message="User password updated successfully", data=user)


@router.patch(
    "/auth/password-reset",
    status_code=200,
    description=(
        "Reset Password with email."
        "A verification code is sent to the user's email before reset"
    ),
    response_model=SuccessResponse[EmailUserResponse],
)
@limiter.limit("3/5minute")
async def reset_password(
    request: Request,
    password_reset: PasswordReset,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    await auth_service.reset_password(password_reset, user_service)
    return SuccessResponse(message="Verification code sent to user email")


@router.post(
    "/auth/logout",
    status_code=201,
    response_model=SuccessResponse[LogoutResponse],
    description="Log out account",
)
@limiter.limit("3/5minute")
async def log_out(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    await auth_service.logout(curr_user, user_service)
    return SuccessResponse(message="Log out completed successfully")


@router.patch(
    "/auth/deactivate",
    status_code=200,
    response_model=SuccessResponse[DeactivateResponse],
    description=(
        "Delete account temporarily."
        "Deactivated account are deleted permanently after 14 days"
    ),
)
@limiter.limit("3/5minute")
async def deactivate_account(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    await auth_service.deactivate_account(curr_user, user_service)
    return SuccessResponse(message="Account deactivated successfully")


@router.patch(
    "/auth/reactivate",
    status_code=200,
    response_model=SuccessResponse[EmailUserResponse],
    description="Reactivate account",
)
@limiter.limit("3/5minute")
async def reactivate_account(
    request: Request,
    reactivate_user: ReactivateUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    await auth_service.reactivate_account(reactivate_user, user_service)
    return SuccessResponse(
        message="Account reactivated successfully. Login to access account"
    )


@router.delete("/auth", status_code=204, description="Delete account permanently")
@limiter.limit("3/5minute")
async def delete_account(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    await auth_service.delete_account(curr_user, user_service)
