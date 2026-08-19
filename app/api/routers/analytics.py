from typing import Annotated
from fastapi import APIRouter, Request, Query, Depends


from app.limiter import _limiter_handler
from app.core.config import get_settings
from app.api.schemas.response import SuccessResponse
from app.api.schemas.analytics import AnalyticsResponse
from app.dependencies import (
    CurrentActiveUser,
    AnalyticsServiceDep,
)

router = APIRouter()


ANALYTICS_LIMIT_KEY = get_settings().ANALYTICS_LIMIT_KEY


@router.get(
    "/analytics",
    status_code=200,
    description="Get account analytics",
    response_model=SuccessResponse[AnalyticsResponse],
    dependencies=[
        Depends(_limiter_handler(key=ANALYTICS_LIMIT_KEY, limit=5, unit="minutes"))
    ],
)
async def get_analytics(
    request: Request,
    analytics_service: AnalyticsServiceDep,
    curr_user: CurrentActiveUser,
    day: Annotated[
        str,
        Query(
            description=(
                "Filter total clicks per url for today, last seven days,"
                "and last fourteen days"
            )
        ),
    ] = None,
):
    analytics: AnalyticsResponse = await analytics_service.get_analytics(curr_user, day)
    return SuccessResponse(message="Analytics retrieved successfully", data=analytics)
