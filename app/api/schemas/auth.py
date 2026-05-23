from pydantic import BaseModel


class TokenData(BaseModel):
    email: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EmailVerify(BaseModel):
    email: str
    otp_code: str


class ResendOtp(BaseModel):
    email: str


class EmailLogin(BaseModel):
    email: str
    password: str
