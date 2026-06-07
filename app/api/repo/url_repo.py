from typing import Any
from datetime import datetime, timezone
from sqlalchemy import select


from app.api.models.url import Url
from app.api.models.slug import Slug
from app.api.schemas.url import UrlBase
from app.api.repo.base import BaseRepository


class UrlRepository(BaseRepository[UrlBase, Url]):
    model = Url

    @staticmethod
    def _entity_to_model(entity: UrlBase) -> model:
        return Url(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "user_id" in filters:
            filter_conditions.append(self.model.user_id == filters["user_id"])
        if "original_url" in filters:
            filter_conditions.append(self.model.original_url == filters["original_url"])
        if "shortened_url" in filters:
            filter_conditions.append(
                self.model.shortened_url == filters["shortened_url"]
            )
        if "is_valid" in filters:
            if filters["is_valid"]:
                filter_conditions.append(
                    self.model.expire_at > datetime.now(timezone.utc)
                )
            else:
                filter_conditions.append(
                    self.model.expire_at < datetime.now(timezone.utc)
                )

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        sortable_fields: dict = {
            "created_at": self.model.created_at,
            "last_updated_at": self.model.last_updated_at,
            "expire_at": self.model.expire_at,
        }
        return [sortable_fields.get(sort, self.model.created_at)]

    async def get_url(self, slug: str, *rows) -> Any:
        stmt = (
            select(*rows)
            .select_from(Slug)
            .join(self.model)
            .where(Slug.custom_slug == slug)
        )

        res = await self._async_session.execute(stmt)
        return res.first()
