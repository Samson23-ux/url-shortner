from fastapi import APIRouter, Request


from app.api.schemas.response import SuccessResponse
from app.api.schemas.slug import SlugCreate, SlugUpdate, SlugResponse
from app.dependencies import (
    SlugService,
    # UserServiceDep,
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
    pass


@router.get(
    "/slugs",
    status_code=200,
    description="Get all craeted slug",
    response_model=SuccessResponse[SlugResponse]
)
async def get_all_slug(
    request: Request,
    slug_service: SlugService,
    curr_user: CurrentActiveUser,
):
    pass


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
    pass


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
    pass


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
    pass
