from typing import Annotated
from pydantic import EmailStr
from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Request, Response, Form


from app.api.schemas.response import SuccessResponse
from app.api.schemas.user import GoogleUserResponse, EmailUserResponse
from app.dependencies import (
    AuthServiceDep,
    UserServiceDep,
    LoginForm,
    CurrentActiveUser,
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
async def sign_up_with_email(
    request: Request,
    email_login: EmailLogin,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.get(
    "/auth/google",
    status_code=302,
    response_class=RedirectResponse,
    description="Sign in with Google account",
)
async def sign_in_with_google(request: Request):
    pass


@router.get(
    "/auth/google/callback",
    status_code=200,
    response_model=SuccessResponse[GoogleUserResponse],
    description="Google redirect uri",
)
async def google_callback(
    request: Request,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.patch(
    "/auth/verify",
    status_code=200,
    response_model=SuccessResponse[EmailUserResponse],
    description="Verify account by submitting the received otp code",
)
async def verify_account(
    request: Request,
    email_verify: EmailVerify,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.post(
    "/auth/verify/resend",
    status_code=201,
    description="Resend verification code",
    response_model=SuccessResponse[OtpResendResponseV1],
)
async def resend_otp(
    request: Request,
    otp_resend: ResendOtp,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.post(
    "/auth/login",
    status_code=201,
    description="Login with email and password",
    response_model=SuccessResponse[Token],
)
async def login(
    request: Request,
    response: Response,
    login_form: LoginForm,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.post(
    "/auth/refresh",
    status_code=201,
    response_model=SuccessResponse[Token],
    description="Create new access token for user with a valid refresh token",
)
async def create_new_token(
    request: Request,
    response: Response,
):
    pass


@router.get(
    "/auth/me",
    status_code=200,
    description="Get current active user",
    response_model=SuccessResponse[EmailUserResponse | GoogleUserResponse],
)
async def get_current_user(
    request: Request,
    curr_user: CurrentActiveUser,
):
    pass


@router.patch(
    "/auth/password-update",
    status_code=200,
    description="Update current password",
    response_model=SuccessResponse[EmailUserResponse],
)
async def update_password(
    request: Request,
    password_update: PasswordUpdate,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    #### check the user type if email and google user (add type filter to db query)
    pass


@router.patch(
    "/auth/password-reset",
    status_code=200,
    description=(
        "Reset Password with email."
        "A verification code is sent to the user's email on completion"
    ),
    response_model=SuccessResponse[EmailUserResponse],
)
async def reset_password(
    request: Request,
    password_reset: PasswordReset,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.post(
    "/auth/logout",
    status_code=201,
    response_model=SuccessResponse[LogoutResponse],
    description="Log out account",
)
async def log_out(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.patch(
    "/auth/deactivate",
    status_code=200,
    response_model=SuccessResponse[DeactivateResponse],
    description=(
        "Delete account temporarily."
        "Deactivated account are deleted permanently after 14 days"
    ),
)
async def deactivate_account(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.patch(
    "/auth/reactivate",
    status_code=200,
    response_model=SuccessResponse[EmailUserResponse],
    description="Reactivate account",
)
async def reactivate_account(
    request: Request,
    email: Annotated[
        EmailStr, Form(..., description="A valid email address for an existing account")
    ],
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass


@router.delete(
    "/auth",
    status_code=204,
    description="Delete account permanently"
)
async def delete_account(
    request: Request,
    curr_user: CurrentActiveUser,
    auth_service: AuthServiceDep,
    user_service: UserServiceDep,
):
    pass
