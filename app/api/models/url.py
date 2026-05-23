import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String,
    text,
    UUID,
    DateTime,
    PrimaryKeyConstraint,
    Index,
    ForeignKey,
)


from app.api.models.base import Base


class Url(Base):
    __tablename__ = "urls"

    id: Mapped[uuid.UUID] = mapped_column(UUID, default=text("uuid_generate_v7()"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", name="urls_user_id_fk", ondelete="CASCADE")
    )
    original_url: Mapped[str] = mapped_column(String, unique=True)
    shortened_url: Mapped[str] = mapped_column(String, unique=True)
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expire_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        PrimaryKeyConstraint("id", name="urls_pk"),
        Index("idx_urls_user_id", user_id),
        Index("idx_urls_original_url", original_url),
        Index("idx_urls_shortened_url", shortened_url),
    )
