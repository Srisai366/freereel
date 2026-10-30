from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Development placeholder only; _check_production refuses to start with it.
_DEV_SECRET = "dev-only-change-me-dev-only-change-me-dev-only"  # noqa: S105


class Settings(BaseSettings):
    """Application settings, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FreeReel API"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "sqlite:///./freereel.db"

    secret_key: str = _DEV_SECRET
    jwt_expire_minutes: int = 60
    jwt_issuer: str = "freereel"

    cors_origins: str = "http://localhost:3000"
    trust_proxy_headers: bool = False
    rate_limit_per_minute: int = 120
    login_rate_limit_per_minute: int = 5

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_dir: str = "./storage"
    media_public_base_url: str = "http://localhost:8000/media"
    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    s3_public_bucket: str = "freereel-media"
    s3_private_bucket: str = "freereel-originals"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None

    upload_tmp_dir: str = "./tmp_uploads"
    max_poster_mb: int = 5
    max_video_mb: int = 4096
    keep_originals: bool = True

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    hls_segment_seconds: int = 6
    ffmpeg_timeout_seconds: int = 6 * 3600
    run_worker_in_process: bool = False
    worker_poll_seconds: float = 5.0
    worker_max_attempts: int = 3

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        if self.environment == "production":
            if self.secret_key == _DEV_SECRET or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be set to a random value of 32+ characters")
            if "*" in self.cors_origin_list:
                raise ValueError("CORS_ORIGINS must list explicit origins in production")
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        # Hosted providers hand out postgres:// URLs; we ship the psycopg (v3) driver.
        url = self.database_url
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix) :]
        return url

    @property
    def max_poster_bytes(self) -> int:
        return self.max_poster_mb * 1024 * 1024

    @property
    def max_video_bytes(self) -> int:
        return self.max_video_mb * 1024 * 1024

    @property
    def public_storage_dir(self) -> Path:
        return Path(self.local_storage_dir) / "public"

    @property
    def private_storage_dir(self) -> Path:
        return Path(self.local_storage_dir) / "private"


@lru_cache
def get_settings() -> Settings:
    return Settings()
