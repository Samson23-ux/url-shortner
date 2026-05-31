from uuid import UUID
from typing import Any
from sqlalchemy import select, func, Sequence
from datetime import datetime, timezone, timedelta


from app.api.models.url import Url
from app.api.models.url_stat import UrlStat
from app.api.repo.base import BaseRepository
from app.api.schemas.analytics import AnalyticsBase


class AnalyticsRepository(BaseRepository[AnalyticsBase, UrlStat]):
    model = UrlStat

    def _entity_to_model(entity: AnalyticsBase) -> model:
        return UrlStat(**entity.model_dump())

    def _model_to_entity(model: UrlStat, entity: AnalyticsBase) -> AnalyticsBase:
        return entity.model_validate(model)

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "url_id" in filters:
            filter_conditions.append(self.model.url_id == filters["url_id"])

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        pass

    async def get_total_urls(self, user_id: UUID) -> int | None:
        stmt = select(func.count(Url.shortened_url)).where(Url.user_id == user_id)
        res = await self._session.execute(stmt)
        return res.scalar()

    async def get_total_clicks(self, user_id: UUID) -> int | None:
        stmt = (
            select(func.count(self.model.clicks))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
        )
        res = await self._session.execute(stmt)
        return res.scalar()

    async def get_most_clicked_url(self, user_id: UUID):
        stmt = (
            select(Url.shortened_url, func.max(self.model.clicks))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
            # .group_by(Url.shortened_url)
        )

        res = await self._session.execute(stmt)
        return res.scalar()

    async def get_least_clicked_url(self, user_id: UUID):
        stmt = (
            select(Url.shortened_url, func.min(self.model.clicks))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
            # .group_by(Url.shortened_url)
        )

        res = await self._session.execute(stmt)
        return res.scalar()

    async def get_avg_clicks_per_day(self, user_id: UUID):
        stmt = (
            select(self.model.date, func.avg(self.model.clicks))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
            .group_by(self.model.date)
        )

        res = await self._session.execute(stmt)
        return res.scalar()

    async def get_recently_created_urls(self, user_id: UUID) -> Sequence[str]:
        recent: datetime = datetime.now(timezone.utc) - timedelta(days=3)

        stmt = select(Url.shortened_url).where(
            Url.user_id == user_id, Url.created_at >= recent
        )
        res = await self._session.execute(stmt)

        return res.scalars().all()

    async def get_total_clicks_per_url(self, user_id: UUID, day: str):
        filter_mappings: dict = {
            "today": Url.created_at >= datetime.now(timezone.utc) - timedelta(days=1),
            "last seven days": Url.created_at
            >= datetime.now(timezone.utc) - timedelta(days=7),
            "last fourteen days": Url.created_at
            >= datetime.now(timezone.utc) - timedelta(days=14),
        }
        stmt = (
            select(Url.shortened_url, self.model.clicks)
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
            .group_by(Url.shortened_url)
        )

        if day:
            day_filter = filter_mappings.get(
                day, Url.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
            )
            stmt = stmt.where(day_filter)

        res = await self._session.execute(stmt)
        return res.scalar()
