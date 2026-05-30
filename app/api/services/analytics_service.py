import asyncio
import sentry_sdk
from uuid import UUID
import sentry_sdk.logger as sentry_logger


from app.api.models.user import User
from app.core.exceptions import ServerError
from app.api.schemas.analytics import AnalyticsResponse
from app.api.repo.analytics_repo import AnalyticsRepository


class AnalyticsService:
    def __init__(self, analytics_repo: AnalyticsRepository):
        self._analytics_repo = analytics_repo

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

            most_clicked_url, _ = most_clicked
            least_clicked_url, _ = least_clicked

            avg_clicks_per_day: dict = {d: c for d, c in avg_clicks}
            total_clicks_per_url: dict = {u: c for u, c in total_clicks_per_url}

            sentry_logger.info("User {email} url analytics retrieved", email=user_email)

            return AnalyticsResponse(
                total_urls=total_urls if total_urls else 0,
                total_clicks=total_clicks if total_clicks else 0,
                most_clicked_url=most_clicked_url,
                least_clicked_url=least_clicked_url,
                avg_clicks_per_day=avg_clicks_per_day,
                recently_created_urls=recent_urls,
                total_clicks_per_url=total_clicks_per_url,
            )
        except Exception as e:
            sentry_sdk.capture_exception(e)
            sentry_logger.error(
                "Error occured while retrieving url analytics for user {email}",
                email=user_email,
            )
            raise ServerError() from e
