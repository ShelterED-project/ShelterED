"""Ретрансляція вчителем (локальний сервер укриття): відмітки переклички учнів його класів
через `POST /sync/events` зі `student_id` у кожній події (docs/sync-protocol.md)."""

import datetime as dt
import uuid

import pytest
from conftest import auth_header, pushes
from test_sync import (
    attempt,
    batch,
    changes,
    committed_world,
    content,
    count,
    now,
    progress,
    rollcall,
    send,
    statuses,
)

from app.models.rollcall import RollCallStatus
from app.models.sync import SyncEvent

pytestmark = pytest.mark.anyio


def relayed(event: dict, student) -> dict:
    return {**event, "student_id": str(student.id)}


@pytest.fixture
async def c(db_session, factory, world):
    return await content(db_session, factory, world.class_a, world.teacher_a)


async def current(client, klass, user) -> dict:
    r = await client.get(f"/classes/{klass.id}/rollcall/current", headers=auth_header(user))
    assert r.status_code == 200, r.text
    return r.json()


async def test_teacher_relays_mark_of_own_class_student(
    client, db_session, world, c, enqueued
) -> None:
    e = relayed(rollcall(c.rc.id, "in_shelter", now()), world.student_a)
    assert statuses(await send(client, world.teacher_a, batch(e))) == [("accepted", None)]

    stored = await db_session.get(SyncEvent, uuid.UUID(e["client_event_id"]))
    assert stored.user_id == world.student_a.id
    assert stored.relayed_by == world.teacher_a.id
    assert stored.source == "local"
    status = await db_session.get(RollCallStatus, (c.rc.id, world.student_a.id))
    assert status.status == "in_shelter"

    view = (await current(client, world.class_a, world.teacher_a))["session"]
    assert view["summary"]["in_shelter"] == 1
    mine = [s for s in view["students"] if s["student_id"] == str(world.student_a.id)]
    assert mine[0]["status"] == "in_shelter"
    # Як від самого учня: push батькам про його статус і перерахунок агрегатів учня.
    assert [(p["student_id"], p["status"]) for p in pushes(enqueued, "rollcall_status")] == [
        (str(world.student_a.id), "in_shelter")
    ]
    assert [call.args for call in enqueued if call.name == "stats.recompute_student"] == [
        [str(world.student_a.id)]
    ]


async def test_relay_access_rules(client, db_session, factory, world, c) -> None:
    other = await content(db_session, factory, world.class_b, world.teacher_b)
    results = await send(
        client,
        world.teacher_a,
        batch(
            # Учень іншого класу в сесію класу вчителя.
            relayed(rollcall(c.rc.id, "safe", now()), world.student_b),
            # Сесія класу, якого вчитель не веде (учень того класу).
            relayed(rollcall(other.rc.id, "safe", now()), world.student_b),
            # Невідомий учень.
            relayed(rollcall(c.rc.id, "safe", now()), world.teacher_a),
            # Невідома сесія.
            relayed(rollcall(uuid.uuid4(), "safe", now()), world.student_a),
            # Без student_id.
            rollcall(c.rc.id, "safe", now()),
            # Інші типи — потрібен підписаний запис учня (B10).
            relayed(progress(c.module.id, 50), world.student_a),
            relayed(attempt(c.test.id, {c.q1.id: ["a"]}, now()), world.student_a),
        ),
    )
    assert statuses(results) == [
        ("rejected", "forbidden"),
        ("rejected", "forbidden"),
        ("rejected", "forbidden"),
        ("rejected", "unknown_entity"),
        ("rejected", "student_id_required"),
        ("rejected", "relay_not_supported"),
        ("rejected", "relay_not_supported"),
    ]
    # Без перевіреного учня в журнал нічого не пишеться, статусів немає.
    assert await count(db_session, SyncEvent) == 0
    assert await count(db_session, RollCallStatus) == 0


async def test_relay_same_batch_twice_and_mixed_batch(
    client, db_session, factory, world, c
) -> None:
    second = await factory.student(world.class_a, "Олег", "Ткач")
    t = now()
    good = relayed(rollcall(c.rc.id, "safe", t), world.student_a)
    body = batch(
        good,
        relayed(rollcall(c.rc.id, "in_shelter", t), second),
        relayed(rollcall(c.rc.id, "safe", t), world.student_b),
        relayed(progress(c.module.id, 10), world.student_a),
    )
    first = statuses(await send(client, world.teacher_a, body))
    assert first == [
        ("accepted", None),
        ("accepted", None),
        ("rejected", "forbidden"),
        ("rejected", "relay_not_supported"),
    ]
    again = statuses(await send(client, world.teacher_a, body))
    assert again == [
        ("duplicate", None),
        ("duplicate", None),
        ("rejected", "forbidden"),
        ("rejected", "relay_not_supported"),
    ]
    assert await count(db_session, SyncEvent) == 2
    assert await count(db_session, RollCallStatus) == 2
    # Та сама подія, що дійшла й напряму від учня (телефон отримав мережу), — дубль.
    direct = {k: v for k, v in good.items() if k != "student_id"}
    assert statuses(await send(client, world.student_a, batch(direct))) == [("duplicate", None)]


async def test_relay_latest_occurred_at_wins_against_direct_mark(
    client, db_session, world, c
) -> None:
    t = now()
    await send(client, world.student_a, batch(rollcall(c.rc.id, "safe", t)))
    older = relayed(rollcall(c.rc.id, "in_shelter", t - dt.timedelta(minutes=5)), world.student_a)
    assert statuses(await send(client, world.teacher_a, batch(older))) == [("accepted", None)]
    status = await db_session.get(RollCallStatus, (c.rc.id, world.student_a.id))
    await db_session.refresh(status)
    assert status.status == "safe"
    newer = relayed(rollcall(c.rc.id, "in_shelter", t + dt.timedelta(minutes=1)), world.student_a)
    assert statuses(await send(client, world.teacher_a, batch(newer))) == [("accepted", None)]
    await db_session.refresh(status)
    assert status.status == "in_shelter"


async def test_relay_after_close_uses_occurred_at(client, db_session, world, c) -> None:
    closed_at = now() - dt.timedelta(minutes=10)
    c.rc.closed_at = closed_at
    await db_session.flush()
    before = relayed(
        rollcall(c.rc.id, "safe", closed_at - dt.timedelta(minutes=5)), world.student_a
    )
    after = relayed(
        rollcall(c.rc.id, "in_shelter", closed_at + dt.timedelta(minutes=5)), world.student_a
    )
    results = await send(client, world.teacher_a, batch(before, after))
    assert statuses(results) == [("accepted", None), ("rejected", "session_closed")]
    # `session_closed` — учня перевірено, тож відмова записана як його подія.
    row = await db_session.get(SyncEvent, uuid.UUID(after["client_event_id"]))
    assert (row.user_id, row.status, row.source) == (world.student_a.id, "rejected", "local")


async def test_parent_and_admin_cannot_send(client, world, c) -> None:
    body = batch(relayed(rollcall(c.rc.id, "safe", now()), world.student_a))
    for user in (world.parent_a, world.admin):
        r = await client.post("/sync/events", json=body, headers=auth_header(user))
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"


async def test_student_with_student_id(client, db_session, world, c) -> None:
    own = relayed(rollcall(c.rc.id, "safe", now()), world.student_a)
    foreign = relayed(rollcall(c.rc.id, "in_shelter", now()), world.student_b)
    results = await send(client, world.student_a, batch(own, foreign))
    assert statuses(results) == [("accepted", None), ("rejected", "forbidden")]
    row = await db_session.get(SyncEvent, uuid.UUID(own["client_event_id"]))
    assert (row.user_id, row.source, row.relayed_by) == (world.student_a.id, "online", None)
    assert await count(db_session, RollCallStatus) == 1


async def test_offline_session_created_later_accepts_earlier_marks(
    client, db_session, world
) -> None:
    """Локальний сервер відкрив перекличку офлайн із власним id і зібрав відмітки; у хмарі
    сесія створюється пізніше (`POST /classes/{id}/rollcall`, той самий id), і відмітки з
    `occurred_at` до її `opened_at` приймаються."""
    session_id = uuid.uuid4()
    marked_at = now() - dt.timedelta(minutes=40)
    headers = auth_header(world.teacher_a)
    r = await client.post(
        f"/classes/{world.class_a.id}/rollcall", json={"id": str(session_id)}, headers=headers
    )
    assert r.status_code == 201, r.text
    opened_at = dt.datetime.fromisoformat(r.json()["opened_at"])
    assert marked_at < opened_at
    r = await client.post(
        f"/classes/{world.class_a.id}/rollcall", json={"id": str(session_id)}, headers=headers
    )
    assert r.status_code == 200
    e = relayed(rollcall(session_id, "in_shelter", marked_at), world.student_a)
    assert statuses(await send(client, world.teacher_a, batch(e))) == [("accepted", None)]
    view = (await current(client, world.class_a, world.teacher_a))["session"]
    assert view["id"] == str(session_id)
    assert view["summary"]["in_shelter"] == 1


async def test_rollcall_already_open_returns_session_id(client, db_session, world, c) -> None:
    """Локальний сервер покладається на `details.session_id`, щоб пересилати в наявну сесію."""
    r = await client.post(
        f"/classes/{world.class_a.id}/rollcall",
        json={"id": str(uuid.uuid4())},
        headers=auth_header(world.teacher_a),
    )
    assert r.status_code == 409
    error = r.json()["error"]
    assert error["code"] == "ROLLCALL_ALREADY_OPEN"
    assert error["details"]["session_id"] == str(c.rc.id)


# ---------- справжні commit-и: стрічка змін учня ----------


async def test_relayed_mark_appears_in_student_changes_feed(committed) -> None:
    w = await committed_world(committed)
    at = now() - dt.timedelta(minutes=1)
    e = relayed(rollcall(w.c.rc.id, "in_shelter", at), w.student)
    r = await committed.client.post("/sync/events", json=batch(e), headers=auth_header(w.teacher))
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "accepted", r.text
    feed = await changes(committed, w.student)
    marks = [ch for ch in feed["changes"] if ch["kind"] == "rollcall_status"]
    assert [(m["session_id"], m["status"]) for m in marks] == [(str(w.c.rc.id), "in_shelter")]
    # Чужому учневі відмітка не видна.
    other = await changes(committed, w.other)
    assert not [ch for ch in other["changes"] if ch["kind"] == "rollcall_status"]


async def test_class_students_roster_for_teacher_only(client, world) -> None:
    klass = world.class_a
    resp = await client.get(f"/classes/{klass.id}/students", headers=auth_header(world.teacher_a))
    assert resp.status_code == 200, resp.text
    ids = {s["student_id"] for s in resp.json()}
    assert str(world.student_a.id) in ids
    assert set(resp.json()[0]) == {"student_id", "display_name", "last_name"}
    for user in (world.student_a, world.parent_a, world.teacher_b):
        r = await client.get(f"/classes/{klass.id}/students", headers=auth_header(user))
        assert r.status_code == 403, (user.role, r.status_code)
