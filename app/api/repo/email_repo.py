from typing import Any
from sqlalchemy import select


from app.api.models.emails import Email
from app.api.schemas.emails import EmailBase
from app.api.repo.base import BaseRepository


class EmailRepository(BaseRepository[EmailBase, Email]):
    model = Email

    def flush(self):
        self._sync_session.flush()

    def refresh(self, model: Email):
        self._sync_session.refresh(model)

    def commit(self):
        self._sync_session.commit()

    def rollback(self):
        self._sync_session.rollback()

    def delete(self, model: Email):
        self._sync_session.delete(model)
        self._sync_session.flush()

    def get_record(
        self, **filters
    ) -> Email | None:
        filter_conditions: list[Any] = self._get_filters(**filters)

        res = self._sync_session.execute(select(Email).where(*filter_conditions))
        return res.scalar()

    def _entity_to_model(entity: EmailBase) -> Email:
        return Email(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "email_id" in filters:
            filter_conditions.append(self.model.id == filters["email_id"])
        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        pass
