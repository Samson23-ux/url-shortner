from uuid import UUID
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


from app.api.models.user import UserType


class UserBase(BaseModel):
    type: UserType
    is_active: bool = False
    is_verified: bool = False
    delete_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GoogleUser(UserBase):
    google_id: str
    google_email: EmailStr


class EmailUser(UserBase):
    email: EmailStr


class UserInDB(UserBase, GoogleUser, EmailUser):
    hashed_password: Optional[str] = None


class GoogleUserResponse(GoogleUser):
    id: UUID


class EmailUserResponse(EmailUser):
    id: UUID

