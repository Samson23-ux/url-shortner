from app.api.repo.url_repo import UrlRepository


class UrlService:
    def __init__(self, url_repo: UrlRepository):
        self._url_repo = url_repo
