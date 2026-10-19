from fastapi import FastAPI

from app.api import health
from app.core.config import APP_VERSION, get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=APP_VERSION)
    app.include_router(health.router)
    return app


app = create_app()
