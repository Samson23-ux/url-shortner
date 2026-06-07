import re
from uuid import UUID
from datetime import datetime
from typing_extensions import Self
from pydantic import BaseModel, ConfigDict, model_validator


from app.core.exceptions import InvalidSlugError


RESERVED_WORDS = ["api", "dashboard", "admin"]
SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class SlugBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    custom_slug: str


class SlugCreate(SlugBase):
    @model_validator(mode="after")
    def validate_slug(self) -> Self:
        is_valid = bool(SLUG_PATTERN.match(self.custom_slug))

        if self.custom_slug in RESERVED_WORDS or not is_valid:
            raise InvalidSlugError(slug=self.custom_slug)
        return self


class SlugUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    new_custom_slug: str

    @model_validator(mode="after")
    def validate_slug(self) -> Self:
        is_valid = bool(SLUG_PATTERN.match(self.new_custom_slug))

        if self.new_custom_slug in RESERVED_WORDS or not is_valid:
            raise InvalidSlugError(slug=self.new_custom_slug)
        return self


class SlugResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    custom_slug: str
    created_at: datetime
