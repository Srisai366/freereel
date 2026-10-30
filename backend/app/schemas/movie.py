import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.schemas.common import validate_external_url

SLUG_PATTERN = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class LanguageOut(ORMModel):
    id: int
    name: str
    code: str


class GenreOut(ORMModel):
    id: int
    name: str
    slug: str


class LanguageWithCount(LanguageOut):
    movie_count: int = 0


class GenreWithCount(GenreOut):
    movie_count: int = 0


class CategoriesOut(BaseModel):
    languages: list[LanguageWithCount]
    genres: list[GenreWithCount]


class MovieCard(ORMModel):
    id: int
    title: str
    slug: str
    release_year: int | None
    duration: int | None
    poster_url: str | None
    thumbnail_url: str | None
    featured: bool
    language: LanguageOut | None
    genres: list[GenreOut]
    video_quality: list[str] = Field(validation_alias="quality_list")
    video_url: str | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def has_video(self) -> bool:
        return bool(self.video_url)


class MovieDetail(MovieCard):
    description: str
    director: str | None
    cast_members: list[str]
    license: str | None
    video_url: str | None = None
    video_format: str | None
    created_at: datetime
    published_at: datetime | None


class MoviePage(BaseModel):
    items: list[MovieCard]
    total: int
    page: int
    page_size: int
    pages: int


# ---- admin ----------------------------------------------------------------


def _clean_cast(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    cleaned = [v.strip() for v in values if v and v.strip()]
    if any(len(v) > 100 for v in cleaned):
        raise ValueError("cast member names must be at most 100 characters")
    return cleaned


def _check_slug(value: str | None) -> str | None:
    if value is not None and value.isdigit():
        raise ValueError("slug cannot be purely numeric")
    return value


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=220, pattern=SLUG_PATTERN)
    description: str = Field(default="", max_length=5000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    language_id: int | None = None
    genre_ids: list[int] = Field(default_factory=list, max_length=10)
    duration: int | None = Field(default=None, ge=1, le=36_000)
    director: str | None = Field(default=None, max_length=200)
    cast_members: list[str] = Field(default_factory=list, max_length=30)
    license: str | None = Field(default=None, max_length=200)
    featured: bool = False
    status: Literal["draft", "published"] = "draft"
    # An authorized externally hosted stream (HLS .m3u8 or MP4), instead of uploading a file.
    video_url: str | None = Field(default=None, max_length=500)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = re.sub(r"\s+", " ", v).strip()
        if not v:
            raise ValueError("title cannot be blank")
        return v

    _slug = field_validator("slug")(_check_slug)
    _cast = field_validator("cast_members")(_clean_cast)
    _video = field_validator("video_url")(validate_external_url)


class MovieUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=220, pattern=SLUG_PATTERN)
    description: str | None = Field(default=None, max_length=5000)
    release_year: int | None = Field(default=None, ge=1888, le=2100)
    language_id: int | None = None
    genre_ids: list[int] | None = Field(default=None, max_length=10)
    duration: int | None = Field(default=None, ge=1, le=36_000)
    director: str | None = Field(default=None, max_length=200)
    cast_members: list[str] | None = Field(default=None, max_length=30)
    license: str | None = Field(default=None, max_length=200)
    featured: bool | None = None
    status: Literal["draft", "published"] | None = None
    video_url: str | None = Field(default=None, max_length=500)

    _slug = field_validator("slug")(_check_slug)
    _cast = field_validator("cast_members")(_clean_cast)
    _video = field_validator("video_url")(validate_external_url)


class JobOut(ORMModel):
    id: int
    movie_id: int
    status: str
    attempts: int
    error: str | None
    source_bytes: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class MovieAdminOut(MovieDetail):
    status: str
    language_id: int | None
    storage_bytes: int
    updated_at: datetime
    latest_job: JobOut | None = None


class MovieAdminPage(BaseModel):
    items: list[MovieAdminOut]
    total: int
    page: int
    page_size: int
    pages: int
