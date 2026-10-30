"""Public, unauthenticated, read-mostly endpoints. Only published content is ever returned."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models import Advertisement
from app.schemas.admin import EventIn, PublicAdOut
from app.schemas.movie import (
    CategoriesOut,
    GenreWithCount,
    LanguageWithCount,
    MovieCard,
    MovieDetail,
    MoviePage,
)
from app.services import analytics
from app.services import movies as svc
from app.services.movies import SortOrder

router = APIRouter(prefix="/api", tags=["public"])

DB = Annotated[Session, Depends(get_db)]
Page = Annotated[int, Query(ge=1, le=10_000)]
PageSize = Annotated[int, Query(ge=1, le=48)]
Limit = Annotated[int, Query(ge=1, le=30)]
LanguageCode = Annotated[str | None, Query(pattern=r"^[a-z]{2,3}$")]
GenreSlug = Annotated[str | None, Query(pattern=r"^[a-z0-9-]{1,60}$")]
Year = Annotated[int | None, Query(ge=1888, le=2100)]


def _cached(response: Response, seconds: int = 60) -> None:
    response.headers["Cache-Control"] = f"public, max-age={seconds}, stale-while-revalidate=300"


@router.get("/health")
def health(db: DB) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable") from exc
    return {"status": "ok"}


@router.get("/movies", response_model=MoviePage)
def list_movies(
    db: DB,
    response: Response,
    page: Page = 1,
    page_size: PageSize = 24,
    language: LanguageCode = None,
    genre: GenreSlug = None,
    year: Year = None,
    sort: SortOrder = "latest",
):
    _cached(response)
    stmt = svc.apply_filters(svc.published(), language=language, genre=genre, year=year)
    return svc.paginate(db, stmt, page, page_size, svc.order_for(sort))


@router.get("/movies/search", response_model=MoviePage)
def search_movies(
    db: DB,
    response: Response,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Page = 1,
    page_size: PageSize = 24,
    language: LanguageCode = None,
    genre: GenreSlug = None,
    year: Year = None,
    sort: SortOrder = "latest",
):
    _cached(response, 30)
    stmt = svc.apply_filters(svc.published(), q=q, language=language, genre=genre, year=year)
    return svc.paginate(db, stmt, page, page_size, svc.order_for(sort))


@router.get("/movies/latest", response_model=list[MovieCard])
def latest_movies(db: DB, response: Response, limit: Limit = 12):
    _cached(response)
    return svc.latest(db, limit)


@router.get("/movies/featured", response_model=list[MovieCard])
def featured_movies(db: DB, response: Response, limit: Limit = 8):
    _cached(response)
    return svc.featured(db, limit)


@router.get("/movies/trending", response_model=list[MovieCard])
def trending_movies(db: DB, response: Response, limit: Limit = 12):
    _cached(response, 300)
    return svc.trending(db, limit)


@router.get("/movies/{movie_ref}", response_model=MovieDetail)
def get_movie(
    movie_ref: Annotated[str, Path(pattern=r"^[a-z0-9-]{1,220}$")],
    db: DB,
    response: Response,
):
    movie = svc.get_public_movie(db, movie_ref)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")
    _cached(response)
    return movie


@router.get("/languages", response_model=list[LanguageWithCount])
def list_languages(db: DB, response: Response):
    _cached(response, 300)
    return svc.languages_with_counts(db)


@router.get("/genres", response_model=list[GenreWithCount])
def list_genres(db: DB, response: Response):
    _cached(response, 300)
    return svc.genres_with_counts(db)


@router.get("/categories", response_model=CategoriesOut)
def list_categories(db: DB, response: Response):
    _cached(response, 300)
    return {"languages": svc.languages_with_counts(db), "genres": svc.genres_with_counts(db)}


@router.get("/ads", response_model=list[PublicAdOut])
def list_ads(
    db: DB,
    response: Response,
    placement: Annotated[str | None, Query(pattern=r"^[a-z_]{1,30}$")] = None,
):
    _cached(response, 120)
    stmt = select(Advertisement).where(Advertisement.status == "active")
    if placement:
        stmt = stmt.where(Advertisement.placement == placement)
    return db.scalars(stmt.order_by(Advertisement.id)).all()


@router.post("/ads/{ad_id}/impression", status_code=status.HTTP_204_NO_CONTENT)
def ad_impression(ad_id: int, db: DB, request: Request) -> Response:
    if analytics.device_category(request.headers.get("user-agent")) is not None:
        analytics.count_ad(db, ad_id, "impressions")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/ads/{ad_id}/click", status_code=status.HTTP_204_NO_CONTENT)
def ad_click(ad_id: int, db: DB, request: Request) -> Response:
    if analytics.device_category(request.headers.get("user-agent")) is not None:
        analytics.count_ad(db, ad_id, "clicks")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
def track_event(event: EventIn, db: DB, request: Request) -> Response:
    """Anonymous analytics beacon. Bots are dropped silently; nothing identifying is stored."""
    device = analytics.device_category(request.headers.get("user-agent"))
    if device is not None:
        analytics.record_event(db, event, device)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
