from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.api.models.user import UserType


class UserBase(BaseModel):
    type: UserType
    is_active: bool = False
    is_verified: bool = False
    is_deactivated: bool = False
    delete_at: datetime | None = None
    created_at: datetime | None = None
    five_days_before: datetime | None = None
    seven_days_before: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GoogleUser(UserBase):
    google_id: str | None = None
    google_email: EmailStr | None = None


class EmailUser(UserBase):
    email: EmailStr | None = None


class UserInDB(GoogleUser, EmailUser):
    hashed_password: str | None = None


class GoogleUserResponse(GoogleUser):
    id: UUID


class EmailUserResponse(EmailUser):
    id: UUID


class CachedUser(BaseModel):
    id: UUID
    type: UserType
    email: str | None = None
    google_email: str | None = None
    is_active: bool
    is_verified: bool
    is_deactivated: bool

    model_config = ConfigDict(from_attributes=True)
