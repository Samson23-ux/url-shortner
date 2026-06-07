import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String,
    Boolean,
    text,
    UUID,
    DateTime,
    PrimaryKeyConstraint,
    Index,
    Enum,
)


from app.api.models.base import Base


class UserType(str, enum.Enum):
    EMAIL = "email"
    GOOGLE = "google"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID, server_default=text("uuid_generate_v7()")
    )
    google_id: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, unique=True)
    google_email: Mapped[str | None] = mapped_column(String, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String)
    type: Mapped[UserType] = mapped_column(
        Enum(UserType, values_callable=lambda e: [m.value for m in e])
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deactivated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    five_days_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seven_days_before: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        PrimaryKeyConstraint("id", name="users_pk"),
        Index("idx_users_email", email),
        Index("idx_users_google_id", google_id),
    )
