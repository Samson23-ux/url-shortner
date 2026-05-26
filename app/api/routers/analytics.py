from fastapi import APIRouter, Request


from app.api.schemas.response import SuccessResponse
from app.api.schemas.analytics import AnalyticsResponse
from app.dependencies import (
    # UserServiceDep,
    CurrentActiveUser,
    AnalyticsServiceDep,
)


router = APIRouter()


@router.get(
    "/analytics",
    status_code=200,
    description="Get account analytics",
    response_model=SuccessResponse[AnalyticsResponse]
)
async def get_analytics(
    request: Request,
    analytics_service: AnalyticsServiceDep,
    curr_user: CurrentActiveUser,
):
    pass
