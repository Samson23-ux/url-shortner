from typing import Annotated
from fastapi import APIRouter, Request, Query


from app.api.schemas.response import SuccessResponse
from app.api.schemas.analytics import AnalyticsResponse
from app.dependencies import (
    CurrentActiveUser,
    AnalyticsServiceDep,
)


router = APIRouter()


@router.get(
    "/analytics",
    status_code=200,
    description="Get account analytics",
    response_model=SuccessResponse[AnalyticsResponse],
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
