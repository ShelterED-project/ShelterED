from functools import lru_cache
from importlib.metadata import version
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Єдине джерело версії — pyproject.toml (пакет встановлено через pip install -e).
APP_VERSION = version("sheltered-backend")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ShelterED API"
    # Профіль розгортання з ТЗ. shelter (локальний сервер укриття) відкладено.
    profile: Literal["cloud"] = "cloud"
    environment: Literal["dev", "test", "prod"] = "dev"
    # SHA коміту, який підставляє CI під час збірки образу.
    git_sha: str | None = None

    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
