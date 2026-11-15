from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    alerts,
    auth,
    health,
    lessons,
    media,
    packs,
    privacy,
    push,
    rollcall,
    school,
    stats,
    sync,
    tutor,
    wellbeing,
)
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import APP_VERSION, get_settings
from app.core.db import get_engine
from app.core.errors import UnhandledErrorMiddleware, register_error_handlers
from app.core.logging import setup_logging
from app.core.request_id import RequestIdMiddleware
from app.core.security_headers import SecurityHeadersMiddleware
from app.schemas.errors import ErrorResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    # Закриваємо пул з'єднань, якщо його встигли створити.
    if get_engine.cache_info().currsize:
        await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)
    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_active else None,
        redoc_url="/redoc" if settings.api_docs_active else None,
        openapi_url="/openapi.json" if settings.api_docs_active else None,
        responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    register_error_handlers(app)
    # Найглибший middleware: непередбачена 500 проходить через CORS, request ID і заголовки.
    app.add_middleware(UnhandledErrorMiddleware)
    # Під CORS, request ID і заголовками безпеки: 413 отримує їх так само, як інші помилки.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Без cookie: токен іде в заголовку Authorization, credentials не потрібні.
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "ETag", "Retry-After"],
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_max_age_s=settings.hsts_max_age_s if settings.hsts_active else None,
    )
    # Додана останньою — виконується першою, тож request ID є і в CORS-відповідях.
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(school.router)
    app.include_router(lessons.router)
    app.include_router(media.router)
    app.include_router(packs.router)
    app.include_router(sync.router)
    app.include_router(rollcall.router)
    app.include_router(stats.router)
    app.include_router(alerts.router)
    app.include_router(push.router)
    app.include_router(tutor.router)
    app.include_router(wellbeing.router)
    app.include_router(privacy.router)
    return app


app = create_app()
