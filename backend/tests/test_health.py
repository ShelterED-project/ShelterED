from fastapi.testclient import TestClient

from app.core.db import get_session
from app.main import create_app

app = create_app()
client = TestClient(app)


class FakeSession:
    def __init__(self, fail: bool) -> None:
        self.fail = fail

    async def execute(self, statement):
        if self.fail:
            raise ConnectionError("db down")


def override_session(fail: bool):
    async def _session():
        yield FakeSession(fail)

    return _session


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok():
    app.dependency_overrides[get_session] = override_session(fail=False)
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_db_down():
    app.dependency_overrides[get_session] = override_session(fail=True)
    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DB_UNAVAILABLE"


def test_version():
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == "0.1.0"
    assert body["profile"] == "cloud"
