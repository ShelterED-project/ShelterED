"""Синхронізація (docs/sync-protocol.md v1): прийом пакета, конфлікти, ролі, стрічка змін,
обрив мережі, паралельний повтор, запізніла подія, збій посеред пакета."""

import asyncio
import datetime as dt
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from conftest import auth_header
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lessons import Lesson, Module, Question, Test
from app.models.rollcall import RollCallSession, RollCallStatus
from app.models.school import LessonAssignment, ScheduleSlot
from app.models.sync import Attempt, ModuleProgress, SyncEvent
from app.services import sync as sync_service

pytestmark = pytest.mark.anyio

DEVICE = str(uuid.uuid4())


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def iso(t: dt.datetime) -> str:
    return t.isoformat().replace("+00:00", "Z")


def event(kind: str, payload: dict[str, Any], at: dt.datetime | None = None, **kw) -> dict:
    return {
        "client_event_id": kw.get("id", str(uuid.uuid4())),
        "type": kind,
        "device_id": DEVICE,
        "occurred_at": iso(at or now()),
        "payload": payload,
    }


def batch(*events: dict, sent_at: dt.datetime | None = None) -> dict:
    return {"sent_at": iso(sent_at or now()), "events": list(events)}


def progress(module_id, pct: int, at=None, completed=None, **kw) -> dict:
    payload: dict[str, Any] = {"module_id": str(module_id), "progress_pct": pct}
    if completed is not None:
        payload["completed_at"] = iso(completed)
    return event("module_progress", payload, at, **kw)


def attempt(test_id, answers: dict, completed: dt.datetime, **kw) -> dict:
    payload = {
        "test_id": str(test_id),
        "answers": {str(k): v for k, v in answers.items()},
        "completed_at": iso(completed),
    }
    return event("test_attempt", payload, completed, **kw)


def rollcall(session_id, status: str, at: dt.datetime, **kw) -> dict:
    return event("rollcall_status", {"session_id": str(session_id), "status": status}, at, **kw)


async def count(db: AsyncSession, model, *where) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*where)) or 0


async def content(db: AsyncSession, factory, klass, teacher) -> SimpleNamespace:
    """Опублікований урок класу (прив'язаний до розкладу): модуль і тест із 2 питаннями."""
    subject = await factory.subject()
    today = dt.date.today()
    slot = ScheduleSlot(
        class_id=klass.id,
        subject_id=subject.id,
        weekday=today.isoweekday(),
        starts_at=dt.time(9, 0),
        ends_at=dt.time(9, 45),
        valid_from=today - dt.timedelta(days=7),
    )
    lesson = Lesson(
        subject_id=subject.id,
        author_id=teacher.id,
        title="Дроби",
        shelter_part="Укриття",
        main_part="Основна",
        status="published",
        published_at=now(),
    )
    db.add_all([slot, lesson])
    await db.flush()
    db.add(LessonAssignment(slot_id=slot.id, date=today, lesson_id=lesson.id))
    module = Module(lesson_id=lesson.id, part="shelter", position=1, title="М1", duration_min=4)
    test = Test(lesson_id=lesson.id, title="Тест")
    db.add_all([module, test])
    await db.flush()
    q1 = Question(
        test_id=test.id,
        position=1,
        kind="single",
        prompt="1/2 + 1/2?",
        options=[{"id": "a", "text": "1"}, {"id": "b", "text": "2"}],
        answer_key=["a"],
        points=1,
    )
    q2 = Question(
        test_id=test.id,
        position=2,
        kind="multiple",
        prompt="Парні?",
        options=[{"id": "a", "text": "2"}, {"id": "b", "text": "3"}, {"id": "c", "text": "4"}],
        answer_key=["a", "c"],
        points=3,
    )
    rc = RollCallSession(class_id=klass.id, opened_at=now() - dt.timedelta(minutes=30))
    db.add_all([q1, q2, rc])
    await db.flush()
    return SimpleNamespace(lesson=lesson, module=module, test=test, q1=q1, q2=q2, rc=rc)


@pytest.fixture
async def c(db_session, factory, world) -> SimpleNamespace:
    return await content(db_session, factory, world.class_a, world.teacher_a)


async def send(client: AsyncClient, user, body: dict) -> list[dict]:
    response = await client.post("/sync/events", json=body, headers=auth_header(user))
    assert response.status_code == 200, response.text
    return response.json()["results"]


def statuses(results: list[dict]) -> list[tuple[str, str | None]]:
    return [(r["status"], r["reason"]) for r in results]


# ---------- прийом і ідемпотентність ----------


async def test_batch_accepts_each_type_and_returns_results_in_request_order(
    client, db_session, world, c
) -> None:
    events = [
        rollcall(c.rc.id, "in_shelter", now()),
        progress(c.module.id, 50, now() - dt.timedelta(minutes=5)),
        attempt(c.test.id, {c.q1.id: ["a"]}, now() - dt.timedelta(minutes=1)),
        event("survey_answer", {"survey_id": str(uuid.uuid4()), "question_id": "q1", "value": 7}),
    ]
    results = await send(client, world.student_a, batch(*events))
    assert [r["client_event_id"] for r in results] == [e["client_event_id"] for e in events]
    assert statuses(results) == [("accepted", None)] * 4
    assert await count(db_session, SyncEvent, SyncEvent.user_id == world.student_a.id) == 4
    row = await db_session.get(SyncEvent, uuid.UUID(events[0]["client_event_id"]))
    assert row.status == "accepted" and row.source == "online" and not row.is_suspicious
    assert row.device_id == uuid.UUID(DEVICE)


async def test_retry_after_lost_response_gives_duplicate_and_one_record(
    client, db_session, world, c
) -> None:
    """Обрив мережі до відповіді: сервер усе записав, клієнт не знає й шле пакет ще раз."""
    body = batch(
        progress(c.module.id, 40),
        attempt(c.test.id, {c.q1.id: ["a"]}, now()),
        rollcall(c.rc.id, "safe", now()),
    )
    await send(client, world.student_a, body)  # відповідь «загубилась»
    results = await send(client, world.student_a, body)
    assert statuses(results) == [("duplicate", None)] * 3
    assert await count(db_session, SyncEvent) == 3
    assert await count(db_session, Attempt) == 1
    assert await count(db_session, ModuleProgress) == 1
    assert await count(db_session, RollCallStatus) == 1


async def test_same_id_twice_in_one_batch(client, db_session, world, c) -> None:
    e = progress(c.module.id, 30)
    results = await send(client, world.student_a, batch(e, dict(e)))
    assert statuses(results) == [("accepted", None), ("duplicate", None)]
    assert await count(db_session, SyncEvent) == 1


async def test_rejections_with_reasons_are_stored_and_repeat_the_same(
    client, db_session, world, factory, c
) -> None:
    other = await content(db_session, factory, world.class_b, world.teacher_b)
    closed = RollCallSession(
        class_id=world.class_a.id,
        opened_at=now() - dt.timedelta(hours=3),
        closed_at=now() - dt.timedelta(hours=2),
    )
    db_session.add(closed)
    await db_session.flush()
    events = [
        event("future_type", {"x": 1}),
        progress(c.module.id, 101),
        event("test_attempt", {"test_id": str(c.test.id), "answers": {}, "score": 100}),
        progress(uuid.uuid4(), 10),
        attempt(uuid.uuid4(), {}, now()),
        rollcall(uuid.uuid4(), "safe", now()),
        progress(other.module.id, 10),
        attempt(other.test.id, {}, now()),
        rollcall(other.rc.id, "safe", now()),
        rollcall(closed.id, "safe", now()),
    ]
    expected = [
        ("rejected", "unknown_type"),
        ("rejected", "invalid_payload"),
        ("rejected", "invalid_payload"),
        ("rejected", "unknown_entity"),
        ("rejected", "unknown_entity"),
        ("rejected", "unknown_entity"),
        ("rejected", "forbidden"),
        ("rejected", "forbidden"),
        ("rejected", "forbidden"),
        ("rejected", "session_closed"),
    ]
    good = progress(c.module.id, 20)
    results = await send(client, world.student_a, batch(*events, good))
    assert statuses(results) == [*expected, ("accepted", None)]
    # Відхилені записані (крім невідомого типу — його не пускає CHECK); нічого не застосовано.
    assert await count(db_session, SyncEvent, SyncEvent.status == "rejected") == 9
    assert await count(db_session, Attempt) == 0
    assert await count(db_session, RollCallStatus) == 0
    # Повтор дає той самий результат.
    again = await send(client, world.student_a, batch(*events, good))
    assert statuses(again) == [*expected, ("duplicate", None)]


async def test_status_before_closing_is_accepted_after_closing(
    client, db_session, world, c
) -> None:
    """Учень відмітився офлайн до відбою, подія прийшла після закриття — приймається."""
    c.rc.closed_at = now() - dt.timedelta(minutes=1)
    await db_session.flush()
    results = await send(
        client, world.student_a, batch(rollcall(c.rc.id, "safe", now() - dt.timedelta(minutes=5)))
    )
    assert statuses(results) == [("accepted", None)]


async def test_mark_before_closing_by_server_time_survives_fast_device_clock(
    client, db_session, world, factory, c
) -> None:
    """Годинник телефона на 10 хв уперед: відмітка за 5 хв до закриття (за часом сервера)
    має `occurred_at` після закриття, але з поправкою на зсув пакета приймається. Відмітка в
    межах допуску після закриття — теж; явно пізня (і за пристроєм, і з поправкою) — ні."""
    closed_at = now() - dt.timedelta(minutes=1)
    c.rc.closed_at = closed_at
    await db_session.flush()
    ahead = dt.timedelta(minutes=10)
    mark = rollcall(c.rc.id, "in_shelter", closed_at - dt.timedelta(minutes=5) + ahead)
    results = await send(client, world.student_a, batch(mark, sent_at=now() + ahead))
    assert statuses(results) == [("accepted", None)]
    status = await db_session.get(RollCallStatus, (c.rc.id, world.student_a.id))
    assert status.status == "in_shelter"

    second = await factory.student(world.class_a, "Олег", "Мельник")
    grace = rollcall(c.rc.id, "safe", closed_at + dt.timedelta(seconds=60))
    assert statuses(await send(client, second, batch(grace))) == [("accepted", None)]
    late = rollcall(c.rc.id, "safe", closed_at + dt.timedelta(minutes=10))
    results = await send(client, second, batch(late, sent_at=now()))
    assert statuses(results) == [("rejected", "session_closed")]


async def test_foreign_event_id_is_not_overwritten(client, db_session, world, c) -> None:
    e = progress(c.module.id, 10)
    await send(client, world.student_a, batch(e))
    student2 = world.student_b
    results = await send(client, student2, batch(e))
    assert statuses(results) == [("rejected", "forbidden")]
    row = await db_session.get(SyncEvent, uuid.UUID(e["client_event_id"]))
    assert row.user_id == world.student_a.id


async def test_envelope_errors_are_422(client, world, c) -> None:
    headers = auth_header(world.student_a)
    body = batch(progress(c.module.id, 10))
    body["events"] = body["events"] * 101
    assert (await client.post("/sync/events", json=body, headers=headers)).status_code == 422
    body = batch(progress(c.module.id, 10))
    body["events"][0]["occurred_at"] = "2026-11-05T09:54:10"
    assert (await client.post("/sync/events", json=body, headers=headers)).status_code == 422
    assert (await client.post("/sync/events", json=batch(), headers=headers)).status_code == 422


# ---------- ролі ----------


async def test_roles(client, world, c) -> None:
    body = batch(progress(c.module.id, 10))
    assert (await client.post("/sync/events", json=body)).status_code == 401
    for user in (world.admin, world.parent_a):
        r = await client.post("/sync/events", json=body, headers=auth_header(user))
        assert r.status_code == 403
    # QR-ретрансляція вчителем — B10: поки 501, щоб події лишились в outbox вчителя.
    r = await client.post("/sync/events", json=body, headers=auth_header(world.teacher_a))
    assert r.status_code == 501 and r.json()["error"]["code"] == "NOT_IMPLEMENTED"
    for user in (world.teacher_a, world.admin, world.parent_a):
        r = await client.get("/sync/changes", headers=auth_header(user))
        assert r.status_code == 403
    assert (await client.get("/sync/changes")).status_code == 401


# ---------- правила конфліктів ----------


async def test_module_progress_takes_maximum(client, db_session, world, c) -> None:
    t = now()
    done = t - dt.timedelta(minutes=10)
    await send(client, world.student_a, batch(progress(c.module.id, 80, t, completed=None)))
    await send(client, world.student_a, batch(progress(c.module.id, 30, t)))
    row = await db_session.get(
        ModuleProgress, (world.student_a.id, c.module.id), populate_existing=True
    )
    assert row.progress_pct == 80 and row.completed_at_client is None
    e = progress(c.module.id, 100, t, completed=done)
    await send(client, world.student_a, batch(e))
    await send(client, world.student_a, batch(progress(c.module.id, 100, t, completed=t)))
    row = await db_session.get(
        ModuleProgress, (world.student_a.id, c.module.id), populate_existing=True
    )
    assert row.progress_pct == 100
    assert row.completed_at_client == done
    assert row.last_event_id == uuid.UUID(e["client_event_id"])


async def test_first_completed_attempt_is_credited_and_graded(client, db_session, world, c) -> None:
    t = now()
    later = attempt(c.test.id, {c.q1.id: ["a"], c.q2.id: ["c", "a"]}, t)
    earlier = attempt(c.test.id, {c.q1.id: ["b"], c.q2.id: ["a", "c"]}, t - dt.timedelta(hours=1))
    # Пізніша спроба прийшла першою (інший пристрій) — спочатку зарахована вона.
    await send(client, world.student_a, batch(later))
    # Раніша завершена спроба перемагає незалежно від порядку надходження.
    results = await send(client, world.student_a, batch(earlier))
    assert statuses(results) == [("accepted", None)]
    rows = {
        str(a.client_event_id): a
        for a in await db_session.scalars(select(Attempt).execution_options(populate_existing=True))
    }
    assert rows[earlier["client_event_id"]].credit_status == "credited"
    assert rows[earlier["client_event_id"]].score == 75  # 3 з 4 балів
    assert rows[later["client_event_id"]].credit_status == "not_credited_repeat"
    assert rows[later["client_event_id"]].score == 100
    # Ще пізніша — не зараховується.
    await send(client, world.student_a, batch(attempt(c.test.id, {}, t + dt.timedelta(hours=1))))
    assert await count(db_session, Attempt, Attempt.credit_status == "credited") == 1
    assert await count(db_session, Attempt) == 3


async def test_rollcall_latest_occurred_at_wins(client, db_session, world, c) -> None:
    t = now()
    await send(client, world.student_a, batch(rollcall(c.rc.id, "safe", t)))
    # Старіша подія, що прийшла пізніше (через QR / довгий офлайн), не перезаписує новішу.
    results = await send(
        client, world.student_a, batch(rollcall(c.rc.id, "in_shelter", t - dt.timedelta(minutes=5)))
    )
    assert statuses(results) == [("accepted", None)]
    row = await db_session.get(
        RollCallStatus, (c.rc.id, world.student_a.id), populate_existing=True
    )
    assert row.status == "safe"
    await send(
        client, world.student_a, batch(rollcall(c.rc.id, "in_shelter", t + dt.timedelta(minutes=1)))
    )
    row = await db_session.get(
        RollCallStatus, (c.rc.id, world.student_a.id), populate_existing=True
    )
    assert row.status == "in_shelter" and row.occurred_at == t + dt.timedelta(minutes=1)


async def test_events_in_batch_are_applied_in_occurred_at_order(
    client, db_session, world, c
) -> None:
    t = now()
    late = rollcall(c.rc.id, "safe", t)
    early = rollcall(c.rc.id, "in_shelter", t - dt.timedelta(minutes=2))
    results = await send(client, world.student_a, batch(late, early))
    assert statuses(results) == [("accepted", None)] * 2
    row = await db_session.get(
        RollCallStatus, (c.rc.id, world.student_a.id), populate_existing=True
    )
    assert row.status == "safe" and row.last_event_id == uuid.UUID(late["client_event_id"])


# ---------- час пристрою ----------


async def test_clock_skew_and_suspicious_flag(client, db_session, world, c) -> None:
    t = now()
    ok = progress(c.module.id, 10, t - dt.timedelta(minutes=1))
    await send(client, world.student_a, batch(ok, sent_at=t))
    row = await db_session.get(SyncEvent, uuid.UUID(ok["client_event_id"]))
    assert not row.is_suspicious and abs(row.clock_skew_ms) < 60_000

    future = attempt(c.test.id, {}, t + dt.timedelta(hours=1))
    results = await send(client, world.student_a, batch(future, sent_at=t))
    assert statuses(results) == [("accepted", None)]  # позначка, не блокування
    row = await db_session.get(SyncEvent, uuid.UUID(future["client_event_id"]))
    assert row.is_suspicious
    a = await db_session.scalar(
        select(Attempt).where(Attempt.client_event_id == row.client_event_id)
    )
    assert a.is_suspicious and a.credit_status == "credited"

    # Годинник пристрою відстає на годину: увесь пакет підозрілий, зсув записано.
    skewed = progress(c.module.id, 20, t - dt.timedelta(hours=1))
    await send(client, world.student_a, batch(skewed, sent_at=t - dt.timedelta(hours=1)))
    row = await db_session.get(SyncEvent, uuid.UUID(skewed["client_event_id"]))
    assert row.is_suspicious and 3_590_000 < row.clock_skew_ms < 3_610_000


async def test_event_three_days_late_is_credited(client, db_session, world, c) -> None:
    three_days = now() - dt.timedelta(days=3)
    c.rc.opened_at = three_days - dt.timedelta(minutes=10)
    c.rc.closed_at = three_days + dt.timedelta(hours=1)
    await db_session.flush()
    events = [
        attempt(c.test.id, {c.q1.id: ["a"], c.q2.id: ["a", "c"]}, three_days),
        progress(c.module.id, 100, three_days, completed=three_days),
        rollcall(c.rc.id, "in_shelter", three_days),
    ]
    results = await send(client, world.student_a, batch(*events))
    assert statuses(results) == [("accepted", None)] * 3
    a = await db_session.scalar(select(Attempt))
    assert a.credit_status == "credited" and a.score == 100 and not a.is_suspicious
    assert a.completed_at_client == three_days
    status = await db_session.get(RollCallStatus, (c.rc.id, world.student_a.id))
    assert status.occurred_at == three_days


# ---------- справжні commit-и: паралельність, збій, стрічка змін ----------


async def committed_world(cm) -> SimpleNamespace:
    f = cm.factory
    w = SimpleNamespace()
    w.school = await f.school()
    w.class_a = await f.klass(w.school, "7-А")
    w.teacher = await f.teacher(w.school, w.class_a)
    w.student = await f.student(w.class_a)
    w.other = await f.student(w.class_a, "Марко", "Коваль")
    w.c = await content(cm.session, f, w.class_a, w.teacher)
    await cm.session.commit()
    return w


async def test_same_batch_twice_in_parallel_gives_one_record(committed) -> None:
    w = await committed_world(committed)
    body = batch(
        *[progress(w.c.module.id, p) for p in (10, 20, 30)],
        attempt(w.c.test.id, {w.c.q1.id: ["a"]}, now()),
        rollcall(w.c.rc.id, "in_shelter", now()),
    )
    headers = auth_header(w.student)
    r1, r2 = await asyncio.gather(
        committed.client.post("/sync/events", json=body, headers=headers),
        committed.client.post("/sync/events", json=body, headers=headers),
    )
    assert r1.status_code == r2.status_code == 200, (r1.text, r2.text)
    pairs = zip(r1.json()["results"], r2.json()["results"], strict=True)
    for a, b in pairs:
        assert {a["status"], b["status"]} == {"accepted", "duplicate"}
    async with committed.maker() as db:
        assert await count(db, SyncEvent) == 5
        assert await count(db, Attempt) == 1
        assert await count(db, ModuleProgress) == 1
        assert await count(db, RollCallStatus) == 1
        mp = await db.get(ModuleProgress, (w.student.id, w.c.module.id))
        assert mp.progress_pct == 30


async def test_parallel_attempts_credit_exactly_one(committed) -> None:
    w = await committed_world(committed)
    headers = auth_header(w.student)
    t = now()
    bodies = [batch(attempt(w.c.test.id, {}, t - dt.timedelta(seconds=i))) for i in range(5)]
    responses = await asyncio.gather(
        *[committed.client.post("/sync/events", json=b, headers=headers) for b in bodies]
    )
    assert all(r.status_code == 200 for r in responses)
    async with committed.maker() as db:
        credited = list(
            await db.scalars(select(Attempt).where(Attempt.credit_status == "credited"))
        )
        assert len(credited) == 1
        # Зарахована найраніша завершена (t - 4 с).
        assert str(credited[0].client_event_id) == bodies[4]["events"][0]["client_event_id"]


class Crash(BaseException):
    """Імітує падіння процесу: не перехоплюється обробкою помилок застосунку."""


async def test_crash_in_the_middle_of_batch_loses_nothing(committed, monkeypatch) -> None:
    w = await committed_world(committed)
    t = now()
    events = [progress(w.c.module.id, 10 * i, t + dt.timedelta(seconds=i)) for i in range(1, 7)]
    body = batch(*events)
    original = sync_service._apply_module_progress
    calls = 0

    async def crashing(*args):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise Crash
        await original(*args)

    monkeypatch.setattr(sync_service, "_apply_module_progress", crashing)
    with pytest.raises(Crash):
        await committed.client.post("/sync/events", json=body, headers=auth_header(w.student))
    async with committed.maker() as db:
        # Перші три події закомічені, четверта відкочена разом із незавершеною транзакцією.
        assert await count(db, SyncEvent) == 3

    monkeypatch.setattr(sync_service, "_apply_module_progress", original)
    response = await committed.client.post(
        "/sync/events", json=body, headers=auth_header(w.student)
    )
    assert response.status_code == 200
    assert (
        statuses(response.json()["results"]) == [("duplicate", None)] * 3 + [("accepted", None)] * 3
    )
    async with committed.maker() as db:
        assert await count(db, SyncEvent) == 6
        mp = await db.get(ModuleProgress, (w.student.id, w.c.module.id))
        assert mp.progress_pct == 60


async def test_failing_event_does_not_block_others_and_asks_for_retry(
    committed, monkeypatch
) -> None:
    w = await committed_world(committed)
    body = batch(
        progress(w.c.module.id, 10, now() - dt.timedelta(seconds=2)),
        rollcall(w.c.rc.id, "safe", now() - dt.timedelta(seconds=1)),
        progress(w.c.module.id, 20, now()),
    )
    original = sync_service._apply_rollcall

    async def failing(*args):
        raise RuntimeError("db hiccup")

    monkeypatch.setattr(sync_service, "_apply_rollcall", failing)
    response = await committed.client.post(
        "/sync/events", json=body, headers=auth_header(w.student)
    )
    assert response.status_code == 500
    assert response.json()["error"]["details"] == {"failed": 1}
    monkeypatch.setattr(sync_service, "_apply_rollcall", original)
    response = await committed.client.post(
        "/sync/events", json=body, headers=auth_header(w.student)
    )
    assert statuses(response.json()["results"]) == [
        ("duplicate", None),
        ("accepted", None),
        ("duplicate", None),
    ]


async def test_deterministic_bad_events_are_rejected_not_retried_forever(
    client, db_session, world, c
) -> None:
    """NUL у payload (JSONB не приймає) і час поза діапазоном після переводу в UTC — не 500
    назавжди, а `rejected`/`invalid_payload`; повтор дає те саме, решта пакета приймається."""
    survey = {"survey_id": str(uuid.uuid4()), "question_id": "q\u00001", "value": 3}
    nul = event("survey_answer", survey)
    old = event("rollcall_status", {"session_id": str(c.rc.id), "status": "safe"})
    old["occurred_at"] = "0001-01-01T00:30:00+01:00"
    late = progress(c.module.id, 100)
    late["payload"]["completed_at"] = "9999-12-31T23:00:00-05:00"
    good = progress(c.module.id, 100.0)
    body = batch(nul, old, late, good)
    expected = [("rejected", "invalid_payload")] * 3 + [("accepted", None)]
    assert statuses(await send(client, world.student_a, body)) == expected
    again = await send(client, world.student_a, body)
    assert statuses(again) == expected[:3] + [("duplicate", None)]
    # Записано перевірений payload: `progress_pct` 100.0 -> 100, NUL-подія — без payload;
    # подію з часом поза діапазоном записати не можна (як unknown_type).
    stored = await db_session.get(SyncEvent, uuid.UUID(good["client_event_id"]))
    assert stored.payload == {
        "module_id": str(c.module.id),
        "progress_pct": 100,
        "completed_at": None,
    }
    rejected = await db_session.get(SyncEvent, uuid.UUID(nul["client_event_id"]))
    assert rejected.payload == {} and rejected.reject_reason == "invalid_payload"
    assert await db_session.get(SyncEvent, uuid.UUID(old["client_event_id"])) is None


async def test_data_error_while_applying_is_rejected_infra_error_is_retried(
    committed, monkeypatch
) -> None:
    """Помилка даних БД (SQLSTATE 22/23, DataError, ValueError) при застосуванні — подія
    `rejected`/`invalid_payload` і повтор дає те саме; збій з'єднання — 500 і повтор."""
    from sqlalchemy.exc import DBAPIError, OperationalError

    class PgError(Exception):
        def __init__(self, sqlstate: str) -> None:
            self.sqlstate = sqlstate

    w = await committed_world(committed)
    headers = auth_header(w.student)
    original = sync_service._apply_rollcall
    error: list[Exception] = []

    async def failing(*args):
        raise error[0]

    monkeypatch.setattr(sync_service, "_apply_rollcall", failing)
    for exc in (DBAPIError("INSERT", {}, PgError("22021")), ValueError("bad"), OverflowError()):
        error[:] = [exc]
        body = batch(rollcall(w.c.rc.id, "safe", now()), progress(w.c.module.id, 10))
        r = await committed.client.post("/sync/events", json=body, headers=headers)
        assert r.status_code == 200, r.text
        expected = [("rejected", "invalid_payload"), ("accepted", None)]
        assert statuses(r.json()["results"]) == expected
        r = await committed.client.post("/sync/events", json=body, headers=headers)
        assert statuses(r.json()["results"]) == [("rejected", "invalid_payload")] + [
            ("duplicate", None)
        ]

    error[:] = [OperationalError("INSERT", {}, PgError("08006"))]
    body = batch(rollcall(w.c.rc.id, "safe", now()))
    r = await committed.client.post("/sync/events", json=body, headers=headers)
    assert r.status_code == 500
    monkeypatch.setattr(sync_service, "_apply_rollcall", original)
    r = await committed.client.post("/sync/events", json=body, headers=headers)
    assert statuses(r.json()["results"]) == [("accepted", None)]


async def changes(cm, user, cursor: str | None = None, limit: int = 200) -> dict:
    params: dict[str, Any] = {"limit": limit}
    if cursor is not None:
        params["cursor"] = cursor
    r = await cm.client.get("/sync/changes", params=params, headers=auth_header(user))
    assert r.status_code == 200, r.text
    return r.json()


async def test_changes_feed_returns_current_state_after_cursor(committed) -> None:
    w = await committed_world(committed)
    client = committed.client
    t = now()
    a = attempt(w.c.test.id, {w.c.q1.id: ["a"]}, t)
    await client.post(
        "/sync/events",
        json=batch(progress(w.c.module.id, 50, t), a, rollcall(w.c.rc.id, "safe", t)),
        headers=auth_header(w.student),
    )
    # Чужі дані в стрічку учня не потрапляють.
    await client.post(
        "/sync/events",
        json=batch(progress(w.c.module.id, 90, t)),
        headers=auth_header(w.other),
    )
    first = await changes(committed, w.student)
    kinds = [ch["kind"] for ch in first["changes"]]
    assert sorted(kinds) == ["attempt_result", "module_progress", "rollcall_status"]
    by_kind = {ch["kind"]: ch for ch in first["changes"]}
    assert by_kind["module_progress"]["progress_pct"] == 50
    assert by_kind["attempt_result"] == {
        "kind": "attempt_result",
        "client_event_id": a["client_event_id"],
        "test_id": str(w.c.test.id),
        "credit_status": "credited",
        "score": 25.0,
        "is_suspicious": False,
    }
    assert by_kind["rollcall_status"]["status"] == "safe"
    assert first["has_more"] is False
    cursor = first["next_cursor"]

    # Повтор з тим самим курсором — нічого нового; новий стан — лише змінений рядок.
    assert (await changes(committed, w.student, cursor))["changes"] == []
    await client.post(
        "/sync/events",
        json=batch(progress(w.c.module.id, 100, t), progress(w.c.module.id, 10, t)),
        headers=auth_header(w.student),
    )
    after = await changes(committed, w.student, cursor)
    assert [ch["progress_pct"] for ch in after["changes"]] == [100]
    assert after["next_cursor"] != cursor
    # Без курсора — з початку (актуальний стан).
    assert len((await changes(committed, w.student))["changes"]) == 3


async def test_changes_pagination(committed) -> None:
    w = await committed_world(committed)
    t = now()
    modules = []
    for i in range(2, 7):
        m = Module(lesson_id=w.c.lesson.id, part="main", position=i, title=f"М{i}", duration_min=3)
        committed.session.add(m)
        modules.append(m)
    await committed.session.commit()
    for m in modules:  # окремі транзакції
        await committed.client.post(
            "/sync/events", json=batch(progress(m.id, 100, t)), headers=auth_header(w.student)
        )
    seen, cursor = [], None
    while True:
        page = await changes(committed, w.student, cursor, limit=2)
        seen += [ch["module_id"] for ch in page["changes"]]
        cursor = page["next_cursor"]
        if not page["has_more"]:
            break
    assert seen == [str(m.id) for m in modules]


async def test_changes_never_skip_a_transaction_that_commits_later(committed) -> None:
    """Транзакція T1 почалась раніше (менший xid), але ще не закомічена; T2 закомічена. Курсор
    не має перестрибнути зміни T1: поки T1 активна, T2 у стрічці не з'являється."""
    w = await committed_world(committed)
    m2 = Module(lesson_id=w.c.lesson.id, part="main", position=2, title="М2", duration_min=3)
    committed.session.add(m2)
    await committed.session.commit()
    async with committed.maker() as t1, committed.maker() as t2:
        # T1 отримує xid першою, а рядок у стрічці — пізніше.
        await t1.execute(select(func.pg_current_xact_id()))
        await t2.execute(
            ModuleProgress.__table__.insert().values(
                student_id=w.student.id,
                module_id=m2.id,
                progress_pct=20,
                last_event_id=await _event_row(committed, w.student),
            )
        )
        await t1.execute(
            ModuleProgress.__table__.insert().values(
                student_id=w.student.id,
                module_id=w.c.module.id,
                progress_pct=10,
                last_event_id=await _event_row(committed, w.student),
            )
        )
        await t2.commit()
        page = await changes(committed, w.student)
        assert page["changes"] == []  # T2 закомічена, але T1 (менший xid) ще активна
        await t1.commit()
    page = await changes(committed, w.student)
    assert [ch["progress_pct"] for ch in page["changes"]] == [10, 20]


async def _event_row(cm, student) -> uuid.UUID:
    """Окремо закомічена подія, на яку посилається рядок прогресу (FK last_event_id)."""
    event_id = uuid.uuid4()
    async with cm.maker() as db:
        db.add(
            SyncEvent(
                client_event_id=event_id,
                type="module_progress",
                user_id=student.id,
                device_id=uuid.uuid4(),
                occurred_at=now(),
                payload={},
                status="accepted",
            )
        )
        await db.commit()
    return event_id


async def test_invalid_cursor_is_422(client, world) -> None:
    for bad in ("abc", "12", "1.x", "-1.2"):
        r = await client.get(f"/sync/changes?cursor={bad}", headers=auth_header(world.student_a))
        assert r.status_code == 422 and r.json()["error"]["code"] == "INVALID_CURSOR"
