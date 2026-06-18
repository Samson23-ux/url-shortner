from uuid import UUID
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone, timedelta, date


from app.api.models.url import Url
from app.api.models.url_stat import UrlStat
from app.api.repo.base import BaseRepository
from app.api.schemas.analytics import AnalyticsBase, UrlStatInDB


class AnalyticsRepository(BaseRepository[AnalyticsBase, UrlStat]):
    model = UrlStat

    @staticmethod
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
        res = await self._async_session.execute(stmt)
        return res.scalar()

    async def get_total_clicks(self, user_id: UUID) -> int | None:
        stmt = (
            select(func.sum(self.model.clicks))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
        )
        res = await self._async_session.execute(stmt)
        return res.scalar()

    async def get_most_clicked_url(self, user_id: UUID):
        subquery_stmt = (
            select(func.max(self.model.clicks).label("max_clicks"))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
            .subquery()
        )

        stmt = (
            select(Url.shortened_url, self.model.clicks)
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(
                Url.user_id == user_id,
                self.model.clicks == subquery_stmt.c.max_clicks
            )
        )

        res = await self._async_session.execute(stmt)
        return res.all()

    async def get_least_clicked_url(self, user_id: UUID):
        subquery_stmt = (
            select(func.min(self.model.clicks).label("min_clicks"))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
            .subquery()
        )

        stmt = (
            select(Url.shortened_url, self.model.clicks)
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(
                Url.user_id == user_id,
                self.model.clicks == subquery_stmt.c.min_clicks
            )
        )

        res = await self._async_session.execute(stmt)
        return res.all()

    async def get_avg_clicks_per_day(self, user_id: UUID):
        stmt = (
            select(self.model.date, func.avg(self.model.clicks))
            .select_from(Url)
            .join(self.model, Url.id == self.model.url_id)
            .where(Url.user_id == user_id)
            .group_by(self.model.date)
        )

        res = await self._async_session.execute(stmt)
        return res.all()

    async def get_recently_created_urls(self, user_id: UUID):
        recent: datetime = datetime.now(timezone.utc) - timedelta(days=3)

        stmt = select(Url.shortened_url).where(
            Url.user_id == user_id, Url.created_at >= recent
        )
        res = await self._async_session.execute(stmt)

        return res.all()

    async def get_total_clicks_per_url(self, user_id: UUID, day: str):
        filter_mappings: dict = {
            "today": self.model.date == date.today(),
            "last seven days": self.model.date
            >= date.today() - timedelta(days=7),
            "last fourteen days": self.model.date
            >= date.today() - timedelta(days=14),
        }
        stmt = (
            select(Url.shortened_url, func.sum(self.model.clicks))
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

        res = await self._async_session.execute(stmt)
        return res.all()

    def upsert_click(self, entity: UrlStatInDB):
        stmt = insert(self.model).values([entity.model_dump()])
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["url_id", "date"], set_={"clicks": stmt.excluded.clicks}
        )
        self._sync_session.execute(upsert_stmt)
