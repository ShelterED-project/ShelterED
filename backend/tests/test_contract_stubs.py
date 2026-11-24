"""Контракт B4: перевірка конверта синхронізації й схем payload (заглушок 501 більше немає)."""

import uuid
from types import SimpleNamespace

import pytest
from conftest import auth_header
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
    response = await client.post("/sync/events", json=body, headers=headers)
    assert response.status_code == 200
    assert response.json()["results"][0]["reason"] == "unknown_type"
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
    PAYLOAD_MODELS["survey_answer"].model_validate({"value": 3})
    bad = [
        ("module_progress", {"module_id": ANY_ID, "progress_pct": 101}),
        ("rollcall_status", {"session_id": ANY_ID, "status": "shelter"}),
        ("test_attempt", {"test_id": ANY_ID, "answers": {}, "score": 90}),
        ("survey_answer", {"value": "погано"}),
        ("survey_answer", {"value": 0}),
        ("survey_answer", {"value": 6}),
        ("survey_answer", {"value": True}),
        ("survey_answer", {"value": 3, "question_id": "q1"}),
    ]
    for kind, payload in bad:
        with pytest.raises(ValidationError):
            PAYLOAD_MODELS[kind].model_validate(payload)
