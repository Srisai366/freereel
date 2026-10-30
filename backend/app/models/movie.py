from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.taxonomy import Genre, Language


class MovieStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"


movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True),
    Column("genre_id", ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class Movie(Base):
    __tablename__ = "movies"
    __table_args__ = (
        Index("ix_movies_status_published_at", "status", "published_at"),
        Index("ix_movies_status_featured", "status", "featured"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    release_year: Mapped[int | None] = mapped_column(Integer, index=True)
    language_id: Mapped[int | None] = mapped_column(
        ForeignKey("languages.id", ondelete="SET NULL"), index=True
    )
    duration: Mapped[int | None] = mapped_column(Integer)  # seconds
    director: Mapped[str | None] = mapped_column(String(200))
    cast_members: Mapped[list[str]] = mapped_column(JSON, default=list)
    # Rights basis shown on the details page, e.g. "Public domain (US)" or "CC BY 3.0".
    license: Mapped[str | None] = mapped_column(String(200))

    poster_url: Mapped[str | None] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    video_url: Mapped[str | None] = mapped_column(String(500))
    video_format: Mapped[str | None] = mapped_column(String(20))  # "hls" or "mp4"
    video_quality: Mapped[str | None] = mapped_column(String(100))  # comma list, e.g. "360p,720p"

    status: Mapped[str] = mapped_column(String(20), default=MovieStatus.DRAFT, index=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)

    # Internal storage keys, used to clean up objects; never exposed publicly.
    poster_key: Mapped[str | None] = mapped_column(String(500))
    original_key: Mapped[str | None] = mapped_column(String(500))
    hls_prefix: Mapped[str | None] = mapped_column(String(500))
    storage_bytes: Mapped[int] = mapped_column(BigInteger, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    language: Mapped[Language | None] = relationship(lazy="joined")
    genres: Mapped[list[Genre]] = relationship(
        secondary=movie_genres, lazy="selectin", order_by=Genre.name
    )

    @property
    def quality_list(self) -> list[str]:
        return [q for q in (self.video_quality or "").split(",") if q]
