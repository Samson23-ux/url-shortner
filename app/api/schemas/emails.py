from uuid import UUID
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EmailBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class EmailInDB(EmailBase):
    id: UUID
    processed_emails: dict
    created_at: Optional[datetime] = None
