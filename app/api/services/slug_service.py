from app.api.repo.slug_repo import SlugRepository


class SlugService:
    def __init__(self, slug_repo: SlugRepository):
        self._slug_repo = slug_repo
