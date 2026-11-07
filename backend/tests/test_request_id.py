import json
import logging

from fastapi.testclient import TestClient

from app.core.logging import JsonFormatter
from app.main import create_app

client = TestClient(create_app())


def test_generates_request_id():
    response = client.get("/health")
    assert len(response.headers["X-Request-ID"]) == 32


def test_keeps_client_request_id():
    response = client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


def test_rejects_unsafe_request_id():
    response = client.get("/health", headers={"X-Request-ID": "bad id\nINJECTED"})
    assert response.headers["X-Request-ID"] != "bad id\nINJECTED"


def test_access_log_has_request_id(caplog):
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/health?token=secret", headers={"X-Request-ID": "req-1"})
    record = next(r for r in caplog.records if r.name == "app.request")
    entry = json.loads(JsonFormatter().format(record))
    assert entry["request_id"] == "req-1"
    assert entry["path"] == "/health"
    assert entry["status"] == 200
    assert "secret" not in json.dumps(entry)


def test_rejects_request_id_with_trailing_newline():
    """`$` у регулярному виразі пропускав `abc\n`; ID має збігатися повністю."""
    import anyio

    from app.core.request_id import VALID_ID, RequestIdMiddleware

    assert VALID_ID.fullmatch("abc-123\n") is None
    seen: list[list[tuple[bytes, bytes]]] = []

    async def inner(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def send(message):
        if message["type"] == "http.response.start":
            seen.append(message["headers"])

    async def receive():
        return {"type": "http.request", "body": b""}

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/health",
        "headers": [(b"x-request-id", b"abc-123\n")],
    }
    anyio.run(RequestIdMiddleware(inner), scope, receive, send)
    request_id = dict(seen[0])[b"x-request-id"].decode()
    assert request_id != "abc-123\n" and "\n" not in request_id
