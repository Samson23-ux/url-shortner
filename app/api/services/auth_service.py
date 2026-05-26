from app.api.schemas.auth import EmailLogin
from app.api.repo.otp_repo import OtpRepository
from app.api.services.user_service import UserService


class AuthService:
    def __init__(self, otp_repo: OtpRepository):
        self._otp_repo = otp_repo

    async def sign_up_with_email(self, email_login: EmailLogin, user_service: UserService):
        pass
