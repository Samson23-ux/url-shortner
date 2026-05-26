import re
from uuid import UUID
from typing import Optional
from datetime import datetime
from typing_extensions import Self
from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.core.exceptions import InvalidSlugError
from app.api.schemas.slug import SLUG_PATTERN, RESERVED_WORDS


class UrlBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    original_url: str


class UrlInDb(UrlBase):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    shortened_url: str
    last_updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    expire_at: datetime


class ShortenUrl(UrlBase):
    model_config = ConfigDict(str_to_lower=True)

    slug: str = Field(default=None, min_length=3, max_length=20)

    @model_validator(mode="after")
    def validate_slug(self) -> Self:
        is_valid = bool(SLUG_PATTERN.match(self.slug))

        if self.slug in RESERVED_WORDS or not is_valid:
            raise InvalidSlugError(slug=self.slug)
        return self


class UrlUpdate(BaseModel):
    new_original_url: str
    

class UrlResponse(BaseModel):
    id: UUID
    user_id: UUID
    shortened_url: str
    last_updated_at: Optional[datetime] = None
    created_at: datetime
    expire_at: datetime
