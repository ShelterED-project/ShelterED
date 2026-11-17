import json
import sys
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models
from utils import utcnow

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def connected(db):
    """Стан, ніби вчитель уже підключився й обрав клас."""
    st = models.get_state(db)
    st.access_token = "access-1"
    st.refresh_token = "refresh-1"
    st.access_expires_at = utcnow() + timedelta(minutes=10)
    st.class_id = CLASS_ID
    st.class_name = "5-А"
    db.commit()
    return st


class FakeCloud:
    """Імітація хмарного API для httpx.MockTransport.

    Обробники можна перевизначати: cloud.routes[("POST", "/sync/events")] = fn(request) -> Response.
    """

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.valid_access = {"access-1"}
        self.refresh_calls = 0
        self.routes = {
            ("GET", f"/classes/{CLASS_ID}"): lambda r: httpx.Response(
                200, json={"id": CLASS_ID, "name": "5-А"}
            ),
            ("GET", f"/classes/{CLASS_ID}/rollcall/current"): lambda r: httpx.Response(
                200, json={"class_id": CLASS_ID, "session": None}
            ),
            ("POST", f"/classes/{CLASS_ID}/rollcall"): lambda r: httpx.Response(
                201, json={"id": json.loads(r.content)["id"]}
            ),
            ("POST", "/sync/events"): self.accept_all,
            ("POST", "/auth/token"): self.token,
        }

    @staticmethod
    def accept_all(request):
        events = json.loads(request.content)["events"]
        return httpx.Response(
            200,
            json={
                "results": [
                    {"client_event_id": e["client_event_id"], "status": "accepted", "reason": None}
                    for e in events
                ],
                "server_time": "2026-11-16T10:00:00Z",
            },
        )

    def token(self, request):
        body = json.loads(request.content)
        assert body["grant_type"] == "refresh_token"
        self.refresh_calls += 1
        new = f"access-{self.refresh_calls + 1}"
        self.valid_access = {new}
        return httpx.Response(
            200,
            json={
                "access_token": new,
                "refresh_token": f"refresh-{self.refresh_calls + 1}",
                "expires_in": 900,
                "token_type": "bearer",
            },
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if not path.startswith("/auth/"):
            auth = request.headers.get("Authorization", "")
            if auth.removeprefix("Bearer ") not in self.valid_access:
                return httpx.Response(401, json={"error": {"code": "UNAUTHORIZED"}})
        route = self.routes.get((request.method, path))
        if route is None:
            return httpx.Response(404, json={"error": {"code": "NOT_FOUND"}})
        return route(request)

    def transport(self):
        return httpx.MockTransport(self.handler)

    def sent_events(self):
        out = []
        for r in self.requests:
            if r.url.path == "/sync/events":
                out.append(json.loads(r.content))
        return out


@pytest.fixture
def cloud():
    return FakeCloud()
