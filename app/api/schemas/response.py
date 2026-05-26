from pydantic import BaseModel
from typing import TypeVar, Generic, Optional


T = TypeVar("T", bound=BaseModel)


class SuccessResponse(BaseModel, Generic[T]):
    status: str = "success"
    message: str
    data: Optional[T | list[T]] = None
