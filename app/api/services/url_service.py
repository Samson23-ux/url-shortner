import sentry_sdk
from uuid import UUID
from sqlalchemy import Sequence
import sentry_sdk.logger as sentry_logger
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta, date


from app.api.models.url import Url
from app.api.models.slug import Slug
from app.api.models.user import User
from app.core.config import get_settings
from app.utils import generate_random_slug
from app.api.repo.url_repo import UrlRepository
from app.api.repo.slug_repo import SlugRepository
from app.api.repo.redis_repo import RedisRepository
from app.api.repo.unit_of_work import UnitOfWorkRepository
from app.api.schemas.url import ShortenUrl, UrlUpdate, UrlResponse
from app.core.exceptions import (
    ServerError,
    SlugExistsError,
    UrlExistsError,
    UrlNotFoundError,
    UrlExpiredError,
    UrlsNotFoundError,
)


class UrlService:
    MAX_RETRIES = 5

    def __init__(self, url_repo: UrlRepository, redis_repo: RedisRepository):
        self._uow = None
        self._slug_repo = None
        self._url_repo = url_repo
        self._redis_repo = redis_repo

    async def _create_slug(
        self, slug: str | None, filter_key: str, user_email: str, user_id: UUID
    ) -> Slug:
        """
        Create a custom slug or use the received slug
        Redis cuckoo filter is queried for quick existence check
        and fallback to db if slug exists for confirmation
        """
        if slug:
            slug_exists: bool = await self._redis_repo.filter_value_exists(
                filter_key, slug
            )

            if slug_exists:
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
                slug_db: Slug = Slug(user_id=user_id, custom_slug=slug)

                self._slug_repo.add(model=slug_db)
                await self._slug_repo.flush()
                await self._slug_repo.refresh(slug_db)

                if not self._redis_repo.filter_exists(filter_key):
                    await self._redis_repo.create_filter(filter_key)
                await self._redis_repo.add_to_filter(filter_key, slug)

                return slug_db
            except IntegrityError:
                await self._uow.rollback()
                slug = generate_random_slug()

        sentry_logger.error("Failed to generate a unique custom slug automatically")
        raise ServerError()

    async def _create_url(
        self,
        url: str | None,
        filter_key: str,
        slug_id: UUID,
        user_email: str,
        user_id: UUID,
        shortened_url: str,
    ) -> Url:
        url_exists: bool = await self._redis_repo.filter_value_exists(filter_key, url)

        if url_exists:
            url_db: Url = await self._url_repo.get_record(original_url=url)

            if url_db.expire_at > datetime.now(timezone.utc):
                sentry_logger.error(
                    "User {email} provided an existing url. Url: {url}",
                    email=user_email,
                    url=url,
                )
                raise UrlExistsError(url=url)
            else:
                # update shortened url
                url_db.slug_id = slug_id
                url_db.shortened_url = shortened_url
                url_db.expire_at = datetime.now(timezone.utc) + timedelta(
                    days=get_settings().URL_EXPIRE_TIME
                )
                url_db.last_updated_at = datetime.now(timezone.utc)
        else:
            if not self._redis_repo.filter_exists(filter_key):
                await self._redis_repo.create_filter(filter_key)
            await self._redis_repo.add_to_filter(filter_key, url)

            url_db: Url = Url(
                user_id=user_id,
                original_url=url,
                slug_id=slug_id,
                shortened_url=shortened_url,
                expire_at=datetime.now(timezone.utc)
                + timedelta(days=get_settings().URL_EXPIRE_TIME),
            )

        self._url_repo.add(model=url_db)
        await self._slug_repo.flush()
        await self._slug_repo.refresh(url_db)

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

        url_filter_key: str = f"users:{user_email}:url"
        slug_filter_key: str = f"users:{user_email}:slug"

        try:
            slug: Slug = await self._create_slug(
                payload_slug, slug_filter_key, user_email, curr_user.id
            )
            shortened_url: str = f"{get_settings().SHORTEN_URL}/{slug.custom_slug}"

            url_db: Url = await self._create_url(
                payload_url,
                url_filter_key,
                slug.id,
                user_email,
                curr_user.id,
                shortened_url,
            )

            await uow.commit()

            sentry_logger.info("Url shortened for user {email}", email=user_email)
            return UrlResponse.model_validate(url_db)
        except Exception as e:
            if isinstance(e, SlugExistsError):
                raise SlugExistsError(slug=payload_slug)
            if isinstance(e, UrlExistsError):
                raise UrlExistsError(url=payload_url)

            await uow.rollback()
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while creating a short url for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def redirect_to_url(self, curr_user: User, slug: str) -> str:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        try:
            url_db: tuple = await self._url_repo.get_url(
                slug,
                Url.id,
                Url.original_url,
                Url.shortened_url,
                Url.expire_at,
            )

            if not url_db:
                sentry_logger.error(
                    "No url found with the slug {slug} for user {email}",
                    slug=slug,
                    email=user_email,
                )
                raise UrlNotFoundError(slug=slug)

            url_id, original_url, shortened_url, expire_at = url_db

            if expire_at <= datetime.now(timezone.utc):
                raise UrlExpiredError(url=shortened_url)

            # use redis counter to track clicks per day
            ttl: int = 60 * 60 * 48
            key: str = f"clicks:{url_id}:{date.today().isoformat()}"
            await self._redis_repo.increment_clicks(key, ttl)

            sentry_logger.info(
                "{url} retrieved for user {email}",
                url=original_url,
                email=user_email,
            )
            return original_url
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

        url_db: tuple = await self._url_repo.get_url(slug, Url)

        if not url_db:
            sentry_logger.error(
                "No url found with the slug {slug} for user {email}",
                slug=slug,
                email=user_email,
            )
            raise UrlNotFoundError(slug=slug)
        url_db: Url | None = url_db[0]

        try:
            old_url: str = url_db.original_url
            filter_key: str = f"users:{user_email}:url"
            new_url: str = url_update.new_original_url

            url_db.original_url = new_url
            url_db.last_updated_at = datetime.now(timezone.utc)

            await self._redis_repo.delete_filter_value(filter_key, old_url)
            await self._redis_repo.add_to_filter(filter_key, new_url)

            self._url_repo.add(model=url_db)
            await self._url_repo.commit()
            await self._url_repo.refresh(url_db)

            sentry_logger.info(
                "{old_url} updated to {new_url} for user {email}",
                old_url=old_url,
                new_url=new_url,
                email=user_email,
            )

            return UrlResponse.model_validate(url_db)
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

        url_db: tuple = await self._url_repo.get_url(slug, Url)

        if not url_db:
            sentry_logger.error(
                "No url found with the slug {slug} for user {email}",
                slug=slug,
                email=user_email,
            )
            raise UrlNotFoundError(slug=slug)
        url_db: Url | None = url_db[0]

        try:
            original_url: str = url_db.original_url
            filter_key: str = f"users:{user_email}:url"

            await self._redis_repo.delete_filter_value(filter_key, original_url)
            await self._url_repo.delete(url_db)

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
