from typing import Any
from sqlalchemy import and_
from datetime import datetime, timezone


from app.api.models.user import User
from app.api.schemas.user import UserBase
from app.api.repo.base import BaseRepository


class UserRepository(BaseRepository[UserBase, User]):
    model = User

    def _entity_to_model(entity: UserBase) -> model:
        return User(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "email" in filters:
            filter_conditions.append(self.model.email == filters["email"])
        if "google_email" in filters:
            filter_conditions.append(self.model.google_email == filters["google_email"])
        if "is_active" in filters:
            filter_conditions.append(self.model.is_active.is_(filters["is_active"]))
        if "is_verified" in filters:
            filter_conditions.append(self.model.is_verified.is_(filters["is_verified"]))
        if "is_deactivated" in filters:
            filter_conditions.append(
                self.model.is_deactivated.is_(filters["is_deactivated"])
            )
        if "days_to_deactivation" in filters:
            today: datetime = datetime.now(timezone.utc)
            filter_conditions.append(
                and_(
                    self.model.seven_days_before
                    >= today,
                    self.model.five_days_before
                    <= today,
                )
            )
        if "delete_deactivated" in filters:
            filter_conditions.append(datetime.now(timezone.utc) >= self.model.delete_at)

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        sortable_fields: dict = {"created_at": self.model.created_at}
        return [sortable_fields.get(sort, self.model.created_at)]
