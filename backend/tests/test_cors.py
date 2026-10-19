from fastapi.testclient import TestClient

from app.main import create_app

client = TestClient(create_app())

PWA = "http://localhost:5173"


def test_preflight_allowed_origin():
    response = client.options(
        "/health",
        headers={"Origin": PWA, "Access-Control-Request-Method": "POST"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == PWA
    assert response.headers["access-control-allow-credentials"] == "true"


def test_exposes_request_id():
    response = client.get("/health", headers={"Origin": PWA})
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_unknown_origin_not_allowed():
    response = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers
