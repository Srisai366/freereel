import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, public
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.services.storage import get_storage

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    stop = None
    if settings.run_worker_in_process:
        from app.workers.video_worker import start_background_worker

        stop = start_background_worker()
    logger.info(
        "startup complete (env=%s, storage=%s)", settings.environment, settings.storage_backend
    )
    yield
    if stop is not None:
        stop.set()


def create_app() -> FastAPI:
    settings = get_settings()
    if settings.environment != "test":
        configure_logging(json_output=settings.is_production)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/api/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/api/openapi.json",
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Same shape as FastAPI's default, minus echoing the raw input back.
        errors = [{k: v for k, v in e.items() if k in ("loc", "msg", "type")} for e in exc.errors()]
        return JSONResponse({"detail": errors}, status_code=422)

    app.include_router(public.router)
    app.include_router(admin.auth_router)
    app.include_router(admin.router)

    if settings.storage_backend == "local":
        storage = get_storage()
        app.mount("/media", StaticFiles(directory=storage.public_root), name="media")

    # Starlette runs the last-added middleware first: CORS must be outermost so even
    # 413/429 responses carry CORS headers the browser can read.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(BodySizeLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    return app


app = create_app()
