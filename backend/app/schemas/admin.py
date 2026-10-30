from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.ads import AD_PLACEMENTS
from app.schemas.common import validate_external_url

Placement = Literal["home_top", "home_middle", "home_bottom", "movie_detail", "watch_page"]
assert set(Placement.__args__) == set(AD_PLACEMENTS)  # noqa: S101  keep the two lists in sync


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=256)


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105  OAuth2 token type, not a secret
    expires_in: int
    admin: AdminOut


class LanguageIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    code: str = Field(pattern=r"^[a-z]{2,3}$")


class GenreIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=60)


class AdIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    placement: Placement
    advertisement_url: str = Field(max_length=500)
    image_url: str | None = Field(default=None, max_length=500)
    status: Literal["active", "inactive"] = "active"

    @field_validator("advertisement_url")
    @classmethod
    def _target(cls, v: str) -> str:
        checked = validate_external_url(v)
        if checked is None:
            raise ValueError("advertisement_url is required")
        return checked

    _image = field_validator("image_url")(validate_external_url)


class AdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    placement: str
    advertisement_url: str
    image_url: str | None
    status: str
    impressions: int
    clicks: int
    created_at: datetime


class PublicAdOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    placement: str
    advertisement_url: str
    image_url: str | None


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int | None
    action: str
    entity_type: str | None
    entity_id: int | None
    details: dict | None
    created_at: datetime


class EventIn(BaseModel):
    type: Literal["visit", "page_view", "play", "progress"]
    session_id: str = Field(pattern=r"^[A-Za-z0-9-]{8,64}$")
    movie_id: int | None = None
    path: str | None = Field(default=None, max_length=300)
    watch_seconds: int | None = Field(default=None, ge=0, le=36_000)
