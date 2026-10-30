import logging
import re
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings

logger = logging.getLogger("app.request")

_UPLOAD_PATH = re.compile(r"^/api/admin/movies/\d+/(poster|video)$")
_DEFAULT_MAX_BODY = 2 * 1024 * 1024
_MULTIPART_OVERHEAD = 1024 * 1024


class SlidingWindowLimiter:
    """In-memory per-key limiter. Fine for a single instance; swap for Redis when scaling out."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > 50_000:
                self._prune(now, window)
            hits = self._hits[key]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= limit:
                return False
            hits.append(now)
            return True

    def _prune(self, now: float, window: float) -> None:
        for key in [k for k, q in self._hits.items() if not q or q[-1] <= now - window]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """Visitor IP for rate limiting.

    Proxy headers are only honoured when TRUST_PROXY_HEADERS is on, which is safe only if the
    origin can't be reached except through the CDN (on AWS the security group allows CloudFront only).
    """
    if get_settings().trust_proxy_headers:
        # AWS CloudFront: "ip:port" (IPv6 addresses contain colons too, so split from the right).
        viewer = request.headers.get("cloudfront-viewer-address")
        if viewer and ":" in viewer:
            return viewer.rsplit(":", 1)[0]
        forwarded = (
            request.headers.get("cf-connecting-ip")  # Cloudflare
            or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        )
        if forwarded:
            return forwarded
    return request.client.host if request.client else "unknown"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request id, access log line, and a JSON 500 for anything unhandled."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled error", extra={"request_id": request_id})
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            },
        )
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if not request.url.path.startswith(("/api/docs", "/api/redoc")):
            headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if get_settings().is_production:
            headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized bodies by Content-Length before anything is read or parsed."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            settings = get_settings()
            path = request.url.path
            match = _UPLOAD_PATH.match(path)
            if match:
                limit = (
                    settings.max_video_bytes
                    if match.group(1) == "video"
                    else settings.max_poster_bytes
                ) + _MULTIPART_OVERHEAD
            else:
                limit = _DEFAULT_MAX_BODY
            length = request.headers.get("content-length")
            if length is None:
                if match:
                    return JSONResponse({"detail": "Content-Length required"}, status_code=411)
            elif not length.isdigit() or int(length) > limit:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP limit on public API traffic. Admin routes (except login) are authenticated, so they're skipped."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if (
            request.method != "OPTIONS"
            and path.startswith("/api/")
            and path != "/api/health"
            and not (path.startswith("/api/admin/") and path != "/api/admin/login")
        ):
            limit = get_settings().rate_limit_per_minute
            if not limiter.hit(f"api:{client_ip(request)}", limit):
                return JSONResponse(
                    {"detail": "Too many requests"}, status_code=429, headers={"Retry-After": "60"}
                )
        return await call_next(request)
