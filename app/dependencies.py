import time
from typing import Annotated
from redis.asyncio import Redis
from slowapi.util import get_remote_address
from fastapi import Depends, Request
import sentry_sdk.logger as sentry_logger
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


from app.api.models.user import User
from app.api.schemas.user import CachedUser
from app.core.config import get_settings
from app.core.security import decode_token
from app.database.session import get_session
from app.api.repo.url_repo import UrlRepository
from app.api.repo.otp_repo import OtpRepository
from app.api.repo.user_repo import UserRepository
from app.api.repo.slug_repo import SlugRepository
from app.api.repo.redis_repo import RedisRepository
from app.core.exceptions import AuthenticationError, RateLimitError
from app.api.services.url_service import UrlService
from app.api.services.auth_service import AuthService
from app.api.services.user_service import UserService
from app.api.services.slug_service import SlugService
from app.api.repo.unit_of_work import UnitOfWorkRepository
from app.api.repo.analytics_repo import AnalyticsRepository
from app.api.services.analytics_service import AnalyticsService


# Auth bearer
bearer = HTTPBearer(auto_error=False)


# ------------------- DB dependency ------------------------------ #

DBSession = Annotated[AsyncSession, Depends(get_session)]


# ------------------- Redis dependency ------------------------------ #
async def get_redis_client(request: Request):
    redis_client = request.app.state.redis
    return redis_client


RedisDep = Annotated[Redis, Depends(get_redis_client)]


#  ------------------- Repo dependency ----------------------------- #


async def get_url_repo(session: DBSession) -> UrlRepository:
    return UrlRepository(async_session=session)


async def get_otp_repo(session: DBSession) -> OtpRepository:
    return OtpRepository(async_session=session)


async def get_user_repo(session: DBSession) -> UserRepository:
    return UserRepository(async_session=session)


async def get_slug_repo(session: DBSession) -> SlugRepository:
    return SlugRepository(async_session=session)


async def get_analytics_repo(session: DBSession) -> AnalyticsRepository:
    return AnalyticsRepository(async_session=session)


async def get_redis_repo(redis: RedisDep) -> RedisRepository:
    return RedisRepository(async_redis=redis)


async def get_unit_of_work(session: DBSession) -> UnitOfWorkRepository:
    return UnitOfWorkRepository(session=session)


UrlRepo = Annotated[UrlRepository, Depends(get_url_repo)]
OtpRepo = Annotated[OtpRepository, Depends(get_otp_repo)]
UserRepo = Annotated[UserRepository, Depends(get_user_repo)]
SlugRepo = Annotated[SlugRepository, Depends(get_slug_repo)]
RedisRepo = Annotated[RedisRepository, Depends(get_redis_repo)]
UnitOfWorkRepo = Annotated[UnitOfWorkRepository, Depends(get_unit_of_work)]
AnalyticsRepo = Annotated[AnalyticsRepository, Depends(get_analytics_repo)]


#  -------------------- Service dependency ---------------------------- #


async def get_url_service(url_repo: UrlRepo, redis_repo: RedisRepo) -> UrlService:
    return UrlService(url_repo=url_repo, redis_repo=redis_repo)


async def get_auth_service(otp_repo: OtpRepo, redis_repo: RedisRepo) -> AuthService:
    return AuthService(otp_repo=otp_repo, redis_repo=redis_repo)


async def get_user_service(user_repo: UserRepo, redis_repo: RedisRepo) -> UserService:
    return UserService(user_repo=user_repo, redis_repo=redis_repo)


async def get_slug_service(slug_repo: SlugRepo, redis_repo: RedisRepo) -> SlugService:
    return SlugService(slug_repo=slug_repo, redis_repo=redis_repo)


async def get_analytics_service(
    analytics_repo: AnalyticsRepo, redis_repo: RedisRepo
) -> AnalyticsService:
    return AnalyticsService(analytics_repo=analytics_repo, redis_repo=redis_repo)


UrlServiceDep = Annotated[UrlService, Depends(get_url_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
SlugServiceDep = Annotated[SlugService, Depends(get_slug_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


# ------------------------ Auth dependency ---------------------------- #


async def _decode_credentials(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
) -> tuple[str, str]:
    """Returns (user_email_or_google_email, user_type) from a validated JWT."""
    if not credentials:
        sentry_logger.error("User not authenticated")
        raise AuthenticationError()

    token: str | None = credentials.credentials
    key: str = get_settings().ACCESS_TOKEN_SECRET_KEY

    payload: dict = await decode_token(token, key)

    if not payload:
        sentry_logger.error("User not authenticated")
        raise AuthenticationError()

    return payload.get("sub"), payload.get("usertype")


async def get_current_user(
    user_service: UserServiceDep,
    identity: Annotated[tuple[str, str], Depends(_decode_credentials)],
) -> User:
    user_email, user_type = identity

    if user_type == "email":
        user: User = await user_service.get_user_by_email(
            email=user_email, is_verified=True, is_deactivated=False
        )
    else:
        user: User = await user_service.get_user_by_email(
            google_email=user_email, is_verified=True, is_deactivated=False
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_user(curr_user: CurrentUser):
    if curr_user.is_active is False:
        raise AuthenticationError()
    return curr_user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


# Redis-first variant for hot, routes (e.g. create/redirect on the
# url shortener). Returns a detached CachedUser — safe to read attributes
# off, but never pass it to UserService.update_user/delete_user, since it
# isn't attached to the request's DB session. Routes that mutate the user
# record (logout, deactivate/reactivate/delete account) must keep using
# CurrentActiveUser above.
async def get_current_user_cached(
    user_service: UserServiceDep,
    identity: Annotated[tuple[str, str], Depends(_decode_credentials)],
) -> CachedUser:
    user_email, user_type = identity

    if user_type == "email":
        return await user_service.get_active_user_cached(
            email=user_email, is_verified=True, is_deactivated=False
        )
    return await user_service.get_active_user_cached(
        google_email=user_email, is_verified=True, is_deactivated=False
    )


CurrentCachedUser = Annotated[CachedUser, Depends(get_current_user_cached)]


async def get_current_active_user_cached(curr_user: CurrentCachedUser) -> CachedUser:
    if curr_user.is_active is False:
        raise AuthenticationError()
    return curr_user


CurrentActiveUserFast = Annotated[CachedUser, Depends(get_current_active_user_cached)]
