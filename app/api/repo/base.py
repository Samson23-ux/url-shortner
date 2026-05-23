from pydantic import BaseModel
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TypeVar, Generic, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, Sequence, desc, asc


from app.api.models.base import Base
from app.core.security import decode_cursor, encode_cursor


Entity = TypeVar("Entity", bound=BaseModel)
SqlalchemyModel = TypeVar("SqlalchemyModel", bound=Base)


class BaseRepository(ABC, Generic[Entity, SqlalchemyModel]):
    def __init__(self, session: AsyncSession):
        self._session = session

    model: type[SqlalchemyModel]

    def add(self, entity: Entity):
        model: SqlalchemyModel = self._entity_to_model(entity)
        self._session.add(model)

    async def flush(self):
        await self._session.flush()

    async def refresh(self, model: SqlalchemyModel):
        await self._session.refresh(model)

    async def commit(self):
        await self._session.commit()

    async def rollback(self):
        await self._session.rollback()

    async def delete(self, model: SqlalchemyModel):
        await self._session.delete(model)
        await self._session.flush()

    async def get_record(self, model: SqlalchemyModel, **filters) -> SqlalchemyModel:
        filter_conditions: list[Any] = self._get_filters(**filters)

        res = await self._session.execute(select(model).where(*filter_conditions))
        return res.scalar()

    async def get_records(
        self,
        model: SqlalchemyModel,
        sort: str,
        order: str,
        cursor: str,
        limit: int,
        **filters,
    ) -> Sequence[SqlalchemyModel]:
        filter_conditions: list[Any] = self._get_filters(**filters)
        sort_fields: list[Any] = self._get_sort_fields(sort)

        cursor_payload: dict = await decode_cursor(cursor)

        if not cursor_payload:
            """get records from the first record in db"""

            if order.lower() == "desc":
                order = desc(*sort_fields)
            else:
                order = asc(*sort_fields)

            stmt = (
                select(model).where(*filter_conditions).order_by(order).limit(limit + 1)
            )
        else:
            """continue with the last record viewed"""

            cursor_order: str = cursor_payload["order"]
            created_at: str = datetime.fromisoformat(cursor_payload["created_at"])

            if cursor_order == "desc":
                cursor_order = desc(*sort_fields)
                created_at_filter = model.created_at < created_at
            else:
                cursor_order = asc(*sort_fields)
                created_at_filter = model.created_at > created_at

            stmt = (
                select(model)
                .where(*filter_conditions, created_at_filter)
                .order_by(cursor_order)
                .limit(limit + 1)
            )

        res = await self._session.execute(stmt)
        records = res.scalars().all()

        has_more: bool = len(records)

        payload: dict = {
            "created_at": records[:limit].created_at.isoformat(),
            "order": cursor_payload["order"],
        }
        next_cursor: str = await encode_cursor(payload)

        return {"data": records[:limit], "cursor": next_cursor if has_more else None}

    @staticmethod
    @abstractmethod
    def _entity_to_model(entity: Entity) -> SqlalchemyModel:
        raise NotImplementedError("Subclasses must implement _entity_to_model method")

    @staticmethod
    @abstractmethod
    def _model_to_entity(model: SqlalchemyModel) -> Entity:
        raise NotImplementedError("Subclasses must implement _model_to_entity method")

    @abstractmethod
    def _get_filters(self, **filters) -> list[Any]:
        return []

    @abstractmethod
    def _get_sort_fields(self, sort: str) -> list[Any]:
        return []
