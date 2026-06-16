import sentry_sdk
from sqlalchemy import Sequence
import sentry_sdk.logger as sentry_logger


from app.api.models.user import User
from app.api.models.slug import Slug
from app.api.repo.slug_repo import SlugRepository
from app.api.repo.redis_repo import RedisRepository
from app.api.schemas.slug import SlugCreate, SlugResponse, SlugUpdate
from app.core.exceptions import (
    ServerError,
    SlugExistsError,
    SlugNotFoundError,
    SlugsNotFoundError,
)


class SlugService:
    def __init__(self, slug_repo: SlugRepository, redis_repo: RedisRepository):
        self._slug_repo = slug_repo
        self._redis_repo = redis_repo

    async def create_slug(
        self, curr_user: User, slug_payload: SlugCreate
    ) -> SlugResponse:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        slug: str = slug_payload.custom_slug
        filter_key: str = f"users:{user_email}:slug"

        slug_exists: bool = await self._redis_repo.filter_value_exists(filter_key, slug)

        if slug_exists:
            slug_db: Slug = await self._slug_repo.get_record(custom_slug=slug)

            if slug_db:
                sentry_logger.error(
                    "User {email} provided an existing slug. Slug: {slug}",
                    email=user_email,
                    slug=slug,
                )
                raise SlugExistsError(slug=slug)

        try:
            slug_db: Slug = Slug(user_id=curr_user.id, custom_slug=slug)

            self._slug_repo.add(model=slug_db)
            await self._slug_repo.commit()
            await self._slug_repo.refresh(slug_db)

            if not self._redis_repo.filter_exists(filter_key):
                await self._redis_repo.create_filter(filter_key)
            await self._redis_repo.add_to_filter(filter_key, slug)

            sentry_logger.info("Slug created for user {email}", email=user_email)

            return SlugResponse.model_validate(slug_db)
        except Exception as e:
            await self._slug_repo.rollback()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while creating a slug for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def get_all_slugs(
        self,
        curr_user: User,
        sort: str | None,
        order: str | None,
        cursor: str | None,
        limit: int,
    ) -> list[SlugResponse]:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        try:
            data: dict = await self._slug_repo.get_records(
                sort, order, cursor, limit, user_id=curr_user.id, is_valid=True
            )

            cursor: str = data.get("cursor")
            slugs: Sequence[Slug] = data.get("data")

            if not slugs:
                sentry_logger.error("User {email} slugs not found", email=user_email)
                raise SlugsNotFoundError()

            slug_out: list[SlugResponse] = []
            for slug in slugs:
                slug_out.append(SlugResponse.model_validate(slug))

            sentry_logger.info("User {email} slugs retrieved", email=user_email)
            return slug_out, cursor
        except Exception as e:
            if isinstance(e, SlugsNotFoundError):
                raise SlugsNotFoundError()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving all slugs for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def get_slug(self, curr_user: User, slug: str) -> SlugResponse:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        try:
            slug_db: Slug = await self._slug_repo.get_record(custom_slug=slug)

            if not slug_db:
                sentry_logger.error(
                    "{slug} slug not found for user {email}",
                    email=user_email,
                    slug=slug,
                )
                raise SlugNotFoundError(slug=slug)

            sentry_logger.info("Slug retrieved for user {email}", email=user_email)
            return SlugResponse.model_validate(slug_db)
        except Exception as e:
            if isinstance(e, SlugNotFoundError):
                raise SlugNotFoundError(slug=slug)

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving slug for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def update_slug(
        self, curr_user: User, slug_update: SlugUpdate, slug: str
    ) -> SlugResponse:
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        slug_db: Slug = await self._slug_repo.get_record(custom_slug=slug)

        if not slug_db:
            sentry_logger.error(
                "{slug} slug not found for user {email}",
                email=user_email,
                slug=slug,
            )
            raise SlugNotFoundError(slug=slug)

        try:
            old_slug: str = slug_db.custom_slug
            filter_key: str = f"users:{user_email}:slug"
            new_slug: str = slug_update.new_custom_slug

            slug_db.custom_slug = new_slug

            await self._redis_repo.delete_filter_value(filter_key, old_slug)
            await self._redis_repo.add_to_filter(filter_key, new_slug)

            self._slug_repo.add(model=slug_db)
            await self._slug_repo.commit()
            await self._slug_repo.refresh(slug_db)

            sentry_logger.info(
                "{old_slug} updated to {new_slug} for user {email}",
                old_slug=old_slug,
                new_slug=new_slug,
                email=user_email,
            )

            return SlugResponse.model_validate(slug_db)
        except Exception as e:
            await self._slug_repo.rollback()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while updating slug for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    async def delete_slug(self, curr_user: User, slug: str):
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        slug_db: Slug = await self._slug_repo.get_record(custom_slug=slug)

        if not slug_db:
            sentry_logger.error(
                "{slug} slug not found for user {email}",
                email=user_email,
                slug=slug,
            )
            raise SlugNotFoundError(slug=slug)

        try:
            custom_slug: str = slug_db.custom_slug
            filter_key: str = f"users:{user_email}:slug"

            await self._redis_repo.delete_filter_value(filter_key, custom_slug)
            await self._slug_repo.delete(slug_db)
            await self._slug_repo.commit()

            sentry_logger.info(
                "{slug} deleted for user {email}", slug=custom_slug, email=user_email
            )
        except Exception as e:
            await self._slug_repo.rollback()

            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while deleting slug for user {email}",
                email=user_email,
            )
            raise ServerError() from e
