from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, utcnow

# Privacy: no IP addresses, no raw User-Agent strings, no account data. The session id is a
# random UUID the browser generates and keeps in localStorage.


class MovieView(Base):
    """One play of a movie by an anonymous session; watch_duration is updated by progress pings."""

    __tablename__ = "movie_views"
    __table_args__ = (
        Index("ix_movie_views_movie_viewed", "movie_id", "viewed_at"),
        Index("ix_movie_views_session_movie", "anonymous_session_id", "movie_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"))
    anonymous_session_id: Mapped[str] = mapped_column(String(64))
    device_category: Mapped[str] = mapped_column(String(10), default="desktop")
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    watch_duration: Mapped[int] = mapped_column(Integer, default=0)  # seconds


class SiteEvent(Base):
    """Anonymous visit / page-view events, used for traffic trends and device breakdown."""

    __tablename__ = "site_events"
    __table_args__ = (Index("ix_site_events_type_created", "event_type", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(20))  # visit | page_view
    path: Mapped[str | None] = mapped_column(String(300))
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id", ondelete="SET NULL"))
    anonymous_session_id: Mapped[str] = mapped_column(String(64), index=True)
    device_category: Mapped[str] = mapped_column(String(10), default="desktop")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
