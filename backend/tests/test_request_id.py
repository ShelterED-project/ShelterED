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
