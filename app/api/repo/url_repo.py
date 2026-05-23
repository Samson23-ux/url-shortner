from typing import Any


from app.api.models.url import Url
from app.api.schemas.url import UrlBase
from app.api.repo.base import BaseRepository


class UrlRepository(BaseRepository[UrlBase, Url]):
    model = Url

    def _entity_to_model(entity: UrlBase) -> model:
        return Url(**entity.model_dump())

    def _model_to_entity(model: Url) -> UrlBase:
        return UrlBase.model_validate(model)

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "original_url" in filters:
            filter_conditions.append(self.model.original_url == filters["original_url"])
        if "shortened_url" in filters:
            filter_conditions.append(self.model.shortened_url == filters["shortened_url"])

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        sortable_fields: dict = {
            "created_at": self.model.created_at,
            "last_updated_at": self.model.last_updated_at,
            "expire_at": self.model.expire_at
        }
        return [sortable_fields.get(sort, self.model.created_at)]
