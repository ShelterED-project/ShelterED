"""«Як ти зараз?» (docs/wellbeing-checkin.md): запис через синхронізацію, одна відповідь на
день, хто що бачить (лише дитина й батьки), журнал переглядів, строк зберігання."""

import datetime as dt
import logging
import uuid
from zoneinfo import ZoneInfo

import pytest
from conftest import auth_header
from sqlalchemy import delete, func, select

from app.models.school import User
from app.models.sync import SyncEvent
from app.models.wellbeing import WellbeingAnswer, WellbeingViewLog
from app.services import wellbeing as service
from app.services.wellbeing_texts import TEXTS

pytestmark = pytest.mark.anyio

KYIV = ZoneInfo("Europe/Kyiv")
DEVICE = str(uuid.uuid4())


def today() -> dt.date:
    return dt.datetime.now(KYIV).date()


def at(day: dt.date, hour: int = 12, minute: int = 0) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute), tzinfo=KYIV)


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).isoformat().replace("+00:00", "Z")


def survey(payload, when: dt.datetime | None = None, event_id: str | None = None) -> dict:
    return {
        "client_event_id": event_id or str(uuid.uuid4()),
        "type": "survey_answer",
        "device_id": DEVICE,
        "occurred_at": iso(when or dt.datetime.now(dt.UTC)),
        "payload": payload,
    }


async def send(client, user, *events: dict) -> list[dict]:
    body = {"sent_at": iso(dt.datetime.now(dt.UTC)), "events": list(events)}
    response = await client.post("/sync/events", json=body, headers=auth_header(user))
    assert response.status_code == 200, response.text
    return response.json()["results"]


async def answer(db, student, day: dt.date, value: int) -> None:
    db.add(
        WellbeingAnswer(
            id=uuid.uuid4(),
            student_id=student.id,
            answered_on=day,
            value=value,
            occurred_at=at(day),
        )
    )
    await db.flush()


async def answers_of(db, student) -> list[tuple[dt.date, int]]:
    rows = await db.execute(
        select(WellbeingAnswer.answered_on, WellbeingAnswer.value)
        .where(WellbeingAnswer.student_id == student.id)
        .order_by(WellbeingAnswer.answered_on)
    )
    return [tuple(r) for r in rows]


async def logs(db, **where) -> list[WellbeingViewLog]:
    query = select(WellbeingViewLog)
    for key, value in where.items():
        query = query.where(getattr(WellbeingViewLog, key) == value)
    return list((await db.scalars(query)).all())


# ---------- запис через POST /sync/events ----------


async def test_answer_is_stored_separately_and_sync_event_payload_is_redacted(
    client, db_session, world, caplog
) -> None:
    event = survey({"value": 2})
    with caplog.at_level(logging.DEBUG):
        results = await send(client, world.student_a, event)
    assert results[0]["status"] == "accepted"
    assert await answers_of(db_session, world.student_a) == [(today(), 2)]
    logged = await db_session.get(SyncEvent, uuid.UUID(event["client_event_id"]))
    assert logged.status == "accepted" and logged.payload == {}
    # Значення не потрапляє в логи.
    assert not any('"value"' in r.getMessage() for r in caplog.records)
    # Повтор — дубль, рядок один.
    assert (await send(client, world.student_a, event))[0]["status"] == "duplicate"
    assert len(await answers_of(db_session, world.student_a)) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"value": 0},
        {"value": 6},
        {"value": "3"},
        {"value": 3.5},
        {"value": True},
        {},
        {"value": 3, "question_id": "q1"},
        {"survey_id": str(uuid.uuid4()), "question_id": "q1", "value": 3},
    ],
)
async def test_invalid_value_is_rejected(client, db_session, world, payload) -> None:
    results = await send(client, world.student_a, survey(payload))
    assert (results[0]["status"], results[0]["reason"]) == ("rejected", "invalid_payload")
    assert await answers_of(db_session, world.student_a) == []


async def test_later_answer_same_day_replaces_earlier_in_any_order(
    client, db_session, world
) -> None:
    day = today() - dt.timedelta(days=1)
    morning = survey({"value": 1}, at(day, 9))
    evening = survey({"value": 4}, at(day, 19))
    # Пізніша приходить першою (інший пристрій синхронізувався раніше).
    await send(client, world.student_a, evening)
    await send(client, world.student_a, morning)
    assert await answers_of(db_session, world.student_a) == [(day, 4)]
    row = await db_session.scalar(
        select(WellbeingAnswer).where(WellbeingAnswer.student_id == world.student_a.id)
    )
    assert row.id == uuid.UUID(evening["client_event_id"])
    # Ще пізніша того ж дня — замінює; інший день — окремий рядок.
    await send(client, world.student_a, survey({"value": 2}, at(day, 21)))
    await send(client, world.student_a, survey({"value": 5}, at(today(), 8)))
    assert await answers_of(db_session, world.student_a) == [(day, 2), (today(), 5)]


async def test_day_is_taken_in_kyiv_time(client, db_session, world) -> None:
    # 23:30 UTC = 01:30 (або 02:30) наступного дня за Києвом.
    utc = dt.datetime.combine(today() - dt.timedelta(days=2), dt.time(23, 30), tzinfo=dt.UTC)
    await send(client, world.student_a, survey({"value": 3}, utc))
    assert await answers_of(db_session, world.student_a) == [(utc.astimezone(KYIV).date(), 3)]


# ---------- учень і батьки ----------


async def test_student_sees_own_pictures_for_14_days_without_numbers_and_no_log(
    client, db_session, world
) -> None:
    await answer(db_session, world.student_a, today(), 5)
    await answer(db_session, world.student_a, today() - dt.timedelta(days=3), 1)
    await answer(db_session, world.student_a, today() - dt.timedelta(days=20), 3)
    r = await client.get(
        f"/students/{world.student_a.id}/wellbeing", headers=auth_header(world.student_a)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["view"] == "self" and body["show_support"] is False
    assert body["days"] == [
        {"date": today().isoformat(), "picture": "sun"},
        {"date": (today() - dt.timedelta(days=3)).isoformat(), "picture": "storm"},
    ]
    assert "value" not in r.text
    assert await logs(db_session) == []


async def test_parent_sees_only_weekly_words_and_view_is_logged(client, db_session, world) -> None:
    for days_ago, value in [(0, 5), (1, 4), (2, 3), (4, 5), (10, 1)]:
        await answer(db_session, world.student_a, today() - dt.timedelta(days=days_ago), value)
    r = await client.get(
        f"/students/{world.student_a.id}/wellbeing", headers=auth_header(world.parent_a)
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["view"] == "parent"
    assert body["mood"] == "sunny"
    assert body["summary"] == "Цього тижня більшість днів — сонячні."
    assert body["gentle_note"] is None and body["tips"] == []
    assert "days" not in body and "value" not in body
    assert body["week_to"] == today().isoformat()
    [log] = await logs(db_session)
    assert (log.viewer_id, log.student_id) == (world.parent_a.id, world.student_a.id)


async def test_parent_summary_needs_three_answers_and_ties_are_calm(
    client, db_session, world
) -> None:
    await answer(db_session, world.student_a, today(), 1)
    await answer(db_session, world.student_a, today() - dt.timedelta(days=1), 2)
    url = f"/students/{world.student_a.id}/wellbeing"
    body = (await client.get(url, headers=auth_header(world.parent_a))).json()
    assert body["mood"] is None and body["summary"] == TEXTS["parent"]["not_enough"]
    # Нічия «непрості» / «сонячні» — показуємо спокійніше слово.
    await answer(db_session, world.student_a, today() - dt.timedelta(days=2), 5)
    await answer(db_session, world.student_a, today() - dt.timedelta(days=3), 4)
    body = (await client.get(url, headers=auth_header(world.parent_a))).json()
    assert body["mood"] == "sunny"


async def test_gentle_signal_three_of_last_five_within_14_days(client, db_session, world) -> None:
    url = f"/students/{world.student_a.id}/wellbeing"
    # Старі непрості дні (поза 14 днями) не рахуються.
    for days_ago in (15, 16, 17):
        await answer(db_session, world.student_a, today() - dt.timedelta(days=days_ago), 1)
    await answer(db_session, world.student_a, today() - dt.timedelta(days=1), 2)
    await answer(db_session, world.student_a, today() - dt.timedelta(days=2), 1)
    await answer(db_session, world.student_a, today() - dt.timedelta(days=3), 4)
    child = (await client.get(url, headers=auth_header(world.student_a))).json()
    assert child["show_support"] is False
    parent = (await client.get(url, headers=auth_header(world.parent_a))).json()
    assert parent["gentle_note"] is None and parent["tips"] == []

    await answer(db_session, world.student_a, today() - dt.timedelta(days=8), 2)
    child = (await client.get(url, headers=auth_header(world.student_a))).json()
    assert child["show_support"] is True
    parent = (await client.get(url, headers=auth_header(world.parent_a))).json()
    assert parent["gentle_note"] == TEXTS["parent"]["gentle_note"]
    assert parent["tips"] == TEXTS["parent"]["tips"]

    # Лише останні 5 відповідей: свіжі сонячні дні витісняють старі непрості.
    for days_ago in (0, 4, 5):
        await answer(db_session, world.student_a, today() - dt.timedelta(days=days_ago), 5)
    child = (await client.get(url, headers=auth_header(world.student_a))).json()
    assert child["show_support"] is False


@pytest.mark.parametrize("who", ["parent_free", "teacher_a", "admin", "student_b"])
async def test_others_cannot_see_child_wellbeing(client, db_session, world, who) -> None:
    await answer(db_session, world.student_a, today(), 3)
    r = await client.get(
        f"/students/{world.student_a.id}/wellbeing", headers=auth_header(getattr(world, who))
    )
    assert r.status_code == 403
    assert await logs(db_session) == []


async def test_other_parent_of_another_child_is_denied(client, factory, world) -> None:
    other_parent = await factory.parent_of(world.student_b)
    r = await client.get(
        f"/students/{world.student_a.id}/wellbeing", headers=auth_header(other_parent)
    )
    assert r.status_code == 403


# ---------- вчитель і адміністрація — нічого ----------


@pytest.mark.parametrize("who", ["teacher_a", "admin"])
async def test_teacher_of_class_and_school_admin_see_nothing(
    client, db_session, factory, world, who
) -> None:
    """Вчитель класу дитини й адмін її школи не бачать ні дитину, ні зведень класу чи школи:
    дані опитування — лише для дитини та її батьків."""
    students = [await factory.student(world.class_a, f"Учень{i}", "Тест") for i in range(5)]
    for student in [world.student_a, *students]:
        await answer(db_session, student, today(), 1)
    headers = auth_header(getattr(world, who))
    r = await client.get(f"/students/{world.student_a.id}/wellbeing", headers=headers)
    assert r.status_code == 403
    for url in (f"/classes/{world.class_a.id}/wellbeing", "/wellbeing/school"):
        assert (await client.get(url, headers=headers)).status_code == 404
    assert await logs(db_session) == []


# ---------- тексти ----------


@pytest.mark.parametrize("who", ["student_a", "parent_a", "teacher_a", "admin"])
async def test_texts_for_any_authenticated_user(client, world, who) -> None:
    r = await client.get("/wellbeing/texts", headers=auth_header(getattr(world, who)))
    assert r.status_code == 200
    body = r.json()
    assert [s["label"] for s in body["child"]["scale"]] == [
        "Гроза",
        "Дощик",
        "Хмаринка",
        "Сонце за хмаркою",
        "Сонечко",
    ]
    assert {h["phone"] for h in body["child"]["support"]["hotlines"]} == {
        "116 111",
        "0 800 500 225",
    }
    assert body["child"]["skip"] == "Пропустити"
    assert "staff" not in body
    lowered = r.text.lower()
    for word in ("депрес", "тривожн", "ризик", "норм", "мусиш", "діагноз"):
        assert word not in lowered, word


async def test_texts_require_auth(client) -> None:
    assert (await client.get("/wellbeing/texts")).status_code == 401


# ---------- зберігання ----------


async def test_purge_removes_answers_older_than_30_days_idempotently(db_session, world) -> None:
    now = dt.datetime.now(dt.UTC)
    for days_ago in (0, 29, 30, 31, 60):
        await answer(db_session, world.student_a, today() - dt.timedelta(days=days_ago), 3)
    assert await service.purge_old(db_session, now) == 2
    kept = [d for d, _ in await answers_of(db_session, world.student_a)]
    assert kept == [today() - dt.timedelta(days=n) for n in (30, 29, 0)]
    assert await service.purge_old(db_session, now) == 0
    assert len(await answers_of(db_session, world.student_a)) == 3


async def test_answers_and_view_log_are_deleted_with_student(client, db_session, world) -> None:
    await answer(db_session, world.student_a, today(), 3)
    await client.get(
        f"/students/{world.student_a.id}/wellbeing", headers=auth_header(world.parent_a)
    )
    await db_session.execute(delete(User).where(User.id == world.student_a.id))
    count = await db_session.scalar(select(func.count()).select_from(WellbeingAnswer))
    assert count == 0
    assert await logs(db_session) == []


def test_purge_task_is_scheduled_daily() -> None:
    import app.workers.wellbeing  # noqa: F401
    from app.workers.celery_app import celery_app

    entry = celery_app.conf.beat_schedule["wellbeing-purge"]
    assert entry["task"] == "wellbeing.purge" and entry["schedule"] == 86400.0
    assert "wellbeing.purge" in celery_app.tasks
