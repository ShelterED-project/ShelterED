"""Ліміт розміру тіла запиту: 413 PAYLOAD_TOO_LARGE до розбору JSON; медіа — власні ліміти."""

import uuid

import pytest
from conftest import auth_header

from app.core.config import get_settings

pytestmark = pytest.mark.anyio


def _too_big() -> bytes:
    return b'{"x": "' + b"a" * get_settings().max_request_body_bytes + b'"}'


async def test_large_body_with_content_length_is_rejected(client, world) -> None:
    r = await client.post(
        "/sync/events",
        content=_too_big(),
        headers={**auth_header(world.student_a), "Content-Type": "application/json"},
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    # Як і інші помилки: request ID і no-store.
    assert r.headers["X-Request-ID"] and r.headers["Cache-Control"] == "no-store"


async def test_large_chunked_body_is_rejected(client) -> None:
    body = _too_big()

    async def chunks():
        step = 64 * 1024
        for start in range(0, len(body), step):
            end = start + step
            yield body[start:end]

    r = await client.post(
        "/auth/token", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413
    assert r.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_small_chunked_body_reaches_the_endpoint(client) -> None:
    async def chunks():
        yield b'{"grant_type": "refresh_token",'
        yield b' "refresh_token": "nope"}'

    r = await client.post(
        "/auth/token", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_GRANT"


async def test_media_upload_has_its_own_limit(client, world) -> None:
    """Відео до 30 МБ іде потоком повз загальний ліміт (свої ліміти за типом файла)."""
    size = get_settings().max_request_body_bytes + 1
    r = await client.put(
        f"/media/{uuid.uuid4()}?kind=video",
        content=b"\x00" * size,
        headers={**auth_header(world.teacher_a), "Content-Type": "video/mp4"},
    )
    assert r.json()["error"]["code"] != "PAYLOAD_TOO_LARGE"
