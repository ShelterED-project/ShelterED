"""Додатковий урок поза розкладом (вчитель класу) і перевірка предмета уроку в слоті."""

import datetime as dt
import gzip
import json
import uuid
from zoneinfo import ZoneInfo

import pytest
from conftest import auth_header
from httpx import AsyncClient
from sqlalchemy import select, text

from app.core.config import get_settings
from app.models.lessons import Lesson
from app.models.packs import KnowledgePack
from app.models.school import LessonAssignment, ScheduleOverride
from app.schemas.school import ExtraLessonCreate
from app.services import packs as packs_service
from app.services import school as school_service
from app.services import sync as sync_service
from app.services.schedule import to_utc

pytestmark = pytest.mark.anyio

KYIV = ZoneInfo("Europe/Kyiv")


def today() -> dt.date:
    return dt.datetime.now(KYIV).date()


# Наступний понеділок (слоти тестів — по понеділках): «майбутні» уроки не залежать від дати запуску.
MONDAY = today() + dt.timedelta(days=7 - today().weekday())


async def published_lesson(factory, teacher, subject, status: str = "published") -> Lesson:
    lesson = Lesson(
        subject_id=subject.id,
        author_id=teacher.id,
        title="Додатковий",
        shelter_part="Укриття",
        main_part="",
        status=status,
        published_at=dt.datetime.now(dt.UTC),
    )
    factory.session.add(lesson)
    await factory.session.flush()
    return lesson


def extra_body(lesson, day: dt.date, **kw) -> dict:
    return {
        "id": str(kw.pop("id", uuid.uuid4())),
        "date": str(day),
        "lesson_id": str(lesson.id),
        **kw,
    }


def url(world, klass=None) -> str:
    return f"/classes/{(klass or world.class_a).id}/schedule/extra-lessons"


async def latest_content(db, world, day: dt.date) -> dict:
    pack = await db.scalar(
        select(KnowledgePack)
        .where(KnowledgePack.class_id == world.class_a.id, KnowledgePack.pack_date == day)
        .order_by(KnowledgePack.version.desc())
        .limit(1)
    )
    return json.loads(gzip.decompress(pack.content_gzip))


async def test_extra_lesson_in_schedule_pack_and_now(
    client: AsyncClient, world, factory, db_session, enqueued
) -> None:
    subject = await factory.subject()
    lesson = await published_lesson(factory, world.teacher_a, subject)
    day = today()
    headers = auth_header(world.teacher_a)
    body = extra_body(lesson, day, starts_at="15:00:00", ends_at="15:45:00")

    resp = await client.post(url(world), json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    out = resp.json()
    assert out["subject_id"] == str(subject.id) and out["pack_day_bytes"] > 0
    assert [c.args for c in enqueued if c.name == "packs.rebuild_class"] == [
        [str(world.class_a.id)]
    ]
    # Повтор — 200 і той самий запис; той самий id з іншими даними — 409.
    again = await client.post(url(world), json=body, headers=headers)
    assert again.status_code == 200 and again.json()["id"] == body["id"]
    other = await client.post(url(world), json={**body, "ends_at": "16:00:00"}, headers=headers)
    assert other.status_code == 409 and other.json()["error"]["code"] == "ID_CONFLICT"

    sched = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": str(day), "days": 1},
        headers=auth_header(world.student_a),
    )
    [item] = sched.json()["days"][0]["items"]
    assert item["kind"] == "extra" and item["slot_id"] is None
    assert item["override_id"] == body["id"] and item["lesson_id"] == str(lesson.id)

    now = await client.get(
        f"/classes/{world.class_a.id}/schedule/current",
        params={"at": to_utc(day, dt.time(15, 10), KYIV).isoformat()},
        headers=headers,
    )
    assert now.json()["item"]["lesson_id"] == str(lesson.id)

    # Прогрес учня з цього уроку синхронізація приймає ще до збірки пакета.
    assert await sync_service._student_has_lesson(db_session, world.student_a.id, lesson.id)
    assert not await sync_service._student_has_lesson(db_session, world.student_b.id, lesson.id)

    await packs_service.rebuild_class(db_session, world.class_a.id, get_settings())
    content = await latest_content(db_session, world, day)
    assert [x["id"] for x in content["lessons"]] == [str(lesson.id)]
    assert content["schedule"][0]["override_id"] == body["id"]
    # Урок поза розкладом теж знаходить перезбірка після публікації/зняття уроку.
    assert await packs_service.classes_with_lesson(db_session, lesson.id, day, day) == [
        world.class_a.id
    ]

    assert (await client.delete(f"{url(world)}/{body['id']}", headers=headers)).status_code == 204
    assert (await client.delete(f"{url(world)}/{body['id']}", headers=headers)).status_code == 204
    await packs_service.rebuild_class(db_session, world.class_a.id, get_settings())
    content = await latest_content(db_session, world, day)
    assert content["lessons"] == [] and content["schedule"] == []


async def test_extra_lesson_without_time_is_not_current(
    client: AsyncClient, world, factory
) -> None:
    subject = await factory.subject()
    lesson = await published_lesson(factory, world.teacher_a, subject)
    headers = auth_header(world.teacher_a)
    body = extra_body(lesson, MONDAY)
    assert (await client.post(url(world), json=body, headers=headers)).status_code == 201
    sched = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": str(MONDAY), "days": 1},
        headers=headers,
    )
    [item] = sched.json()["days"][0]["items"]
    assert item["starts_at"] is None and item["starts_at_utc"] is None
    assert item["lesson_id"] == str(lesson.id)
    now = await client.get(
        f"/classes/{world.class_a.id}/schedule/current",
        params={"at": to_utc(MONDAY, dt.time(12, 0), KYIV).isoformat()},
        headers=headers,
    )
    assert now.json()["item"] is None
    # Лише одна межа часу — 422.
    half = extra_body(lesson, MONDAY, starts_at="10:00:00")
    assert (await client.post(url(world), json=half, headers=headers)).status_code == 422


async def test_extra_lesson_roles_and_rules(
    client: AsyncClient, world, factory, db_session
) -> None:
    subject = await factory.subject()
    lesson = await published_lesson(factory, world.teacher_a, subject)
    body = extra_body(lesson, MONDAY)
    # Вчитель іншого класу, адміністрація (розклад уроків — справа вчителя), учень, батьки.
    for user in (world.teacher_b, world.admin, world.student_a, world.parent_a):
        resp = await client.post(url(world), json=body, headers=auth_header(user))
        assert resp.status_code == 403, user.role
        resp = await client.delete(f"{url(world)}/{body['id']}", headers=auth_header(user))
        assert resp.status_code == 403, user.role
    headers = auth_header(world.teacher_a)
    draft = await published_lesson(factory, world.teacher_a, subject, status="draft")
    resp = await client.post(url(world), json=extra_body(draft, MONDAY), headers=headers)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "LESSON_NOT_PUBLISHED"
    foreign = await published_lesson(factory, await factory.teacher(world.other_school), subject)
    resp = await client.post(url(world), json=extra_body(foreign, MONDAY), headers=headers)
    assert resp.status_code == 404
    # Вчитель класу додає урок; вчитель іншого класу не може видалити його через свій клас.
    assert (await client.post(url(world), json=body, headers=headers)).status_code == 201
    resp = await client.delete(
        f"{url(world, world.class_b)}/{body['id']}", headers=auth_header(world.teacher_b)
    )
    assert resp.status_code == 204
    sched = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": str(MONDAY), "days": 1},
        headers=headers,
    )
    assert len(sched.json()["days"][0]["items"]) == 1
    # Видалення через ендпоінт додаткових уроків не чіпає перевизначень адміністрації.
    cancel_id = str(uuid.uuid4())
    slot = await make_slot(client, world, subject)
    await client.post(
        f"/classes/{world.class_a.id}/schedule/overrides",
        json={"id": cancel_id, "date": str(MONDAY), "kind": "cancel", "slot_id": slot["id"]},
        headers=auth_header(world.admin),
    )
    assert (await client.delete(f"{url(world)}/{cancel_id}", headers=headers)).status_code == 204
    overrides = await client.get(
        f"/classes/{world.class_a.id}/schedule/overrides",
        params={"from": str(MONDAY), "to": str(MONDAY)},
        headers=headers,
    )
    assert {o["id"] for o in overrides.json()} == {cancel_id, body["id"]}


async def test_extra_lesson_retry_racing_hard_delete(
    client: AsyncClient, world, factory, db_session
) -> None:
    """Повтор бачить запис, але до вставки його видаляють (тут — перевизначення
    адміністрації): вставка створює запис знову з перевірками й розміром пакета, без 500."""
    subject = await factory.subject()
    lesson = await published_lesson(factory, world.teacher_a, subject)
    body = extra_body(lesson, MONDAY)
    headers = auth_header(world.teacher_a)
    assert (await client.post(url(world), json=body, headers=headers)).status_code == 201
    # Запис лишається в identity map сесії, а з БД зникає повз ORM (як паралельне видалення).
    assert await db_session.get(ScheduleOverride, uuid.UUID(body["id"])) is not None
    await db_session.execute(
        text("DELETE FROM schedule_override WHERE id = :id"), {"id": body["id"]}
    )
    extra, created, size = await school_service.create_extra_lesson(
        db_session, world.teacher_a, world.class_a, ExtraLessonCreate(**body), get_settings()
    )
    assert created and extra.lesson_id == lesson.id and size > 0


# ---------- предмет уроку = предмет слота ----------


async def make_slot(client: AsyncClient, world, subject) -> dict:
    body = {
        "id": str(uuid.uuid4()),
        "subject_id": str(subject.id),
        "weekday": 1,
        "starts_at": "09:00:00",
        "ends_at": "09:45:00",
        "valid_from": "2026-09-01",
        "valid_to": None,
    }
    resp = await client.post(
        f"/classes/{world.class_a.id}/schedule/slots", json=body, headers=auth_header(world.admin)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_lesson_subject_must_match_slot(
    client: AsyncClient, world, factory, db_session
) -> None:
    math, history = await factory.subject(), await factory.subject()
    slot = await make_slot(client, world, math)
    math_lesson = await published_lesson(factory, world.teacher_a, math)
    history_lesson = await published_lesson(factory, world.teacher_a, history)
    base = f"/classes/{world.class_a.id}/schedule/slots/{slot['id']}/lessons"
    headers, admin = auth_header(world.teacher_a), auth_header(world.admin)

    wrong = await client.put(
        f"{base}/{MONDAY}", json={"lesson_id": str(history_lesson.id)}, headers=headers
    )
    assert wrong.status_code == 422
    err = wrong.json()["error"]
    assert err["code"] == "LESSON_SUBJECT_MISMATCH"
    assert err["details"]["subject_id"] == str(math.id)

    # Заміна предмета на дату: тепер у слот іде урок нового предмета, а не старого.
    next_week = MONDAY + dt.timedelta(days=7)
    replace = {
        "id": str(uuid.uuid4()),
        "date": str(next_week),
        "kind": "replace",
        "slot_id": slot["id"],
        "subject_id": str(history.id),
    }
    overrides = f"/classes/{world.class_a.id}/schedule/overrides"
    assert (await client.post(overrides, json=replace, headers=admin)).status_code == 201
    ok = await client.put(
        f"{base}/{next_week}", json={"lesson_id": str(history_lesson.id)}, headers=headers
    )
    assert ok.status_code == 200
    resp = await client.put(
        f"{base}/{next_week}", json={"lesson_id": str(math_lesson.id)}, headers=headers
    )
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "LESSON_SUBJECT_MISMATCH"

    # Заміна предмета в день, де вже стоїть урок іншого предмета, — 422.
    assert (
        await client.put(
            f"{base}/{MONDAY}", json={"lesson_id": str(math_lesson.id)}, headers=headers
        )
    ).status_code == 200
    clash = {**replace, "id": str(uuid.uuid4()), "date": str(MONDAY)}
    resp = await client.post(overrides, json=clash, headers=admin)
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "LESSON_SUBJECT_MISMATCH"

    # Зміна предмета слота, коли в ньому вже стоїть майбутній урок старого предмета, — 422
    # (день із заміною предмета не заважає).
    slot_url = f"/classes/{world.class_a.id}/schedule/slots/{slot['id']}"
    resp = await client.patch(slot_url, json={"subject_id": str(history.id)}, headers=admin)
    assert resp.status_code == 422
    err = resp.json()["error"]
    assert err["code"] == "LESSON_SUBJECT_MISMATCH" and err["details"]["dates"] == [str(MONDAY)]
    assert (await client.delete(f"{base}/{MONDAY}", headers=headers)).status_code == 204
    resp = await client.patch(slot_url, json={"subject_id": str(history.id)}, headers=admin)
    assert resp.status_code == 200
    assert len(list(await db_session.scalars(select(LessonAssignment)))) == 1
