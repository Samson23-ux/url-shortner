from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse


from app.api.schemas.response import SuccessResponse
from app.api.schemas.url import ShortenUrl, UrlUpdate, UrlResponse
from app.dependencies import (
    UrlServiceDep,
    # UserServiceDep,
    CurrentActiveUser,
)


router = APIRouter()


@router.post(
    "/shorten",
    status_code=201,
    description=(
        "Shorten a long url. Shortened url expire after 7 days"
        "An optional unique custom slug can be provided based on preferences"
    ),
    response_model=SuccessResponse[UrlResponse]
)
async def shorten_url(
    request: Request,
    url_payload: ShortenUrl,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    pass


@router.get(
    "/shorten/{shortened_url}",
    status_code=302,
    description="Redirects to the original url associated with the shortened url",
    response_class=RedirectResponse
)
async def get_url(
    request: Request,
    shortened_url: str,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    pass


@router.get(
    "/shorten/all",
    status_code=200,
    description="Get all shortened url",
    response_model=SuccessResponse[UrlResponse]
)
async def get_all_url(
    request: Request,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    pass


@router.patch(
    "/shorten/{shortened_url}",
    status_code=200,
    description="Update the original url associated to a shortened url",
    response_class=SuccessResponse[UrlResponse]
)
async def update_url(
    request: Request,
    shortened_url: str,
    url_update: UrlUpdate,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    pass


@router.delete(
    "/shorten/{shortened_url}",
    status_code=204,
    description="Delete url record"
)
async def delete_url(
    request: Request,
    shortened_url: str,
    url_update: UrlUpdate,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    pass
