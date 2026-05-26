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


class Slug(Base):
    __tablename__ = "slugs"

    id: Mapped[uuid.UUID] = mapped_column(UUID, server_default=text("uuid_generate_v7()"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("users.id", name="slugs_user_id_fk", ondelete="CASCADE")
    )
    custom_slug: Mapped[str] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        PrimaryKeyConstraint("id", name="slugs_pk"),
        Index("idx_slugs_user_id", user_id),
        Index("idx_urls_custom_slug", custom_slug),
    )
