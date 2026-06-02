import uuid
from datetime import date
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    text,
    UUID,
    ForeignKey,
    Date,
    Integer,
    PrimaryKeyConstraint,
    Index,
    UniqueConstraint
)


from app.api.models.base import Base


class UrlStat(Base):
    __tablename__ = "url_stats"

    id: Mapped[uuid.UUID] = mapped_column(UUID, server_default=text("uuid_generate_v7()"))
    url_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("urls.id", name="urls_urls_id_fk", ondelete="CASCADE")
    )
    clicks: Mapped[int] = mapped_column(Integer)
    date: Mapped[date] = mapped_column(Date)


    __table_args__ = (
        PrimaryKeyConstraint("id", name="url_stats_pk"),
        Index("idx_urls_url_id", url_id),
        UniqueConstraint(url_id, date, name="url_stats_unique_key")
    )
