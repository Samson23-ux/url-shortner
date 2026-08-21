from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid7

import sentry_sdk
import sentry_sdk.logger as sentry_logger
from sqlalchemy import Sequence
from sqlalchemy.exc import IntegrityError

from app.api.models.slug import Slug
from app.api.models.url import Url
from app.api.models.user import User
from app.api.repo.redis_repo import RedisRepository
from app.api.repo.slug_repo import SlugRepository
from app.api.repo.unit_of_work import UnitOfWorkRepository
from app.api.repo.url_repo import UrlRepository
from app.api.schemas.slug import SlugInDB
from app.api.schemas.url import ShortenUrl, UrlInDB, UrlResponse, UrlUpdate
from app.core.config import get_settings
from app.core.exceptions import (
    ServerError,
    SlugExistsError,
    UrlExistsError,
    UrlExpiredError,
    UrlNotFoundError,
    UrlsNotFoundError,
)
from app.utils import generate_random_slug


class UrlService:
    MAX_RETRIES = 5

    def __init__(self, url_repo: UrlRepository, redis_repo: RedisRepository):
        self._uow = None
        self._slug_repo = None
        self._url_repo = url_repo
        self._redis_repo = redis_repo

    async def _create_slug(
        self, slug: str | None, user_email: str, user_id: UUID
    ) -> Slug:
        """
        Create a custom slug or use the received slug
        Redis cuckoo filter is queried for quick existence check
        and fallback to db if slug exists for confirmation
        """
        if slug:
            slug_db: Slug = await self._slug_repo.get_record(custom_slug=slug)

            if slug_db:
                sentry_logger.error(
                    "User {email} provided an existing slug. Slug: {slug}",
                    email=user_email,
                    slug=slug,
                )
                raise SlugExistsError(slug=slug)
        else:
            slug = generate_random_slug()

        for _ in range(self.MAX_RETRIES):
            try:
                slug_db: SlugInDB = SlugInDB(
                    id=uuid7(), user_id=user_id, custom_slug=slug
                )
                await self._slug_repo.insert_slug(slug_db)

                return slug_db
            except IntegrityError:
                await self._uow.rollback()
                slug = generate_random_slug()

        sentry_logger.error("Failed to generate a unique custom slug automatically")
        raise ServerError()

    async def _create_url(
        self,
        url: str | None,
        slug_id: UUID,
        user_email: str,
        user_id: UUID,
        shortened_url: str,
    ) -> Url:
        url_db: UrlInDB = UrlInDB(
            id=uuid7(),
            user_id=user_id,
            slug_id=slug_id,
            original_url=url,
            shortened_url=shortened_url,
            expire_at=datetime.now(UTC)
            + timedelta(days=get_settings().URL_EXPIRE_TIME),
        )
        res = await self._url_repo.insert_url(url_db)

        # slug_id differs when the url already exists
        # since only the original_url is updated on conflict
        if slug_id != res.slug_id:
            if res.expire_at > datetime.now(UTC):
                sentry_logger.error(
                    "User {email} provided an existing url. Url: {url}",
                    email=user_email,
                    url=url,
                )
                raise UrlExistsError(url=url)

            url_db.id = res.id
            url_db.slug_id = slug_id
            url_db.shortened_url = shortened_url
            url_db.last_updated_at = datetime.now(UTC)
            url_db.expire_at = datetime.now(UTC) + timedelta(
                days=get_settings().URL_EXPIRE_TIME
            )

            await self._url_repo.update_url(url_db)

        return url_db

    async def shorten_url(
        self, uow: UnitOfWorkRepository, curr_user: User, url_payload: ShortenUrl
    ) -> UrlResponse:
        # close active sessions
        await self._url_repo.aclose()

        self._uow = uow
        self._url_repo = UrlRepository(self._uow._session)
        self._slug_repo = SlugRepository(self._uow._session)

        payload_slug: str = url_payload.custom_slug
        payload_url: str = url_payload.original_url

        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        try:
            slug: Slug = await self._create_slug(payload_slug, user_email, curr_user.id)
            shortened_url: str = f"{get_settings().SHORTEN_URL}/{slug.custom_slug}"

            url_db: UrlInDB = await self._create_url(
                payload_url,
                slug.id,
                user_email,
                curr_user.id,
                shortened_url,
            )

            await uow.commit()

            sentry_logger.info("Url shortened for user {email}", email=user_email)
            return UrlResponse(**url_db.model_dump())
        except Exception as e:
            await uow.rollback()

            if isinstance(e, SlugExistsError):
                raise SlugExistsError(slug=payload_slug)
            if isinstance(e, UrlExistsError):
                raise UrlExistsError(url=payload_url)

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while creating a short url for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def redirect_to_url(self, curr_user: User, slug: str) -> tuple[str, bool]:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        cache_key: str = f"url:{slug}"

        try:
            cached_url: dict = await self._redis_repo.get_cached_url(cache_key)
            cache_hit: bool = bool(cached_url)

            if cached_url:
                url_id: str = cached_url["id"]
                original_url: str = cached_url["original_url"]
                shortened_url: str = cached_url["shortened_url"]
                expire_at: datetime = datetime.fromisoformat(cached_url["expire_at"])
            else:
                shortened_url: str = f"{get_settings().SHORTEN_URL}/{slug}"
                url: Url | None = await self._url_repo.get_record(
                    shortened_url=shortened_url
                )

                if not url:
                    sentry_logger.error(
                        "No url found with the slug {slug} for user {email}",
                        slug=slug,
                        email=user_email,
                    )
                    raise UrlNotFoundError(slug=slug)

                url_id: str = url.id
                expire_at: datetime = url.expire_at
                original_url: str = url.original_url
                shortened_url: str = url.shortened_url

            if expire_at <= datetime.now(UTC):
                raise UrlExpiredError(url=shortened_url)

            if not cached_url:
                cache_ttl: int = int(
                    (expire_at - datetime.now(UTC)).total_seconds()
                )
                await self._redis_repo.cache_url(
                    cache_key,
                    {
                        "id": str(url_id),
                        "original_url": original_url,
                        "shortened_url": shortened_url,
                        "expire_at": expire_at.isoformat(),
                    },
                    cache_ttl,
                )

            # use redis counter to track clicks per day
            ttl: int = 60 * 60 * 48
            key: str = f"clicks:{url_id}:{datetime.now(UTC).date().isoformat()}"
            await self._redis_repo.increment_clicks(key, ttl)

            sentry_logger.info(
                "{url} retrieved for user {email}",
                url=original_url,
                email=user_email,
            )
            return original_url, cache_hit
        except Exception as e:
            if isinstance(e, UrlNotFoundError):
                raise UrlNotFoundError(slug=slug)
            if isinstance(e, UrlExpiredError):
                raise UrlExpiredError(url=shortened_url)

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving url for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def get_all_urls(
        self,
        curr_user: User,
        sort: str | None,
        order: str,
        cursor: str | None,
        limit: int,
    ) -> list[UrlResponse]:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        try:
            data: dict = await self._url_repo.get_records(
                sort, order, cursor, limit, user_id=curr_user.id, is_valid=True
            )

            cursor: str = data.get("cursor")
            urls: Sequence[Url] = data.get("data")

            if not urls:
                sentry_logger.error("User {email} urls not found", email=user_email)
                raise UrlsNotFoundError()

            url_out: list[UrlResponse] = []
            for url in urls:
                url_out.append(UrlResponse.model_validate(url))

            sentry_logger.info("User {email} urls retrieved", email=user_email)
            return url_out, cursor
        except Exception as e:
            if isinstance(e, UrlsNotFoundError):
                raise UrlsNotFoundError()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving all urls for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def update_url(
        self, curr_user: User, url_update: UrlUpdate, slug: str
    ) -> UrlResponse:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        shortened_url: str = f"{get_settings().SHORTEN_URL}/{slug}"
        url: Url | None = await self._url_repo.get_record(shortened_url=shortened_url)

        if not url:
            sentry_logger.error(
                "No url found with the slug {slug} for user {email}",
                slug=slug,
                email=user_email,
            )
            raise UrlNotFoundError(slug=slug)

        try:
            old_url: str = url.original_url
            new_url: str = url_update.new_original_url

            url.original_url = new_url
            url.last_updated_at = datetime.now(UTC)

            await self._redis_repo.delete_key(f"url:{slug}")

            self._url_repo.add(model=url)
            await self._url_repo.commit()
            await self._url_repo.refresh(url)

            sentry_logger.info(
                "{old_url} updated to {new_url} for user {email}",
                old_url=old_url,
                new_url=new_url,
                email=user_email,
            )

            return UrlResponse.model_validate(url)
        except Exception as e:
            await self._url_repo.rollback()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while updating url for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def delete_url(self, curr_user: User, slug: str):
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        shortened_url: str = f"{get_settings().SHORTEN_URL}/{slug}"
        url: Url | None = await self._url_repo.get_record(shortened_url=shortened_url)

        if not url:
            sentry_logger.error(
                "No url found with the slug {slug} for user {email}",
                slug=slug,
                email=user_email,
            )
            raise UrlNotFoundError(slug=slug)

        try:
            original_url: str = url.original_url

            await self._redis_repo.delete_key(f"url:{slug}")
            await self._url_repo.delete(url)
            await self._url_repo.commit()

            sentry_logger.info(
                "{url} deleted for user {email}", url=original_url, email=user_email
            )
        except Exception as e:
            await self._url_repo.rollback()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while deleting url for user {email}",
                email=user_email,
            )
            raise ServerError() from e
