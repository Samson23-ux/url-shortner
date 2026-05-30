from typing import Annotated
from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse


from app.api.schemas.response import SuccessResponse
from app.api.schemas.url import ShortenUrl, UrlUpdate, UrlResponse
from app.dependencies import (
    UrlServiceDep,
    CurrentActiveUser,
    UnitOfWorkRepo,
)


router = APIRouter()


@router.post(
    "/shorten",
    status_code=201,
    description=(
        "Shorten a long url. Shortened url expire after 7 days"
        "An optional unique custom slug can be provided based on preferences"
    ),
    response_model=SuccessResponse[UrlResponse],
)
async def shorten_url(
    request: Request,
    uow: UnitOfWorkRepo,
    url_payload: ShortenUrl,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    url: UrlResponse = await url_service.shorten_url(uow, curr_user, url_payload)
    return SuccessResponse(message="Shortened url created successfully", data=url)


@router.get(
    "/shorten/{slug}",
    status_code=302,
    description="Redirects to the original url associated with the shortened url",
    response_class=RedirectResponse,
)
async def redirect_to_url(
    request: Request,
    slug: str,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    url: str = await url_service.redirect_to_url(curr_user, slug)
    return RedirectResponse(url)


@router.get(
    "/shorten/all",
    status_code=200,
    description="Get all shortened url",
    response_model=SuccessResponse[list[UrlResponse]],
)
async def get_all_url(
    request: Request,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
    sort: Annotated[
        str, Query(description="Sort by created_at, last_updated_at, expire_at")
    ] = None,
    order: Annotated[str, Query(description="Order in asc or desc")] = None,
    cursor: Annotated[str, Query()] = None,
    limit: Annotated[int, Query()] = 10,
):
    urls: list[UrlResponse] = await url_service.get_all_urls(
        curr_user, sort, order, cursor, limit
    )
    return SuccessResponse(message="Urls retrieved successfully", data=urls)


@router.patch(
    "/shorten/{slug}",
    status_code=200,
    description="Update the original url associated to a shortened url",
    response_class=SuccessResponse[UrlResponse],
)
async def update_url(
    request: Request,
    slug: str,
    url_update: UrlUpdate,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    url: UrlResponse = await url_service.update_url(curr_user, url_update, slug)
    return SuccessResponse(message="Url updated successfully", data=url)


@router.delete(
    "/shorten/{slug}", status_code=204, description="Delete url record"
)
async def delete_url(
    request: Request,
    slug: str,
    url_service: UrlServiceDep,
    curr_user: CurrentActiveUser,
):
    await url_service.delete_url(curr_user, slug)
