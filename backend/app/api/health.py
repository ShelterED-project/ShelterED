import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import APP_VERSION, Settings, get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.schemas.errors import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str


class VersionResponse(BaseModel):
    version: str
    git_sha: str | None
    profile: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness: процес живий. БД не перевіряє, щоб падіння Neon не перезапускало API."""
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def ready(session: Annotated[AsyncSession, Depends(get_session)]) -> HealthResponse:
    """Readiness: API може обслуговувати запити (є з'єднання з БД)."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Database is not reachable: %s", type(exc).__name__)
        raise AppError("DB_UNAVAILABLE", "Database is not reachable", status_code=503) from exc
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
async def get_version(settings: Annotated[Settings, Depends(get_settings)]) -> VersionResponse:
    return VersionResponse(
        version=APP_VERSION,
        git_sha=settings.git_sha,
        profile=settings.profile,
        environment=settings.environment,
    )
