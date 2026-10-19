from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.config import APP_VERSION, Settings, get_settings

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
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
async def get_version(settings: Annotated[Settings, Depends(get_settings)]) -> VersionResponse:
    return VersionResponse(
        version=APP_VERSION,
        git_sha=settings.git_sha,
        profile=settings.profile,
        environment=settings.environment,
    )
