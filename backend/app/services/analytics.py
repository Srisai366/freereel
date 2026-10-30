import re
from datetime import timedelta

from sqlalchemy import desc, func, select, update
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import (
    Advertisement,
    Genre,
    JobStatus,
    Language,
    Movie,
    MovieStatus,
    MovieView,
    ProcessingJob,
    SiteEvent,
    movie_genres,
)
from app.schemas.admin import EventIn

_BOT = re.compile(r"bot|crawl|spider|slurp|headless|lighthouse|preview|curl|wget|python-", re.I)
_TABLET = re.compile(r"ipad|tablet|kindle|silk|playbook|android(?!.*mobile)", re.I)
_MOBILE = re.compile(r"mobi|iphone|ipod|android|blackberry|opera mini|iemobile", re.I)

PLAY_DEDUP_WINDOW = timedelta(minutes=30)
PROGRESS_WINDOW = timedelta(hours=12)


def device_category(user_agent: str | None) -> str | None:
    """Coarse device class from the User-Agent; None for bots. The UA itself is never stored."""
    ua = user_agent or ""
    if not ua or _BOT.search(ua):
        return None
    if _TABLET.search(ua):
        return "tablet"
    if _MOBILE.search(ua):
        return "mobile"
    return "desktop"


def record_event(db: Session, event: EventIn, device: str) -> None:
    now = utcnow()
    if event.type in ("visit", "page_view"):
        db.add(
            SiteEvent(
                event_type=event.type,
                path=event.path,
                movie_id=event.movie_id if _is_public_movie(db, event.movie_id) else None,
                anonymous_session_id=event.session_id,
                device_category=device,
            )
        )
        db.commit()
        return

    movie = _public_movie(db, event.movie_id)
    if movie is None:
        return
    recent = db.scalar(
        select(MovieView)
        .where(
            MovieView.movie_id == movie.id,
            MovieView.anonymous_session_id == event.session_id,
            MovieView.viewed_at
            >= now - (PLAY_DEDUP_WINDOW if event.type == "play" else PROGRESS_WINDOW),
        )
        .order_by(MovieView.id.desc())
        .limit(1)
    )
    if event.type == "play":
        if recent is None:
            db.add(
                MovieView(
                    movie_id=movie.id, anonymous_session_id=event.session_id, device_category=device
                )
            )
            db.commit()
        return

    # progress
    if recent is not None and event.watch_seconds is not None:
        seconds = event.watch_seconds
        if movie.duration:
            seconds = min(seconds, movie.duration)
        if seconds > recent.watch_duration:
            recent.watch_duration = seconds
            db.commit()


def _public_movie(db: Session, movie_id: int | None) -> Movie | None:
    if movie_id is None:
        return None
    movie = db.get(Movie, movie_id)
    return movie if movie and movie.status == MovieStatus.PUBLISHED else None


def _is_public_movie(db: Session, movie_id: int | None) -> bool:
    return _public_movie(db, movie_id) is not None


def count_ad(db: Session, ad_id: int, field: str) -> bool:
    column = getattr(Advertisement, field)
    result = db.execute(
        update(Advertisement)
        .where(Advertisement.id == ad_id, Advertisement.status == "active")
        .values({field: column + 1})
    )
    db.commit()
    return result.rowcount > 0


def dashboard(db: Session, days: int) -> dict:
    since = utcnow() - timedelta(days=days)

    by_status = dict(db.execute(select(Movie.status, func.count()).group_by(Movie.status)).all())
    jobs_by_status = dict(
        db.execute(select(ProcessingJob.status, func.count()).group_by(ProcessingJob.status)).all()
    )

    period_views = select(MovieView).where(MovieView.viewed_at >= since).subquery()
    period_visits = (
        select(SiteEvent)
        .where(SiteEvent.event_type == "visit", SiteEvent.created_at >= since)
        .subquery()
    )

    most_watched = db.execute(
        select(
            Movie.id,
            Movie.title,
            Movie.slug,
            func.count(MovieView.id).label("views"),
            func.coalesce(func.sum(MovieView.watch_duration), 0).label("watch_seconds"),
        )
        .join(MovieView, MovieView.movie_id == Movie.id)
        .group_by(Movie.id, Movie.title, Movie.slug)
        .order_by(desc("views"))
        .limit(10)
    ).all()

    popular_genres = db.execute(
        select(Genre.name, func.count(period_views.c.id).label("views"))
        .join(movie_genres, movie_genres.c.genre_id == Genre.id)
        .join(period_views, period_views.c.movie_id == movie_genres.c.movie_id)
        .group_by(Genre.name)
        .order_by(desc("views"))
        .limit(10)
    ).all()

    popular_languages = db.execute(
        select(Language.name, func.count(period_views.c.id).label("views"))
        .join(Movie, Movie.language_id == Language.id)
        .join(period_views, period_views.c.movie_id == Movie.id)
        .group_by(Language.name)
        .order_by(desc("views"))
        .limit(10)
    ).all()

    devices = db.execute(
        select(period_visits.c.device_category, func.count()).group_by(
            period_visits.c.device_category
        )
    ).all()

    visit_day = func.date(period_visits.c.created_at)
    visits_by_day = dict(db.execute(select(visit_day, func.count()).group_by(visit_day)).all())
    view_day = func.date(period_views.c.viewed_at)
    views_by_day = dict(db.execute(select(view_day, func.count()).group_by(view_day)).all())
    trend = [
        {"date": str(day), "visits": visits_by_day.get(day, 0), "plays": views_by_day.get(day, 0)}
        for day in sorted(set(visits_by_day) | set(views_by_day), key=str)
    ]

    recent_movies = (
        db.scalars(select(Movie).order_by(Movie.created_at.desc()).limit(5)).unique().all()
    )
    failures = db.execute(
        select(
            ProcessingJob.id,
            ProcessingJob.movie_id,
            Movie.title,
            ProcessingJob.error,
            ProcessingJob.finished_at,
        )
        .join(Movie, Movie.id == ProcessingJob.movie_id)
        .where(ProcessingJob.status == JobStatus.FAILED)
        .order_by(ProcessingJob.id.desc())
        .limit(10)
    ).all()
    active_jobs = db.execute(
        select(
            ProcessingJob.id,
            ProcessingJob.movie_id,
            Movie.title,
            ProcessingJob.status,
            ProcessingJob.created_at,
        )
        .join(Movie, Movie.id == ProcessingJob.movie_id)
        .where(ProcessingJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]))
        .order_by(ProcessingJob.id)
    ).all()
    ads = db.scalars(select(Advertisement).order_by(Advertisement.impressions.desc())).all()

    return {
        "period_days": days,
        "totals": {
            "movies": sum(by_status.values()),
            "movies_by_status": by_status,
            "views": db.scalar(select(func.count(MovieView.id))) or 0,
            "views_in_period": db.scalar(select(func.count()).select_from(period_views)) or 0,
            "watch_seconds": db.scalar(select(func.coalesce(func.sum(MovieView.watch_duration), 0)))
            or 0,
            "visits": db.scalar(select(func.count()).where(SiteEvent.event_type == "visit")) or 0,
            "visits_in_period": db.scalar(select(func.count()).select_from(period_visits)) or 0,
            "unique_visitors_in_period": db.scalar(
                select(func.count(func.distinct(SiteEvent.anonymous_session_id))).where(
                    SiteEvent.created_at >= since
                )
            )
            or 0,
            "storage_bytes": db.scalar(select(func.coalesce(func.sum(Movie.storage_bytes), 0)))
            or 0,
        },
        "most_watched": [dict(r._mapping) for r in most_watched],
        "popular_genres": [{"name": n, "views": v} for n, v in popular_genres],
        "popular_languages": [{"name": n, "views": v} for n, v in popular_languages],
        "devices": {d: c for d, c in devices},
        "trend": trend,
        "recent_movies": [
            {
                "id": m.id,
                "title": m.title,
                "slug": m.slug,
                "status": m.status,
                "created_at": m.created_at,
            }
            for m in recent_movies
        ],
        "jobs_by_status": jobs_by_status,
        "active_jobs": [dict(r._mapping) for r in active_jobs],
        "processing_failures": [dict(r._mapping) for r in failures],
        "ads": [
            {
                "id": a.id,
                "title": a.title,
                "placement": a.placement,
                "status": a.status,
                "impressions": a.impressions,
                "clicks": a.clicks,
                "ctr": round(a.clicks / a.impressions * 100, 2) if a.impressions else 0.0,
            }
            for a in ads
        ],
    }
