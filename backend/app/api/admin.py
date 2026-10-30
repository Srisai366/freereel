"""Administrator API. Every route except /login sits behind get_current_admin at router level,
so a new endpoint can't accidentally be left public."""

import uuid
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_full_admin
from app.core.config import get_settings
from app.core.middleware import client_ip, limiter
from app.core.security import create_access_token, dummy_hash, verify_password
from app.database.base import utcnow
from app.database.session import get_db
from app.models import (
    AdminUser,
    Advertisement,
    AuditLog,
    Genre,
    JobStatus,
    Language,
    Movie,
    MovieStatus,
    ProcessingJob,
)
from app.schemas.admin import (
    AdIn,
    AdminOut,
    AdOut,
    AuditLogOut,
    GenreIn,
    LanguageIn,
    LoginRequest,
    TokenResponse,
)
from app.schemas.movie import (
    GenreOut,
    JobOut,
    LanguageOut,
    MovieAdminOut,
    MovieAdminPage,
    MovieCreate,
    MovieUpdate,
)
from app.services import analytics, audit, uploads, video_jobs
from app.services import movies as movie_svc
from app.services.storage import get_storage
from app.services.text import escape_like, slugify

DB = Annotated[Session, Depends(get_db)]
CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]
FullAdmin = Annotated[AdminUser, Depends(require_full_admin)]

auth_router = APIRouter(prefix="/api/admin", tags=["admin-auth"])
router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


# ---- auth --------------------------------------------------------------------


@auth_router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: DB):
    settings = get_settings()
    ip = client_ip(request)
    if not limiter.hit(f"login:{ip}", settings.login_rate_limit_per_minute):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many login attempts, try again in a minute",
            headers={"Retry-After": "60"},
        )
    admin = db.scalar(select(AdminUser).where(AdminUser.username == body.username))
    # Always run one hash verification so response time doesn't reveal whether the user exists.
    valid = verify_password(admin.password_hash if admin else dummy_hash(), body.password)
    if admin is None or not valid or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    admin.last_login_at = utcnow()
    audit.record(db, admin, "admin.login", details={"ip": ip})
    db.commit()
    token, expires_in = create_access_token(admin.id, admin.role)
    return {"access_token": token, "expires_in": expires_in, "admin": admin}


@router.get("/me", response_model=AdminOut)
def me(admin: CurrentAdmin):
    return admin


# ---- movies ------------------------------------------------------------------


def _get_movie(db: Session, movie_id: int) -> Movie:
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Movie not found")
    return movie


def _admin_out(db: Session, movie: Movie) -> MovieAdminOut:
    out = MovieAdminOut.model_validate(movie)
    job = video_jobs.latest_job(db, movie.id)
    out.latest_job = JobOut.model_validate(job) if job else None
    return out


def _resolve_genres(db: Session, genre_ids: list[int]) -> list[Genre]:
    ids = set(genre_ids)
    genres = list(db.scalars(select(Genre).where(Genre.id.in_(ids)))) if ids else []
    if len(genres) != len(ids):
        raise HTTPException(422, "Unknown genre id")
    return genres


def _check_language(db: Session, language_id: int | None) -> None:
    if language_id is not None and db.get(Language, language_id) is None:
        raise HTTPException(422, "Unknown language id")


def _apply_video_url(movie: Movie, url: str | None) -> None:
    movie.video_url = url
    movie.video_format = ("hls" if ".m3u8" in url.lower() else "mp4") if url else None


@router.get("/movies", response_model=MovieAdminPage)
def admin_list_movies(
    db: DB,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    q: Annotated[str | None, Query(max_length=100)] = None,
    movie_status: Annotated[MovieStatus | None, Query(alias="status")] = None,
):
    stmt = select(Movie)
    if q:
        stmt = stmt.where(Movie.title.ilike(f"%{escape_like(q)}%", escape="\\"))
    if movie_status:
        stmt = stmt.where(Movie.status == movie_status)
    result = movie_svc.paginate(
        db, stmt, page, page_size, [Movie.created_at.desc(), Movie.id.desc()]
    )
    result["items"] = [_admin_out(db, m) for m in result["items"]]
    return result


@router.get("/movies/{movie_id}", response_model=MovieAdminOut)
def admin_get_movie(movie_id: int, db: DB):
    return _admin_out(db, _get_movie(db, movie_id))


@router.post("/movies", response_model=MovieAdminOut, status_code=status.HTTP_201_CREATED)
def create_movie(body: MovieCreate, db: DB, admin: CurrentAdmin):
    _check_language(db, body.language_id)
    genres = _resolve_genres(db, body.genre_ids)
    if body.slug:
        if db.scalar(select(Movie.id).where(Movie.slug == body.slug)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Slug already in use")
        slug = body.slug
    else:
        slug = movie_svc.unique_slug(db, body.title, body.release_year)

    data = body.model_dump(exclude={"genre_ids", "slug", "video_url", "status"})
    movie = Movie(**data, slug=slug, genres=genres, status=body.status)
    _apply_video_url(movie, body.video_url)
    if movie.status == MovieStatus.PUBLISHED:
        movie.published_at = utcnow()
    db.add(movie)
    db.flush()
    audit.record(db, admin, "movie.create", "movie", movie.id, {"title": movie.title})
    db.commit()
    return _admin_out(db, movie)


@router.put("/movies/{movie_id}", response_model=MovieAdminOut)
def update_movie(movie_id: int, body: MovieUpdate, db: DB, admin: CurrentAdmin):
    movie = _get_movie(db, movie_id)
    changes = body.model_dump(exclude_unset=True)

    if "language_id" in changes:
        _check_language(db, changes["language_id"])
    if "genre_ids" in changes:
        movie.genres = _resolve_genres(db, changes.pop("genre_ids") or [])
    if "slug" in changes and changes["slug"] and changes["slug"] != movie.slug:
        if db.scalar(select(Movie.id).where(Movie.slug == changes["slug"], Movie.id != movie.id)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Slug already in use")
    elif "slug" in changes and not changes["slug"]:
        changes.pop("slug")
    if "video_url" in changes:
        _apply_video_url(movie, changes.pop("video_url"))
    if "status" in changes:
        new_status = changes.pop("status")
        if new_status == MovieStatus.PUBLISHED and movie.status != MovieStatus.PUBLISHED:
            movie.published_at = movie.published_at or utcnow()
        movie.status = new_status
    for field, value in changes.items():
        if field in ("title", "featured", "cast_members", "description") and value is None:
            continue  # explicit null on a required field is ignored rather than stored
        setattr(movie, field, value)

    audit.record(
        db, admin, "movie.update", "movie", movie.id, {"fields": sorted(body.model_fields_set)}
    )
    db.commit()
    return _admin_out(db, movie)


@router.delete("/movies/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_movie(movie_id: int, db: DB, admin: FullAdmin) -> Response:
    movie = _get_movie(db, movie_id)
    audit.record(db, admin, "movie.delete", "movie", movie.id, {"title": movie.title})
    db.delete(movie)
    db.commit()
    storage = get_storage()
    storage.safe_delete_prefix(f"movies/{movie_id}", public=True)
    storage.safe_delete_prefix(f"originals/{movie_id}", public=False)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/movies/{movie_id}/poster", response_model=MovieAdminOut)
def upload_poster(movie_id: int, db: DB, admin: CurrentAdmin, file: UploadFile = File(...)):
    movie = _get_movie(db, movie_id)
    settings = get_settings()
    ext = uploads.extension_of(file.filename, uploads.IMAGE_EXTENSIONS)
    raw = uploads.save_stream(file.file, settings.max_poster_bytes, ext)
    optimized = None
    try:
        optimized = uploads.optimize_poster(raw)
        key = f"movies/{movie.id}/posters/{uuid.uuid4().hex}.webp"
        storage = get_storage()
        storage.put_file(optimized, key, public=True)
    finally:
        raw.unlink(missing_ok=True)
        if optimized:
            optimized.unlink(missing_ok=True)

    old_key = movie.poster_key
    movie.poster_key = key
    movie.poster_url = storage.public_url(key)
    audit.record(db, admin, "movie.poster", "movie", movie.id)
    db.commit()
    storage.safe_delete(old_key, public=True)
    return _admin_out(db, movie)


@router.post(
    "/movies/{movie_id}/video", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED
)
def upload_video(movie_id: int, db: DB, admin: CurrentAdmin, file: UploadFile = File(...)):
    """Accept an authorized original; processing happens later in the worker (202 Accepted)."""
    movie = _get_movie(db, movie_id)
    settings = get_settings()
    ext = uploads.extension_of(file.filename, uploads.VIDEO_EXTENSIONS)
    raw = uploads.save_stream(file.file, settings.max_video_bytes, ext)
    try:
        uploads.validate_video_file(raw)
        audit.record(
            db, admin, "movie.video_upload", "movie", movie.id, {"bytes": raw.stat().st_size}
        )
        job = video_jobs.enqueue_video(db, movie, raw, ext)
    finally:
        raw.unlink(missing_ok=True)
    return job


# ---- processing jobs -----------------------------------------------------------


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    db: DB,
    job_status: Annotated[JobStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    stmt = select(ProcessingJob)
    if job_status:
        stmt = stmt.where(ProcessingJob.status == job_status)
    return db.scalars(stmt.order_by(ProcessingJob.id.desc()).limit(limit)).all()


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: int, db: DB, admin: CurrentAdmin):
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    if job.status != JobStatus.FAILED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only failed jobs can be retried")
    audit.record(db, admin, "job.retry", "job", job.id)
    video_jobs.requeue(db, job)
    return job


# ---- languages & genres ------------------------------------------------------------


def _flush_unique(db: Session, what: str) -> None:
    """Flush pending changes, turning a unique-constraint violation into a 409."""
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"{what} already exists") from None


@router.get("/languages", response_model=list[LanguageOut])
def admin_languages(db: DB):
    return db.scalars(select(Language).order_by(Language.name)).all()


@router.post("/languages", response_model=LanguageOut, status_code=status.HTTP_201_CREATED)
def create_language(body: LanguageIn, db: DB, admin: FullAdmin):
    lang = Language(name=body.name.strip(), code=body.code)
    db.add(lang)
    _flush_unique(db, "Language")
    audit.record(db, admin, "language.create", "language", lang.id, {"code": lang.code})
    db.commit()
    return lang


@router.put("/languages/{language_id}", response_model=LanguageOut)
def update_language(language_id: int, body: LanguageIn, db: DB, admin: FullAdmin):
    lang = db.get(Language, language_id)
    if lang is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Language not found")
    lang.name, lang.code = body.name.strip(), body.code
    _flush_unique(db, "Language")
    audit.record(db, admin, "language.update", "language", lang.id)
    db.commit()
    return lang


@router.delete("/languages/{language_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_language(language_id: int, db: DB, admin: FullAdmin) -> Response:
    lang = db.get(Language, language_id)
    if lang is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Language not found")
    in_use = db.scalar(select(func.count(Movie.id)).where(Movie.language_id == language_id))
    if in_use:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Language is used by {in_use} movie(s)")
    audit.record(db, admin, "language.delete", "language", lang.id, {"code": lang.code})
    db.delete(lang)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/genres", response_model=list[GenreOut])
def admin_genres(db: DB):
    return db.scalars(select(Genre).order_by(Genre.name)).all()


@router.post("/genres", response_model=GenreOut, status_code=status.HTTP_201_CREATED)
def create_genre(body: GenreIn, db: DB, admin: FullAdmin):
    genre = Genre(name=body.name.strip(), slug=body.slug or slugify(body.name))
    if not genre.slug:
        raise HTTPException(422, "Genre needs a Latin-letter slug")
    db.add(genre)
    _flush_unique(db, "Genre")
    audit.record(db, admin, "genre.create", "genre", genre.id, {"slug": genre.slug})
    db.commit()
    return genre


@router.put("/genres/{genre_id}", response_model=GenreOut)
def update_genre(genre_id: int, body: GenreIn, db: DB, admin: FullAdmin):
    genre = db.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Genre not found")
    genre.name = body.name.strip()
    genre.slug = body.slug or slugify(body.name) or genre.slug
    _flush_unique(db, "Genre")
    audit.record(db, admin, "genre.update", "genre", genre.id)
    db.commit()
    return genre


@router.delete("/genres/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_genre(genre_id: int, db: DB, admin: FullAdmin) -> Response:
    genre = db.get(Genre, genre_id)
    if genre is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Genre not found")
    audit.record(db, admin, "genre.delete", "genre", genre.id, {"slug": genre.slug})
    db.delete(genre)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- advertisements ------------------------------------------------------------------


@router.get("/ads", response_model=list[AdOut])
def admin_ads(db: DB):
    return db.scalars(select(Advertisement).order_by(Advertisement.id.desc())).all()


@router.post("/ads", response_model=AdOut, status_code=status.HTTP_201_CREATED)
def create_ad(body: AdIn, db: DB, admin: FullAdmin):
    ad = Advertisement(**body.model_dump())
    db.add(ad)
    db.flush()
    audit.record(db, admin, "ad.create", "advertisement", ad.id, {"title": ad.title})
    db.commit()
    return ad


@router.put("/ads/{ad_id}", response_model=AdOut)
def update_ad(ad_id: int, body: AdIn, db: DB, admin: FullAdmin):
    ad = db.get(Advertisement, ad_id)
    if ad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Advertisement not found")
    for field, value in body.model_dump().items():
        setattr(ad, field, value)
    audit.record(db, admin, "ad.update", "advertisement", ad.id)
    db.commit()
    return ad


@router.delete("/ads/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ad(ad_id: int, db: DB, admin: FullAdmin) -> Response:
    ad = db.get(Advertisement, ad_id)
    if ad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Advertisement not found")
    audit.record(db, admin, "ad.delete", "advertisement", ad.id, {"title": ad.title})
    db.delete(ad)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- analytics & audit -------------------------------------------------------------


@router.get("/analytics")
def admin_analytics(db: DB, days: Annotated[int, Query(ge=1, le=365)] = 30) -> dict:
    return analytics.dashboard(db, days)


@router.get(
    "/audit-logs", response_model=list[AuditLogOut], dependencies=[Depends(require_full_admin)]
)
def audit_logs(db: DB, limit: Annotated[int, Query(ge=1, le=500)] = 100):
    return db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
