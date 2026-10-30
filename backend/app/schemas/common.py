from urllib.parse import urlparse

from app.core.config import get_settings


def validate_external_url(value: str | None) -> str | None:
    """Allow https URLs only (plain http just for localhost during development)."""
    if value is None or value == "":
        return None
    parsed = urlparse(value)
    if not parsed.netloc:
        raise ValueError("must be an absolute URL")
    if parsed.scheme == "https":
        return value
    if (
        parsed.scheme == "http"
        and parsed.hostname in ("localhost", "127.0.0.1")
        and not get_settings().is_production
    ):
        return value
    raise ValueError("must be an https URL")
