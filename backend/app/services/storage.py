"""Object storage abstraction: local filesystem for development, S3-compatible (R2/S3) in production.

Public objects (posters, thumbnails, HLS) are served via MEDIA_PUBLIC_BASE_URL (a CDN in
production). Private objects (original uploads) live in a separate root/bucket that is never
publicly reachable.
"""

import logging
import mimetypes
import shutil
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path, PurePosixPath

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

mimetypes.add_type("application/vnd.apple.mpegurl", ".m3u8")
mimetypes.add_type("video/mp2t", ".ts")
mimetypes.add_type("image/webp", ".webp")

IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


def validate_key(key: str) -> str:
    path = PurePosixPath(key)
    if not key or path.is_absolute() or ".." in path.parts or "\\" in key:
        raise ValueError(f"invalid storage key: {key!r}")
    return key


def guess_content_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


class Storage(ABC):
    def __init__(self, settings: Settings) -> None:
        self.public_base_url = settings.media_public_base_url.rstrip("/")

    @abstractmethod
    def put_file(self, local_path: Path, key: str, *, public: bool) -> int:
        """Upload a file and return its size in bytes."""

    @abstractmethod
    def get_file(self, key: str, dest: Path, *, public: bool) -> None: ...

    @abstractmethod
    def delete(self, key: str, *, public: bool) -> None: ...

    @abstractmethod
    def delete_prefix(self, prefix: str, *, public: bool) -> None: ...

    def put_directory(self, local_dir: Path, prefix: str, *, public: bool) -> int:
        total = 0
        for path in sorted(local_dir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(local_dir).as_posix()
                total += self.put_file(path, f"{prefix.rstrip('/')}/{rel}", public=public)
        return total

    def public_url(self, key: str) -> str:
        return f"{self.public_base_url}/{validate_key(key)}"

    def safe_delete_prefix(self, prefix: str | None, *, public: bool) -> None:
        """Best-effort cleanup that never raises (used after the DB change is committed)."""
        if not prefix:
            return
        try:
            self.delete_prefix(prefix, public=public)
        except Exception:
            logger.exception("storage cleanup failed for prefix %s", prefix)

    def safe_delete(self, key: str | None, *, public: bool) -> None:
        if not key:
            return
        try:
            self.delete(key, public=public)
        except Exception:
            logger.exception("storage cleanup failed for key %s", key)


class LocalStorage(Storage):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.public_root = settings.public_storage_dir.resolve()
        self.private_root = settings.private_storage_dir.resolve()
        self.public_root.mkdir(parents=True, exist_ok=True)
        self.private_root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str, public: bool) -> Path:
        root = self.public_root if public else self.private_root
        path = (root / validate_key(key)).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f"invalid storage key: {key!r}")
        return path

    def put_file(self, local_path: Path, key: str, *, public: bool) -> int:
        dest = self._path(key, public)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, dest)
        return dest.stat().st_size

    def get_file(self, key: str, dest: Path, *, public: bool) -> None:
        shutil.copyfile(self._path(key, public), dest)

    def delete(self, key: str, *, public: bool) -> None:
        self._path(key, public).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str, *, public: bool) -> None:
        path = self._path(prefix.rstrip("/"), public)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


class S3Storage(Storage):
    """Works with AWS S3 and Cloudflare R2 (set S3_ENDPOINT_URL and S3_REGION=auto for R2)."""

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        import boto3  # imported lazily so local dev doesn't need credentials

        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )
        self.public_bucket = settings.s3_public_bucket
        self.private_bucket = settings.s3_private_bucket

    def _bucket(self, public: bool) -> str:
        return self.public_bucket if public else self.private_bucket

    def put_file(self, local_path: Path, key: str, *, public: bool) -> int:
        extra = {"ContentType": guess_content_type(local_path.name)}
        if public:
            # Keys embed a random id or job id, so objects never change once written.
            extra["CacheControl"] = IMMUTABLE_CACHE
        self.client.upload_file(
            str(local_path), self._bucket(public), validate_key(key), ExtraArgs=extra
        )
        return local_path.stat().st_size

    def get_file(self, key: str, dest: Path, *, public: bool) -> None:
        self.client.download_file(self._bucket(public), validate_key(key), str(dest))

    def delete(self, key: str, *, public: bool) -> None:
        self.client.delete_object(Bucket=self._bucket(public), Key=validate_key(key))

    def delete_prefix(self, prefix: str, *, public: bool) -> None:
        bucket = self._bucket(public)
        prefix = validate_key(prefix).rstrip("/") + "/"
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            for i in range(0, len(objects), 1000):
                self.client.delete_objects(
                    Bucket=bucket, Delete={"Objects": objects[i : i + 1000], "Quiet": True}
                )


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(settings)
