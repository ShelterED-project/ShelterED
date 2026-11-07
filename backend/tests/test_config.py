import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_defaults(monkeypatch):
    # conftest.py виставляє тестові змінні оточення — для перевірки дефолтів прибираємо.
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    settings = Settings(_env_file=None)
    assert settings.profile == "cloud"
    assert settings.environment == "dev"
    assert settings.cors_origins == ["http://localhost:5173"]


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example"]')
    settings = Settings(_env_file=None)
    assert settings.environment == "prod"
    assert settings.cors_origins == ["https://app.example"]


def test_database_url_is_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:topsecret@host/db")
    settings = Settings(_env_file=None)
    assert "topsecret" not in repr(settings)
    assert settings.database_url.get_secret_value().endswith("@host/db")


def test_jwt_secret_too_short_rejected(monkeypatch):
    # Порожній секрет із `.env.example` дав би підробні токени.
    monkeypatch.setenv("JWT_SECRET", "")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None)
    monkeypatch.setenv("JWT_SECRET", "short-secret")
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "origins",
    ['["*"]', '["http://app.example"]', '["https://app.example", "http://localhost:5173"]'],
)
def test_prod_rejects_wildcard_and_plain_http_cors_origins(monkeypatch, origins):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("CORS_ORIGINS", origins)
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(_env_file=None)
    # Поза prod (розробка) http://localhost дозволено.
    monkeypatch.setenv("ENVIRONMENT", "dev")
    Settings(_env_file=None)


def test_prod_requires_database_url(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None)
    monkeypatch.setenv("ENVIRONMENT", "dev")
    assert Settings(_env_file=None).database_url is None
