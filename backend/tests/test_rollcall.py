"""Перекличка (B12): ручний старт і закриття, перегляд для вчителя (ETag/304), учня й батьків,
відмітки через синхронізацію (B9), ролі."""

import datetime as dt
import uuid

import pytest
from conftest import auth_header, pushes
from httpx import AsyncClient
from sqlalchemy import select

pytestmark = pytest.mark.anyio


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def start(client: AsyncClient, user, klass, session_id=None, **body):
    return await client.post(
        f"/classes/{klass.id}/rollcall",
        json={"id": str(session_id or uuid.uuid4()), **body},
        headers=auth_header(user),
    )


async def mark(client: AsyncClient, student, session_id, status: str, at=None) -> dict:
    at = at or now()
    body = {
        "sent_at": at.isoformat(),
        "events": [
            {
                "client_event_id": str(uuid.uuid4()),
                "type": "rollcall_status",
                "device_id": str(uuid.uuid4()),
                "occurred_at": at.isoformat(),
                "payload": {"session_id": str(session_id), "status": status},
            }
        ],
    }
    r = await client.post("/sync/events", json=body, headers=auth_header(student))
    assert r.status_code == 200, r.text
    return r.json()["results"][0]


async def test_teacher_starts_and_closes_idempotently(client, world) -> None:
    sid = uuid.uuid4()
    r = await start(client, world.teacher_a, world.class_a, sid, is_drill=True)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"] == str(sid) and body["is_drill"] is True and body["closed_at"] is None
    assert body["alert_event_id"] is None
    assert body["summary"] == {"safe": 0, "in_shelter": 0, "no_response": 1}
    # Повтор з тим самим id — 200, та сама сесія.
    again = await start(client, world.teacher_a, world.class_a, sid, is_drill=True)
    assert again.status_code == 200 and again.json()["opened_at"] == body["opened_at"]
    # Інший id, поки сесія відкрита — 409 з id відкритої.
    other = await start(client, world.teacher_a, world.class_a)
    assert other.status_code == 409
    assert other.json()["error"] == {
        "code": "ROLLCALL_ALREADY_OPEN",
        "message": "Another roll call is already open for this class",
        "details": {"session_id": str(sid)},
    }
    # Той самий id з іншими даними — ID_CONFLICT.
    conflict = await start(client, world.teacher_a, world.class_a, sid, is_drill=False)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "ID_CONFLICT"

    url = f"/classes/{world.class_a.id}/rollcall/{sid}/close"
    closed = await client.post(url, headers=auth_header(world.teacher_a))
    assert closed.status_code == 200 and closed.json()["closed_at"] is not None
    repeat = await client.post(url, headers=auth_header(world.teacher_a))
    assert repeat.status_code == 200 and repeat.json()["closed_at"] == closed.json()["closed_at"]
    # Після закриття можна відкрити нову.
    assert (await start(client, world.teacher_a, world.class_a)).status_code == 201


async def test_close_session_of_another_class_is_404(client, world) -> None:
    sid = uuid.uuid4()
    assert (await start(client, world.teacher_b, world.class_b, sid)).status_code == 201
    # Вчитель класу A не закриє сесію класу B через свій клас.
    url = f"/classes/{world.class_a.id}/rollcall/{sid}/close"
    assert (await client.post(url, headers=auth_header(world.teacher_a))).status_code == 404
    missing = f"/classes/{world.class_a.id}/rollcall/{uuid.uuid4()}/close"
    assert (await client.post(missing, headers=auth_header(world.teacher_a))).status_code == 404


async def test_start_and_close_roles(client, world) -> None:
    for user in (world.student_a, world.admin, world.parent_a, world.teacher_b):
        assert (await start(client, user, world.class_a)).status_code == 403
    sid = uuid.uuid4()
    await start(client, world.teacher_a, world.class_a, sid)
    url = f"/classes/{world.class_a.id}/rollcall/{sid}/close"
    for user in (world.student_a, world.admin, world.parent_a, world.teacher_b):
        assert (await client.post(url, headers=auth_header(user))).status_code == 403
    assert (await client.post(url)).status_code == 401


async def test_teacher_sees_class_statuses_student_sees_self(client, world, factory) -> None:
    second = await factory.student(world.class_a, "Оксана", "Андрієнко")
    third = await factory.student(world.class_a, "Петро", "Яковенко")
    sid = uuid.UUID((await start(client, world.teacher_a, world.class_a)).json()["id"])
    t = now()
    assert (await mark(client, world.student_a, sid, "in_shelter", t))["status"] == "accepted"
    assert (await mark(client, second, sid, "safe", t))["status"] == "accepted"

    url = f"/classes/{world.class_a.id}/rollcall/current"
    r = await client.get(url, headers=auth_header(world.teacher_a))
    assert r.status_code == 200
    session = r.json()["session"]
    assert session["summary"] == {"safe": 1, "in_shelter": 1, "no_response": 1}
    by_id = {s["student_id"]: s for s in session["students"]}
    assert by_id[str(world.student_a.id)]["status"] == "in_shelter"
    assert by_id[str(world.student_a.id)]["received_at"] is not None
    assert by_id[str(second.id)]["status"] == "safe"
    assert by_id[str(third.id)] == {
        "student_id": str(third.id),
        "display_name": "Петро",
        "last_name": "Яковенко",
        "status": "no_response",
        "occurred_at": None,
        "received_at": None,
    }
    # Сортування за прізвищем.
    assert [s["last_name"] for s in session["students"]] == ["Андрієнко", "Петренко", "Яковенко"]

    # Адмін школи — теж увесь клас; учень — лише себе.
    r = await client.get(url, headers=auth_header(world.admin))
    assert len(r.json()["session"]["students"]) == 3
    r = await client.get(url, headers=auth_header(third))
    mine = r.json()["session"]
    assert [s["student_id"] for s in mine["students"]] == [str(third.id)]
    assert mine["summary"] == {"safe": 0, "in_shelter": 0, "no_response": 1}


async def test_current_roles_and_empty(client, world) -> None:
    url = f"/classes/{world.class_a.id}/rollcall/current"
    r = await client.get(url, headers=auth_header(world.teacher_a))
    assert r.status_code == 200 and r.json() == {"class_id": str(world.class_a.id), "session": None}
    for user in (world.teacher_b, world.student_b, world.parent_a, world.other_admin):
        assert (await client.get(url, headers=auth_header(user))).status_code == 403
    assert (await client.get(url)).status_code == 401


async def test_polling_with_etag(client, world) -> None:
    url = f"/classes/{world.class_a.id}/rollcall/current"
    headers = auth_header(world.teacher_a)
    sid = uuid.UUID((await start(client, world.teacher_a, world.class_a)).json()["id"])
    first = await client.get(url, headers=headers)
    etag = first.headers["ETag"]
    assert first.headers["Cache-Control"] == "private, no-cache"
    cached = await client.get(url, headers={**headers, "If-None-Match": etag})
    assert cached.status_code == 304 and cached.content == b""
    await mark(client, world.student_a, sid, "safe")
    changed = await client.get(url, headers={**headers, "If-None-Match": etag})
    assert changed.status_code == 200 and changed.headers["ETag"] != etag
    assert changed.json()["session"]["summary"]["safe"] == 1


async def test_parent_sees_only_own_child(client, world) -> None:
    url = f"/students/{world.student_a.id}/rollcall/current"
    r = await client.get(url, headers=auth_header(world.parent_a))
    assert r.status_code == 200
    assert r.json() == {
        "student_id": str(world.student_a.id),
        "session_id": None,
        "is_drill": None,
        "opened_at": None,
        "status": None,
        "occurred_at": None,
        "received_at": None,
    }
    sid = uuid.UUID((await start(client, world.teacher_a, world.class_a)).json()["id"])
    r = await client.get(url, headers=auth_header(world.parent_a))
    assert r.json()["session_id"] == str(sid) and r.json()["status"] == "no_response"
    await mark(client, world.student_a, sid, "in_shelter")
    r = await client.get(url, headers=auth_header(world.parent_a))
    assert r.json()["status"] == "in_shelter" and r.json()["is_drill"] is False

    for user in (world.parent_free, world.student_b, world.teacher_b, world.other_admin):
        assert (await client.get(url, headers=auth_header(user))).status_code == 403
    for user in (world.student_a, world.teacher_a, world.admin):
        assert (await client.get(url, headers=auth_header(user))).status_code == 200


async def test_alert_opens_session_student_marks_teacher_sees(client, world, enqueued) -> None:
    """Головний сценарій: ручна тривога → перекличка → відмітка подією → вчитель бачить."""
    r = await client.post(
        "/alerts/manual",
        json={"id": str(uuid.uuid4()), "class_id": str(world.class_a.id)},
        headers=auth_header(world.teacher_a),
    )
    assert r.status_code == 201, r.text
    url = f"/classes/{world.class_a.id}/rollcall/current"
    student_view = (await client.get(url, headers=auth_header(world.student_a))).json()
    sid = student_view["session"]["id"]
    assert student_view["session"]["alert_event_id"] == r.json()["id"]
    assert (await mark(client, world.student_a, sid, "in_shelter"))["status"] == "accepted"
    session = (await client.get(url, headers=auth_header(world.teacher_a))).json()["session"]
    assert session["summary"]["in_shelter"] == 1


async def test_manual_start_during_alert_belongs_to_alert_and_closes_with_all_clear(
    client, world, db_session, enqueued
) -> None:
    """Тривога з API почалась на перерві (переклички немає), вчитель відкриває її вручну:
    сесія належить тривозі, тож відбій її закриває й шле `all_clear`, а не лишає відкритою
    зі старими відмітками до наступної тривоги."""
    from app.models.alerts import AlertEvent
    from app.services import alerts as alerts_service
    from app.services.alert_provider import ActiveAlerts, AlertProvider, ProviderAlert

    class Provider(AlertProvider):
        name = "alerts.in.ua"
        alerts: list[ProviderAlert] = []

        async def active_alerts(self) -> ActiveAlerts:
            return ActiveAlerts(list(self.alerts), complete=True)

    provider = Provider()
    provider.alerts = [ProviderAlert("777", "oblast", "kyiv", now() - dt.timedelta(minutes=5))]
    await alerts_service.poll(db_session, provider)
    alert = await db_session.scalar(
        select(AlertEvent).where(AlertEvent.school_id == world.school.id)
    )
    r = await start(client, world.teacher_a, world.class_a)
    assert r.status_code == 201, r.text
    assert r.json()["alert_event_id"] == str(alert.id)
    # Навчальна перекличка під час справжньої тривоги до неї не прив'язується.
    r_b = await start(client, world.teacher_b, world.class_b, is_drill=True)
    assert r_b.json()["alert_event_id"] is None
    await mark(client, world.student_a, r.json()["id"], "in_shelter")

    provider.alerts = []
    await alerts_service.poll(db_session, provider)
    url = f"/classes/{world.class_a.id}/rollcall/current"
    assert (await client.get(url, headers=auth_header(world.teacher_a))).json()["session"] is None
    assert [p["class_id"] for p in pushes(enqueued, "all_clear")] == [str(world.class_a.id)]


# ---------- push батькам при зміні статусу (B12.4) ----------


def batch_of(*events) -> dict:
    return {"sent_at": now().isoformat(), "events": list(events)}


def rc_event(session_id, status: str, at: dt.datetime, event_id=None) -> dict:
    return {
        "client_event_id": str(event_id or uuid.uuid4()),
        "type": "rollcall_status",
        "device_id": str(uuid.uuid4()),
        "occurred_at": at.isoformat(),
        "payload": {"session_id": str(session_id), "status": status},
    }


async def test_status_change_pushes_parents_once(client, world, enqueued) -> None:
    sid = uuid.uuid4()
    assert (await start(client, world.teacher_a, world.class_a, sid)).status_code == 201
    t0 = now()
    await mark(client, world.student_a, sid, "in_shelter", t0)
    expected = {
        "type": "rollcall_status",
        "student_id": str(world.student_a.id),
        "session_id": str(sid),
        "status": "in_shelter",
    }
    assert pushes(enqueued, "rollcall_status") == [expected]
    call = next(c for c in enqueued if c.name == "push.send")
    assert call.queue == "push" and call.args[1].startswith("rollcall_status:")
    # Той самий статус ще раз (інша подія) — без push; повтор тієї ж події — duplicate, без push.
    await mark(client, world.student_a, sid, "in_shelter", t0 + dt.timedelta(seconds=5))
    assert len(pushes(enqueued, "rollcall_status")) == 1
    # Стара подія (раніший occurred_at) з іншим статусом не перемагає — без push.
    await mark(client, world.student_a, sid, "safe", t0 - dt.timedelta(minutes=1))
    assert len(pushes(enqueued, "rollcall_status")) == 1
    # Справжня зміна — новий push.
    await mark(client, world.student_a, sid, "safe", t0 + dt.timedelta(seconds=10))
    assert pushes(enqueued, "rollcall_status")[-1] == {**expected, "status": "safe"}
    assert len(pushes(enqueued, "rollcall_status")) == 2


async def test_repeated_batch_does_not_push_again(client, world, enqueued) -> None:
    sid = uuid.uuid4()
    await start(client, world.teacher_a, world.class_a, sid)
    body = batch_of(rc_event(sid, "in_shelter", now()))
    headers = auth_header(world.student_a)
    for _ in range(2):
        r = await client.post("/sync/events", json=body, headers=headers)
        assert r.status_code == 200
    assert r.json()["results"][0]["status"] == "duplicate"
    assert len(pushes(enqueued, "rollcall_status")) == 1


async def test_batch_with_several_changes_pushes_latest_status(client, world, enqueued) -> None:
    sid = uuid.uuid4()
    await start(client, world.teacher_a, world.class_a, sid)
    t0 = now() - dt.timedelta(minutes=5)
    body = batch_of(
        rc_event(sid, "safe", t0 + dt.timedelta(minutes=1)),
        rc_event(sid, "in_shelter", t0),
    )
    r = await client.post("/sync/events", json=body, headers=auth_header(world.student_a))
    assert [x["status"] for x in r.json()["results"]] == ["accepted", "accepted"]
    assert [p["status"] for p in pushes(enqueued, "rollcall_status")] == ["safe"]


async def test_batch_returning_to_previous_status_does_not_push(client, world, enqueued) -> None:
    """A→B→A в одному пакеті: для батьків статус не змінився — push немає. A→B→A→B — є."""
    sid = uuid.uuid4()
    await start(client, world.teacher_a, world.class_a, sid)
    t0 = now() - dt.timedelta(minutes=10)
    await mark(client, world.student_a, sid, "in_shelter", t0)
    assert len(pushes(enqueued, "rollcall_status")) == 1
    body = batch_of(
        rc_event(sid, "safe", t0 + dt.timedelta(minutes=1)),
        rc_event(sid, "in_shelter", t0 + dt.timedelta(minutes=2)),
    )
    r = await client.post("/sync/events", json=body, headers=auth_header(world.student_a))
    assert [x["status"] for x in r.json()["results"]] == ["accepted", "accepted"]
    assert len(pushes(enqueued, "rollcall_status")) == 1
    body = batch_of(
        rc_event(sid, "safe", t0 + dt.timedelta(minutes=3)),
        rc_event(sid, "in_shelter", t0 + dt.timedelta(minutes=4)),
        rc_event(sid, "safe", t0 + dt.timedelta(minutes=5)),
    )
    r = await client.post("/sync/events", json=body, headers=auth_header(world.student_a))
    assert [p["status"] for p in pushes(enqueued, "rollcall_status")] == ["in_shelter", "safe"]


async def test_no_push_for_closed_session_or_rejected_event(client, world, enqueued) -> None:
    sid = uuid.uuid4()
    t0 = now()
    await start(client, world.teacher_a, world.class_a, sid)
    url = f"/classes/{world.class_a.id}/rollcall/{sid}/close"
    assert (await client.post(url, headers=auth_header(world.teacher_a))).status_code == 200
    # Офлайн-відмітка до закриття приймається, але push батькам уже не йде.
    result = await mark(client, world.student_a, sid, "safe", t0)
    assert result["status"] == "accepted"
    # Учень іншого класу — forbidden, push немає.
    sid_b = uuid.uuid4()
    await start(client, world.teacher_a, world.class_a, sid_b)
    result = await mark(client, world.student_b, sid_b, "safe")
    assert result["reason"] == "forbidden"
    assert pushes(enqueued, "rollcall_status") == []
