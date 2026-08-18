import sentry_sdk
import sentry_sdk.logger as sentry_logger


from app.core.config import get_settings
from app.api.models.user import User
from app.api.schemas.user import UserInDB, CachedUser
from app.api.repo.user_repo import UserRepository
from app.api.repo.redis_repo import RedisRepository
from app.core.exceptions import ServerError, UserNotFoundError


def _user_cache_key(email: str) -> str:
    return f"user:{email}"


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "type": user.type.value,
        "email": user.email or "",
        "google_email": user.google_email or "",
        "is_active": "1" if user.is_active else "0",
        "is_verified": "1" if user.is_verified else "0",
        "is_deactivated": "1" if user.is_deactivated else "0",
    }


def _deserialize_cached_user(cached: dict) -> CachedUser:
    return CachedUser(
        id=cached["id"],
        type=cached["type"],
        email=cached["email"] or None,
        google_email=cached["google_email"] or None,
        is_active=cached["is_active"] == "1",
        is_verified=cached["is_verified"] == "1",
        is_deactivated=cached["is_deactivated"] == "1",
    )


class UserService:
    def __init__(self, user_repo: UserRepository, redis_repo: RedisRepository):
        self._user_repo = user_repo
        self._redis_repo = redis_repo

    async def get_user_by_email(self, **filters) -> User:
        if "email" in filters:
            user_email: str = filters["email"]
        if "google_email" in filters:
            user_email: str = filters["google_email"]

        try:
            user: User | None = await self._user_repo.get_record(**filters)

            if not user:
                sentry_logger.error("User not found with email {email}", email=user_email)
                raise UserNotFoundError(user_email=user_email)

            return user
        except Exception as e:
            if isinstance(e, UserNotFoundError):
                raise UserNotFoundError(user_email=user_email)

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving user with email {email}",
                email=user_email
            )
            raise ServerError() from e

    async def _get_user_by_email(self, **filters) -> User | None:
        return await self._user_repo.get_record(**filters)

    async def get_active_user_cached(self, **filters) -> CachedUser:
        """
        Redis-first lookup for the hot, high-QPS routes (create/redirect).
        Returns a detached CachedUser, not a session-attached User — do not
        pass the result to update_user/delete_user. Falls back to the DB on
        a cache miss and repopulates the cache. update_user/delete_user
        invalidate the cache key on any change, so a cache hit here is
        never staler than the last write, bounded by the TTL either way.
        """
        user_email: str = filters.get("email") or filters.get("google_email")
        cache_key: str = _user_cache_key(user_email)

        cached: dict = await self._redis_repo.get_cached_user(cache_key)

        if cached:
            cached_user: CachedUser = _deserialize_cached_user(cached)

            if not cached_user.is_verified or cached_user.is_deactivated:
                sentry_logger.error(
                    "User not found with email {email}", email=user_email
                )
                raise UserNotFoundError(user_email=user_email)

            return cached_user

        user: User = await self.get_user_by_email(**filters)

        ttl: int = get_settings().ACCESS_TOKEN_EXPIRE_TIME * 60
        await self._redis_repo.cache_user(cache_key, _serialize_user(user), ttl)

        return CachedUser.model_validate(user)

    async def _cache_user(self, user: User):
        """Writes the current row state into the cache, e.g. after an
        update, so a still-cached CachedUser reflects is_active/
        is_deactivated changes (logout, deactivate/reactivate) without
        waiting for TTL expiry or a lazy re-fetch on the next hit."""
        ttl: int = get_settings().ACCESS_TOKEN_EXPIRE_TIME * 60
        value: dict = _serialize_user(user)

        if user.email:
            await self._redis_repo.cache_user(_user_cache_key(user.email), value, ttl)
        if user.google_email:
            await self._redis_repo.cache_user(_user_cache_key(user.google_email), value, ttl)

    async def _invalidate_user_cache(self, user: User):
        if user.email:
            await self._redis_repo.delete_key(_user_cache_key(user.email))
        if user.google_email:
            await self._redis_repo.delete_key(_user_cache_key(user.google_email))

    def get_deactivated_users(self) -> list[tuple]:
        return self._user_repo._get_records(User.email, User.delete_at, days_to_deactivation=True)

    async def create_user(self, user: UserInDB):
        try:
            self._user_repo.add(entity=user)
            await self._user_repo.commit()
        except Exception as e:
            await self._user_repo.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while creating user with email {email}",
                email=user.email
            )
            raise ServerError() from e

    async def update_user(self, user: User):
        try:
            self._user_repo.add(model=user)
            await self._user_repo.commit()
            await self._user_repo.refresh(user)
            await self._cache_user(user)
        except Exception as e:
            await self._user_repo.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while updating user with email {email}",
                email=user.email
            )
            raise ServerError() from e

    async def delete_user(self, user: User):
        try:
            await self._user_repo.delete(user)
            await self._user_repo.commit()
            await self._invalidate_user_cache(user)
        except Exception as e:
            await self._user_repo.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while deleting user with email {email}",
                email=user.email
            )
            raise ServerError() from e

    def delete_deactivated_users(self):
        self._user_repo.bulk_delete(delete_deactivated=True)
        self._user_repo.sync_commit()
