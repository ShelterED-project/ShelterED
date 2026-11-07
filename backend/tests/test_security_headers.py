import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture
def make_client(monkeypatch: pytest.MonkeyPatch):
    def make(base_url: str = "http://test", **env: str) -> TestClient:
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear()
        return TestClient(create_app(), base_url=base_url)

    yield make
    get_settings.cache_clear()


def test_static_headers_on_every_response(make_client):
    response = make_client().get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in response.headers


def test_error_responses_have_headers(make_client):
    response = make_client().get("/no-such-path")
    assert response.status_code == 404
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_api_responses_not_cached_by_default(make_client):
    client = make_client()
    for path in ("/auth/me", "/deletion-requests", "/health", "/no-such-path"):
        assert client.get(path).headers["Cache-Control"] == "no-store", path
    # Префікс за проксі (root_path) не обходить заборону кешу.
    behind_proxy = TestClient(client.app, base_url="http://test", root_path="/api")
    assert behind_proxy.get("/api/auth/me").headers["Cache-Control"] == "no-store"


def test_own_cache_control_is_kept(make_client):
    from fastapi import Response

    app = make_client().app

    @app.get("/cached-test")
    async def cached() -> Response:
        return Response(headers={"Cache-Control": "private, no-cache"})

    response = TestClient(app).get("/cached-test")
    assert response.headers["Cache-Control"] == "private, no-cache"


def test_hsts_only_over_https_when_enabled(make_client):
    client = make_client("https://test", HSTS_ENABLED="true", HSTS_MAX_AGE_S="600")
    assert client.get("/health").headers["Strict-Transport-Security"] == "max-age=600"
    plain = TestClient(client.app, base_url="http://test")
    assert "Strict-Transport-Security" not in plain.get("/health").headers


def test_hsts_off_by_default_even_over_https(make_client):
    response = make_client("https://test").get("/health")
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_on_in_prod(make_client):
    response = make_client("https://test", ENVIRONMENT="prod").get("/health")
    assert response.headers["Strict-Transport-Security"].startswith("max-age=")


def test_spoofed_forwarded_proto_ignored(make_client):
    client = make_client(HSTS_ENABLED="true")
    response = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert "Strict-Transport-Security" not in response.headers
