from app.core.config import Settings


def test_defaults():
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
