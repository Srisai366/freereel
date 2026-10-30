import math
from datetime import timedelta
from typing import Literal

from sqlalchemy import Select, String, and_, cast, func, or_, select
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Genre, Language, Movie, MovieStatus, MovieView, movie_genres
from app.services.text import escape_like, slugify

SortOrder = Literal["latest", "title", "year", "popular"]


def published() -> Select[tuple[Movie]]:
    return select(Movie).where(Movie.status == MovieStatus.PUBLISHED)


def apply_filters(
    stmt: Select,
    *,
    q: str | None = None,
    language: str | None = None,
    genre: str | None = None,
    year: int | None = None,
) -> Select:
    if q:
        like = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                Movie.title.ilike(like, escape="\\"),
                Movie.director.ilike(like, escape="\\"),
                cast(Movie.cast_members, String).ilike(like, escape="\\"),
            )
        )
    if language:
        stmt = stmt.where(Movie.language.has(Language.code == language))
    if genre:
        stmt = stmt.where(Movie.genres.any(Genre.slug == genre))
    if year:
        stmt = stmt.where(Movie.release_year == year)
    return stmt


def paginate(db: Session, stmt: Select, page: int, page_size: int, order_by: list) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = (
        db.scalars(stmt.order_by(*order_by).offset((page - 1) * page_size).limit(page_size))
        .unique()
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)),
    }


def _popularity():
    return (
        select(func.count(MovieView.id))
        .where(MovieView.movie_id == Movie.id)
        .correlate(Movie)
        .scalar_subquery()
    )


def order_for(sort: SortOrder) -> list:
    if sort == "title":
        return [Movie.title.asc(), Movie.id.asc()]
    if sort == "year":
        return [Movie.release_year.desc(), Movie.id.desc()]
    if sort == "popular":
        return [_popularity().desc(), Movie.id.desc()]
    return [Movie.published_at.desc(), Movie.id.desc()]


def latest(db: Session, limit: int) -> list[Movie]:
    return list(db.scalars(published().order_by(*order_for("latest")).limit(limit)).unique())


def featured(db: Session, limit: int) -> list[Movie]:
    stmt = published().where(Movie.featured.is_(True)).order_by(*order_for("latest")).limit(limit)
    return list(db.scalars(stmt).unique())


def trending(db: Session, limit: int, days: int = 7) -> list[Movie]:
    """Most played in the last `days`; topped up with the latest titles when there's little data."""
    cutoff = utcnow() - timedelta(days=days)
    views = (
        select(MovieView.movie_id, func.count(MovieView.id).label("plays"))
        .where(MovieView.viewed_at >= cutoff)
        .group_by(MovieView.movie_id)
        .subquery()
    )
    stmt = (
        published()
        .join(views, views.c.movie_id == Movie.id)
        .order_by(views.c.plays.desc(), Movie.id.desc())
        .limit(limit)
    )
    movies = list(db.scalars(stmt).unique())
    if len(movies) < limit:
        seen = [m.id for m in movies]
        filler = published().where(Movie.id.not_in(seen)) if seen else published()
        movies += db.scalars(
            filler.order_by(*order_for("latest")).limit(limit - len(movies))
        ).unique()
    return movies


def get_public_movie(db: Session, ref: str) -> Movie | None:
    """Look up a published movie by numeric id or by slug (slugs are never purely numeric)."""
    stmt = (
        published().where(Movie.id == int(ref))
        if ref.isdigit()
        else published().where(Movie.slug == ref)
    )
    return db.scalars(stmt).unique().first()


def languages_with_counts(db: Session) -> list[dict]:
    stmt = (
        select(Language, func.count(Movie.id))
        .outerjoin(
            Movie, and_(Movie.language_id == Language.id, Movie.status == MovieStatus.PUBLISHED)
        )
        .group_by(Language.id)
        .order_by(Language.name)
    )
    return [
        {"id": lang.id, "name": lang.name, "code": lang.code, "movie_count": count}
        for lang, count in db.execute(stmt)
    ]


def genres_with_counts(db: Session) -> list[dict]:
    stmt = (
        select(Genre, func.count(Movie.id))
        .outerjoin(movie_genres, movie_genres.c.genre_id == Genre.id)
        .outerjoin(
            Movie, and_(Movie.id == movie_genres.c.movie_id, Movie.status == MovieStatus.PUBLISHED)
        )
        .group_by(Genre.id)
        .order_by(Genre.name)
    )
    return [
        {"id": g.id, "name": g.name, "slug": g.slug, "movie_count": count}
        for g, count in db.execute(stmt)
    ]


def unique_slug(db: Session, title: str, year: int | None, exclude_id: int | None = None) -> str:
    base = slugify(title) or "movie"
    if year:
        base = f"{base}-{year}"
    elif base.isdigit():
        base = f"movie-{base}"
    candidate, n = base, 2
    while True:
        stmt = select(Movie.id).where(Movie.slug == candidate)
        if exclude_id is not None:
            stmt = stmt.where(Movie.id != exclude_id)
        if db.scalar(stmt) is None:
            return candidate
        candidate, n = f"{base}-{n}", n + 1
