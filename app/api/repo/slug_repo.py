from typing import Any


from app.api.models.slug import Slug
from app.api.schemas.slug import SlugBase
from app.api.repo.base import BaseRepository


class SlugRepository(BaseRepository[SlugBase, Slug]):
    model = Slug

    def _entity_to_model(entity: SlugBase) -> model:
        return Slug(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "custom_slug" in filters:
            filter_conditions.append(self.model.custom_slug == filters["custom_slug"])
        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        sortable_fields: dict = {"created_at": self.model.created_at}
        return [sortable_fields.get(sort, self.model.created_at)]
