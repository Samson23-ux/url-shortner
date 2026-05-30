from typing import Annotated
from fastapi import APIRouter, Request, Query


from app.api.schemas.response import SuccessResponse
from app.api.schemas.slug import SlugCreate, SlugUpdate, SlugResponse
from app.dependencies import (
    SlugService,
    CurrentActiveUser,
)


router = APIRouter()


@router.post(
    "/slugs",
    status_code=201,
    description="Create a custom slug",
    response_model=SuccessResponse[SlugResponse]
)
async def create_slug(
    request: Request,
    slug_payload: SlugCreate,
    slug_service: SlugService,
    curr_user: CurrentActiveUser,
):
    slug: SlugResponse = await slug_service.create_slug(curr_user, slug_payload)
    return SuccessResponse(message="Slug created successfully", data=slug)


@router.get(
    "/slugs",
    status_code=200,
    description="Get all craeted slug",
    response_model=SuccessResponse[list[SlugResponse]]
)
async def get_all_slug(
    request: Request,
    slug_service: SlugService,
    curr_user: CurrentActiveUser,
    sort: Annotated[
        str, Query(description="Sort by created_at")
    ] = None,
    order: Annotated[str, Query(description="Order in asc or desc")] = None,
    cursor: Annotated[str, Query()] = None,
    limit: Annotated[int, Query()] = 10,
):
    slugs: list[SlugResponse] = await slug_service.get_all_slugs(
        curr_user, sort, order, cursor, limit
    )
    return SuccessResponse(message="Slugs retrieved successfully", data=slugs)


@router.get(
    "/slugs/{slug}",
    status_code=200,
    description="Get created slug",
    response_model=SuccessResponse[SlugResponse]
)
async def get_slug(
    request: Request,
    slug: str,
    slug_service: SlugService,
    curr_user: CurrentActiveUser,
):
    slug: SlugResponse = await slug_service.get_slug(curr_user, slug)
    return SuccessResponse(message="Slug retrived successfully", data=slug)


@router.patch(
    "/slugs/{slug}",
    status_code=200,
    description="Update existing slug",
    response_model=SuccessResponse[SlugResponse]
)
async def update_slug(
    request: Request,
    slug: str,
    slug_payload: SlugUpdate,
    slug_service: SlugService,
    curr_user: CurrentActiveUser,
):
    slug: SlugResponse = await slug_service.update_slug(curr_user, slug_payload, slug)
    return SuccessResponse(message="Slug updated successfully", data=slug)


@router.delete(
    "/slugs/{slug}",
    status_code=204,
    description="Delete existing slug",
)
async def delete_slug(
    request: Request,
    slug: str,
    slug_service: SlugService,
    curr_user: CurrentActiveUser,
):
    await slug_service.delete_slug(curr_user, slug)
