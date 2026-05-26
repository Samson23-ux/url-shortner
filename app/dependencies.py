import logging
from fastapi import Depends
from typing import Annotated
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm


from app.api.models.user import User
from app.core.config import get_settings
from app.core.security import decode_token
from app.database.session import get_session
from app.api.repo.url_repo import UrlRepository
from app.api.repo.otp_repo import OtpRepository
from app.api.repo.user_repo import UserRepository
from app.api.repo.slug_repo import SlugRepository
from app.core.exceptions import AuthenticationError
from app.api.services.url_service import UrlService
from app.api.services.auth_service import AuthService
from app.api.services.user_service import UserService
from app.api.services.slug_service import SlugService
from app.api.repo.analytics_service import AnalyticsRepository
from app.api.services.analytics_service import AnalyticsService


logger = logging.getLogger(__name__)


# Auth bearer
bearer = HTTPBearer(auto_error=False)


# ------------------- DB dependency ------------------------------ #

DBSession = Annotated[AsyncSession, Depends(get_session)]


#  ------------------- Repo dependency ----------------------------- #

async def get_url_repo(session: DBSession) -> UrlRepository:
    return UrlRepository(session=session)

async def get_otp_repo(session: DBSession) -> OtpRepository:
    return OtpRepository(session=session)

async def get_user_repo(session: DBSession) -> UserRepository:
    return UserRepository(session=session)

async def get_slug_repo(session: DBSession) -> SlugRepository:
    return SlugRepository(session=session)

async def get_analytics_repo(session: DBSession) -> AnalyticsRepository:
    return AnalyticsRepository(session=session)

UrlRepo = Annotated[UrlRepository, Depends(get_url_repo)]
OtpRepo = Annotated[OtpRepository, Depends(get_otp_repo)]
UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
SlugRepo = Annotated[SlugRepository, Depends(get_slug_repo)]
AnalyticsRepo = Annotated[AnalyticsRepository, Depends(get_analytics_repo)]


#  -------------------- Service dependency ---------------------------- #

async def get_url_service(url_repo: UrlRepo) -> UrlService:
    return UrlService(url_repo=url_repo)

async def get_auth_service(otp_repo: OtpRepo) -> AuthService:
    return AuthService(otp_repo=otp_repo)

async def get_user_service(user_repo: UserRepo) -> UserService:
    return UserService(user_repo=user_repo)

async def get_slug_service(slug_repo: SlugRepo) -> SlugService:
    return SlugService(slug_repo=slug_repo)

async def get_analytics_service(analytics_repo: AnalyticsRepo) -> AnalyticsService:
    return AnalyticsService(analytics_repo=analytics_repo)

UrlServiceDep = Annotated[UrlService, Depends(get_url_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
SlugServiceDep = Annotated[SlugService, Depends(get_slug_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


# ------------------------ Auth dependency ---------------------------- #

async def get_current_user(
    user_service: UserServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]
) -> User:
    token: str | None = credentials.credentials
    key: str = get_settings().ACCESS_TOKEN_SECRET_KEY

    payload: dict = await decode_token(token, key)

    if not payload:
        logger.error("User not authenticated")
        raise AuthenticationError()

    user_email: str = payload.get("sub")

    user: User = await user_service.get_user_by_email(user_email)

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(curr_user: CurrentUser):
    if curr_user.is_active is False:
        raise AuthenticationError()
    return curr_user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


LoginForm = Annotated[OAuth2PasswordRequestForm, Depends()]
