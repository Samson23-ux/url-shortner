from uuid import UUID
from typing import Optional
from datetime import datetime
from typing_extensions import Self
from pydantic import BaseModel, ConfigDict, Field, model_validator


from app.core.exceptions import InvalidSlugError
from app.api.schemas.slug import SLUG_PATTERN, RESERVED_WORDS


class UrlBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    original_url: str


class ShortenUrl(UrlBase):
    model_config = ConfigDict(str_to_lower=True)

    custom_slug: str = Field(default=None, min_length=3, max_length=20)

    @model_validator(mode="after")
    def validate_slug(self) -> Self:
        if self.custom_slug:
            is_valid = bool(SLUG_PATTERN.match(self.custom_slug))

            if self.custom_slug in RESERVED_WORDS or not is_valid:
                raise InvalidSlugError(slug=self.custom_slug)
        return self


class UrlUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    new_original_url: str


class UrlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    slug_id: UUID
    original_url: str
    shortened_url: str
    last_updated_at: Optional[datetime] = None
    created_at: datetime
    expire_at: datetime
