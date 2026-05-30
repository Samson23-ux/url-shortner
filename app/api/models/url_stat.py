import uuid
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    String,
    text,
    UUID,
    ForeignKey,
    Date
)


from app.api.models.base import Base


class UrlStat(Base):
    __tablename__ = "url_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID, server_default=text("uuid_generate_v7()"))
    url_id: Mapped[str] = mapped_column(
        String, ForeignKey("urls.id", name="urls_urls_id_fk", ondelete="CASCADE")
    )
    clicks: Mapped[str] = mapped_column(String)
    date: Mapped[date] = mapped_column(Date)
