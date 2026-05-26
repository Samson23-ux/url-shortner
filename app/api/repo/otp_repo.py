from typing import Any


from app.api.models.otp import Otp
from app.api.schemas.auth import AuthBase
from app.api.repo.base import BaseRepository


class OtpRepository(BaseRepository[AuthBase, Otp]):
    model = Otp

    def _entity_to_model(entity: AuthBase) -> model:
        return Otp(**entity.model_dump())

    def _model_to_entity(model: Otp, entity: AuthBase) -> AuthBase:
        return entity.model_validate(model)

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "otp" in filters:
            filter_conditions.append(self.model.otp == filters["otp"])

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        pass
