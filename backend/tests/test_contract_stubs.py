"""Заглушки контракту B4: кожна зареєстрована, захищена роллю й відповідає 501."""

import uuid
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import auth_header
from fastapi import FastAPI
from httpx import AsyncClient

pytestmark = pytest.mark.anyio

ANY_ID = "0192f0a0-0000-7000-8000-00000000ffff"


def sync_body() -> dict:
    return {
        "sent_at": "2026-11-05T09:55:00Z",
        "events": [
            {
                "client_event_id": str(uuid.uuid4()),
                "type": "rollcall_status",
                "device_id": str(uuid.uuid4()),
                "occurred_at": "2026-11-05T09:54:10Z",
                "payload": {"session_id": ANY_ID, "status": "in_shelter"},
            }
        ],
    }


Path = Callable[[SimpleNamespace], str]
Body = Callable[[SimpleNamespace], Any] | None

# (метод, шаблон у OpenAPI, шлях, тіло, роль із доступом, роль без доступу або None)
STUBS: list[tuple[str, str, Path, Body, str, str | None]] = [
    (
        "get",
        "/packs/manifest",
        lambda w: f"/packs/manifest?class_id={w.class_a.id}",
        None,
        "student_a",
        "parent_a",
    ),
    ("get", "/packs/{pack_id}", lambda w: f"/packs/{ANY_ID}", None, "teacher_a", "parent_a"),
    ("post", "/sync/events", lambda w: "/sync/events", lambda w: sync_body(), "student_a", "admin"),
    ("get", "/sync/changes", lambda w: "/sync/changes?cursor=0", None, "student_a", "teacher_a"),
    (
        "get",
        "/classes/{class_id}/rollcall/current",
        lambda w: f"/classes/{w.class_a.id}/rollcall/current",
        None,
        "teacher_a",
        "teacher_b",
    ),
    (
        "post",
        "/classes/{class_id}/rollcall",
        lambda w: f"/classes/{w.class_a.id}/rollcall",
        lambda w: {"id": str(uuid.uuid4())},
        "teacher_a",
        "student_a",
    ),
    (
        "post",
        "/classes/{class_id}/rollcall/{session_id}/close",
        lambda w: f"/classes/{w.class_a.id}/rollcall/{ANY_ID}/close",
        None,
        "teacher_a",
        "admin",
    ),
    (
        "get",
        "/students/{student_id}/rollcall/current",
        lambda w: f"/students/{w.student_a.id}/rollcall/current",
        None,
        "parent_a",
        "parent_free",
    ),
    (
        "post",
        "/alerts/manual",
        lambda w: "/alerts/manual",
        lambda w: {"id": str(uuid.uuid4()), "class_id": str(w.class_a.id), "is_drill": True},
        "teacher_a",
        "student_a",
    ),
    (
        "post",
        "/alerts/{alert_id}/end",
        lambda w: f"/alerts/{ANY_ID}/end",
        None,
        "teacher_a",
        "parent_a",
    ),
    ("get", "/alerts/active", lambda w: "/alerts/active", None, "parent_a", None),
    ("get", "/alerts", lambda w: "/alerts?limit=10", None, "admin", "teacher_a"),
    (
        "post",
        "/push/subscriptions",
        lambda w: "/push/subscriptions",
        lambda w: {
            "id": str(uuid.uuid4()),
            "endpoint": "https://push.example.com/abc",
            "keys": {"p256dh": "BNcRdreALRFX", "auth": "tBHI"},
        },
        "student_a",
        None,
    ),
    (
        "delete",
        "/push/subscriptions/{subscription_id}",
        lambda w: f"/push/subscriptions/{ANY_ID}",
        None,
        "parent_a",
        None,
    ),
    (
        "post",
        "/tutor/ask",
        lambda w: "/tutor/ask",
        lambda w: {"request_id": str(uuid.uuid4()), "mode": "explain_again", "lesson_id": ANY_ID},
        "student_a",
        "teacher_a",
    ),
]


async def _call(client: AsyncClient, method: str, url: str, body: Any, headers: dict) -> Any:
    kwargs: dict[str, Any] = {"headers": headers}
    if body is not None:
        kwargs["json"] = body
    return await client.request(method.upper(), url, **kwargs)


@pytest.mark.parametrize(
    ("method", "template", "path", "body", "allowed", "denied"),
    STUBS,
    ids=[f"{m.upper()} {t}" for m, t, *_ in STUBS],
)
async def test_stub_is_registered_protected_and_not_implemented(
    client: AsyncClient,
    app: FastAPI,
    world: SimpleNamespace,
    method: str,
    template: str,
    path: Path,
    body: Body,
    allowed: str,
    denied: str | None,
) -> None:
    # Описана в OpenAPI: 501 і успішна відповідь із прикладом для моків.
    operation = app.openapi()["paths"][template][method]
    assert "501" in operation["responses"]
    success = operation["responses"].get("201") or operation["responses"].get("200")
    if method != "delete":
        assert success["content"]["application/json"]["example"]

    url = path(world)
    data = body(world) if body else None
    assert (await _call(client, method, url, data, {})).status_code == 401
    if denied is not None:
        forbidden = await _call(client, method, url, data, auth_header(getattr(world, denied)))
        assert forbidden.status_code == 403, forbidden.text
    response = await _call(client, method, url, data, auth_header(getattr(world, allowed)))
    assert response.status_code == 501, response.text
    assert response.json()["error"]["code"] == "NOT_IMPLEMENTED"


async def test_sync_events_rejects_bad_envelope_but_not_unknown_type(
    client: AsyncClient, world: SimpleNamespace
) -> None:
    headers = auth_header(world.student_a)
    # Понад 100 подій — 422 для всього пакета.
    body = sync_body()
    body["events"] = body["events"] * 101
    assert (await client.post("/sync/events", json=body, headers=headers)).status_code == 422
    # Невідомий тип і довільний payload не ламають конверт: їх відхилить сервер по-подієво.
    body = sync_body()
    body["events"][0]["type"] = "future_type"
    body["events"][0]["payload"] = {"anything": 1}
    assert (await client.post("/sync/events", json=body, headers=headers)).status_code == 501
    # Час без часового поясу — невалідний конверт.
    body = sync_body()
    body["events"][0]["occurred_at"] = "2026-11-05T09:54:10"
    assert (await client.post("/sync/events", json=body, headers=headers)).status_code == 422


def test_payload_schemas_match_protocol() -> None:
    from pydantic import ValidationError

    from app.schemas.sync import PAYLOAD_MODELS

    PAYLOAD_MODELS["module_progress"].model_validate({"module_id": ANY_ID, "progress_pct": 100})
    PAYLOAD_MODELS["rollcall_status"].model_validate({"session_id": ANY_ID, "status": "safe"})
    PAYLOAD_MODELS["test_attempt"].model_validate(
        {"test_id": ANY_ID, "answers": {ANY_ID: ["a"]}, "completed_at": "2026-11-05T09:50:12Z"}
    )
    PAYLOAD_MODELS["survey_answer"].model_validate(
        {"survey_id": ANY_ID, "question_id": "q1", "value": 3}
    )
    bad = [
        ("module_progress", {"module_id": ANY_ID, "progress_pct": 101}),
        ("rollcall_status", {"session_id": ANY_ID, "status": "shelter"}),
        ("test_attempt", {"test_id": ANY_ID, "answers": {}, "score": 90}),
        ("survey_answer", {"survey_id": ANY_ID, "question_id": "q1", "value": "погано"}),
    ]
    for kind, payload in bad:
        with pytest.raises(ValidationError):
            PAYLOAD_MODELS[kind].model_validate(payload)
