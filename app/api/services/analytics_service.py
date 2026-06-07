import asyncio
import sentry_sdk
from uuid import UUID
import sentry_sdk.logger as sentry_logger


from app.api.models.user import User
from app.core.exceptions import ServerError
from app.api.repo.redis_repo import RedisRepository
from app.api.repo.analytics_repo import AnalyticsRepository
from app.api.schemas.analytics import AnalyticsResponse, UrlStatInDB


class AnalyticsService:
    def __init__(
        self, analytics_repo: AnalyticsRepository, redis_repo: RedisRepository
    ):
        self._analytics_repo = analytics_repo
        self._redis_repo = redis_repo

    async def get_analytics(self, curr_user: User, day: str | None):
        if curr_user.type == "email":
            user_email: str = curr_user.email
        else:
            user_email: str = curr_user.google_email

        try:
            user_id: UUID = curr_user.id
            (
                total_urls,
                total_clicks,
                most_clicked,
                least_clicked,
                avg_clicks,
                recent_urls,
                total_clicks_per_url,
            ) = await asyncio.gather(
                self._analytics_repo.get_total_urls(user_id),
                self._analytics_repo.get_total_clicks(user_id),
                self._analytics_repo.get_most_clicked_url(user_id),
                self._analytics_repo.get_least_clicked_url(user_id),
                self._analytics_repo.get_avg_clicks_per_day(user_id),
                self._analytics_repo.get_recently_created_urls(user_id),
                self._analytics_repo.get_total_clicks_per_url(user_id, day),
            )

            most_clicked_url, most_clicks = most_clicked[0]
            least_clicked_url, least_clicks = least_clicked[0]

            avg_clicks_per_day: dict = {d.isoformat(): int(c) for d, c in avg_clicks}
            recently_created_urls: list = [u for u, in recent_urls]
            total_clicks_per_url: dict = {u: int(c) for u, c in total_clicks_per_url}

            sentry_logger.info("User {email} url analytics retrieved", email=user_email)

            analytics: AnalyticsResponse = AnalyticsResponse(
                total_urls=total_urls if total_urls else 0,
                total_clicks=total_clicks if total_clicks else 0,
                most_clicked_url=most_clicked_url if most_clicks > 0 else None,
                least_clicked_url=least_clicked_url if least_clicks > 0 else None,
                avg_clicks_per_day=avg_clicks_per_day,
                recently_created_urls=recently_created_urls,
                total_clicks_per_url=total_clicks_per_url,
            )
            return analytics
        except Exception as e:
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving url analytics for user {email}",
                email=user_email,
            )
            raise ServerError() from e

    def get_clicks_keys(self, key):
        return self._redis_repo.get_clicks_keys(key)

    def get_clicks(self, key):
        return self._redis_repo.get_clicks(key)

    def upsert_click(self, url_stat: UrlStatInDB):
        self._analytics_repo.upsert_click(url_stat)
        self._analytics_repo.sync_commit()
