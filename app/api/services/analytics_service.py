from app.api.repo.analytics import AnalyticsRepository


class AnalyticsService:
    def __init__(self, analytics_repo: AnalyticsRepository):
        self._analytics_repo = analytics_repo
