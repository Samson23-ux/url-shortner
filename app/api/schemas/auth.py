from pydantic import BaseModel, EmailStr, ConfigDict


class AuthBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class TokenData(AuthBase):
    email: str


class Token(AuthBase):
    access_token: str
    token_type: str = "bearer"


class EmailVerify(AuthBase):
    email: str
    otp_code: str


class ResendOtp(AuthBase):
    email: str


class EmailLogin(AuthBase):
    email: str
    password: str


class PasswordUpdate(AuthBase):
    curr_password: str
    new_password: str


class PasswordReset(AuthBase):
    email: EmailStr
    new_password: str


class SignUpResponse(BaseModel):
    pass


class OtpResendResponseV1(BaseModel):
    pass


class LogoutResponse(BaseModel):
    pass


class DeactivateResponse(BaseModel):
    pass
