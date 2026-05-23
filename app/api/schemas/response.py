from pydantic import BaseModel
from typing import TypeVar, Generic


T = TypeVar("T", bound=BaseModel)


class SuccessResponse(BaseModel, Generic[T]):
    status: str = "success"
    message: str
    data: T | list[T]
