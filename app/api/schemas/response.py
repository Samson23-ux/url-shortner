from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class SuccessResponse[T: BaseModel](BaseModel):
    status: str = "success"
    message: str
    data: T | list[T] | None = None


class AllSuccessResponse(SuccessResponse):
    cursor: str | None
