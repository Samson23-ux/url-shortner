from fastapi import APIRouter

from app.api.routers import analytics, auth, slug, url
from app.core.config import get_settings

router = APIRouter(prefix=get_settings().API_PREFIX)


router.include_router(url.router, tags=["Url"])
router.include_router(auth.router, tags=["Auth"])
router.include_router(slug.router, tags=["Slug"])
router.include_router(analytics.router, tags=["Analytics"])
