from fastapi import FastAPI

from app.api import health
from app.core.config import APP_VERSION, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import setup_logging
from app.core.request_id import RequestIdMiddleware
from app.schemas.errors import ErrorResponse


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)
    app = FastAPI(
        title=settings.app_name,
        version=APP_VERSION,
        responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    register_error_handlers(app)
    app.add_middleware(RequestIdMiddleware)
    app.include_router(health.router)
    return app


app = create_app()
