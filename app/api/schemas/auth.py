from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict, Field


from app.api.models.user import UserType
from app.api.models.otp import OtpPurpose, OtpStatus


class AuthBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TokenData(AuthBase):
    email: str
    user_type: UserType


class Token(AuthBase):
    access_token: str
    token_type: str = "bearer"


class EmailVerify(AuthBase):
    email: str
    otp_code: str
    password: str = Field(
        default=None,
        min_length=8,
        description="A password value should be passed for password reset"
    )


class ResendOtp(AuthBase):
    email: str


class EmailLogin(AuthBase):
    email: str
    password: str = Field(..., min_length=8)


class PasswordUpdate(AuthBase):
    curr_password: str
    new_password: str


class PasswordReset(AuthBase):
    email: EmailStr


class OtpInDB(AuthBase):
    otp: str
    user_id: UUID
    purpose: OtpPurpose
    status: OtpStatus = "valid"
    expires_at: datetime


class SignUpResponse(BaseModel):
    pass


class OtpResendResponseV1(BaseModel):
    pass


class LogoutResponse(BaseModel):
    pass


class DeactivateResponse(BaseModel):
    pass
