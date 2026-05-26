from typing import Any


from app.api.models.url import Url
from app.api.repo.base import BaseRepository
from app.api.schemas.analytics import AnalyticsBase


class AnalyticsRepository(BaseRepository[AnalyticsBase, Url]):
    model = Url

    def _entity_to_model(entity: AnalyticsBase) -> model:
        return Url(**entity.model_dump())

    def _model_to_entity(model: Url, entity: AnalyticsBase) -> AnalyticsBase:
        return entity.model_validate(model)

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "original_url" in filters:
            filter_conditions.append(self.model.original_url == filters["original_url"])
        if "shortened_url" in filters:
            filter_conditions.append(self.model.shortened_url == filters["shortened_url"])
        if "status" in filters:
            filter_conditions.append(self.model.status == filters["status"])

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        pass
