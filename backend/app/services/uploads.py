"""Upload validation: size caps while streaming to disk, extension allow-lists, magic-byte sniffing."""

import uuid
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

from app.core.config import get_settings

CHUNK = 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"}
POSTER_MAX_SIZE = (600, 900)

Image.MAX_IMAGE_PIXELS = 40_000_000  # refuse decompression bombs


class UploadRejected(HTTPException):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(status_code=status_code, detail=detail)


def extension_of(filename: str | None, allowed: set[str]) -> str:
    ext = Path(filename or "").suffix.lower()
    if ext not in allowed:
        raise UploadRejected(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"File type not allowed. Allowed: {', '.join(sorted(allowed))}",
        )
    return ext


def save_stream(src: BinaryIO, max_bytes: int, suffix: str) -> Path:
    """Copy an upload to a private temp file, aborting as soon as it exceeds max_bytes."""
    tmp_dir = Path(get_settings().upload_tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest = tmp_dir / f"{uuid.uuid4().hex}{suffix}"
    written = 0
    try:
        with dest.open("wb") as out:
            while chunk := src.read(CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    raise UploadRejected(
                        413,
                        f"File exceeds the {max_bytes // (1024 * 1024)} MB limit",
                    )
                out.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    if written == 0:
        dest.unlink(missing_ok=True)
        raise UploadRejected(status.HTTP_400_BAD_REQUEST, "File is empty")
    return dest


def read_head(path: Path, size: int = 32) -> bytes:
    with path.open("rb") as f:
        return f.read(size)


def sniff_image(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def sniff_video(head: bytes) -> str | None:
    if head[4:8] == b"ftyp":
        return "mp4"  # MP4 / M4V / MOV (ISO base media)
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "matroska"  # MKV / WebM
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi"
    if head[4:8] in (b"moov", b"mdat", b"wide", b"free"):
        return "mov"  # older QuickTime files
    return None


def optimize_poster(src: Path) -> Path:
    """Decode with Pillow (rejects corrupt/disguised files), resize, and re-encode as WebP.

    Re-encoding also strips metadata (EXIF/GPS) and any payload hidden after the image data.
    """
    if sniff_image(read_head(src)) is None:
        raise UploadRejected(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Not a valid JPEG, PNG or WebP"
        )
    try:
        with Image.open(src) as probe:
            probe.verify()
        with Image.open(src) as img:
            img = img.convert("RGB")
            img.thumbnail(POSTER_MAX_SIZE, Image.Resampling.LANCZOS)
            dest = src.with_suffix(".poster.webp")
            img.save(dest, "WEBP", quality=82, method=6)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise UploadRejected(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Image could not be decoded"
        ) from exc
    return dest


def validate_video_file(path: Path) -> str:
    kind = sniff_video(read_head(path))
    if kind is None:
        raise UploadRejected(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "File content is not a recognised video container",
        )
    return kind
