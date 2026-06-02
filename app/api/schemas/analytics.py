from uuid import UUID
from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class AnalyticsBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class UrlStatInDB(AnalyticsBase):
    url_id: UUID
    clicks: int
    date: date


class AnalyticsOut(AnalyticsBase):
    total_urls: int = 0
    total_clicks: int = 0
    most_clicked_url: Optional[str] = None
    least_clicked_url: Optional[str] = None
    avg_clicks_per_day: dict[date, int]
    recently_created_urls: list[str] = []
    total_clicks_per_url: dict[str, int] = {}


class AnalyticsResponse(AnalyticsOut):
    pass
