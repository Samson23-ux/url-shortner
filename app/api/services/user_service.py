from app.api.repo.user_repo import UserRepository


class UserService:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    async def get_user_by_email(self, user_email: str):
        pass
