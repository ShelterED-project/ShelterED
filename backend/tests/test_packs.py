"""«Рюкзак»: збірка пакетів, версії, перезбірка, маніфест і завантаження."""

import datetime as dt
import gzip
import json
import logging
import uuid
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from conftest import auth_header, pushes
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.models.lessons import Card, Lesson, MediaAsset, Module, Question, Test
from app.models.packs import KnowledgePack, KnowledgePackLesson, KnowledgePackMedia
from app.models.school import LessonAssignment, ScheduleSlot
from app.services import packs as service

pytestmark = pytest.mark.anyio

KYIV = ZoneInfo("Europe/Kyiv")


def today() -> dt.date:
    return dt.datetime.now(dt.UTC).astimezone(KYIV).date()


async def media(db, world, kind: str, mime: str, size: int, **kw) -> MediaAsset:
    asset = MediaAsset(
        kind=kind,
        storage_key=f"{kind}/{uuid.uuid4()}.bin",
        mime_type=mime,
        size_bytes=size,
        sha256="ab" * 32,
        uploaded_by=world.teacher_a.id,
        **kw,
    )
    db.add(asset)
    await db.flush()
    return asset


@pytest.fixture
async def course(factory, world) -> SimpleNamespace:
    """7-А: слоти сьогодні й завтра. Сьогодні — урок з відео й субтитрами, модулями обох
    частин і тестом; завтра — урок без медіа."""
    db = factory.session
    c = SimpleNamespace()
    c.day = today()
    c.subject = await factory.subject()
    c.vtt = await media(db, world, "subtitles", "text/vtt", 1000)
    c.video = await media(db, world, "video", "video/mp4", 5000, subtitles_id=c.vtt.id)
    c.lesson = Lesson(
        subject_id=c.subject.id,
        author_id=world.teacher_a.id,
        title="Дроби",
        shelter_part="Укриття",
        main_part="Основна",
        status="published",
        published_at=dt.datetime.now(dt.UTC),
    )
    c.lesson2 = Lesson(
        subject_id=c.subject.id,
        author_id=world.teacher_a.id,
        title="Десяткові",
        shelter_part="Укриття 2",
        main_part="Основна 2",
        status="published",
        published_at=dt.datetime.now(dt.UTC),
    )
    db.add_all([c.lesson, c.lesson2])
    await db.flush()
    c.main = Module(lesson_id=c.lesson.id, part="main", position=1, title="Осн", duration_min=5)
    c.shelter = Module(
        lesson_id=c.lesson.id, part="shelter", position=1, title="Укр", duration_min=4
    )
    db.add_all([c.main, c.shelter])
    await db.flush()
    c.card = Card(
        module_id=c.shelter.id,
        position=1,
        kind="video",
        body={"caption": "Відео"},
        media_asset_id=c.video.id,
    )
    c.test = Test(lesson_id=c.lesson.id, title="Перевір себе")
    db.add_all([c.card, c.test])
    await db.flush()
    c.question = Question(
        test_id=c.test.id,
        position=1,
        kind="single",
        prompt="1/2 + 1/4?",
        options=[{"id": "a", "text": "3/4"}, {"id": "b", "text": "2/6"}],
        answer_key=["a"],
    )
    db.add(c.question)
    c.slots = []
    for offset, lesson in ((0, c.lesson), (1, c.lesson2)):
        day = c.day + dt.timedelta(days=offset)
        slot = ScheduleSlot(
            class_id=world.class_a.id,
            subject_id=c.subject.id,
            weekday=day.isoweekday(),
            starts_at=dt.time(9, 0),
            ends_at=dt.time(9, 45),
            valid_from=c.day - dt.timedelta(days=7),
        )
        db.add(slot)
        await db.flush()
        db.add(LessonAssignment(slot_id=slot.id, date=day, lesson_id=lesson.id))
        c.slots.append(slot)
    await db.flush()
    return c


async def rebuild(db, world, **kw):
    return await service.rebuild_class(
        db, world.class_a.id, kw.pop("settings", get_settings()), **kw
    )


def content(pack: KnowledgePack) -> dict:
    return json.loads(gzip.decompress(pack.content_gzip))


# ---------- збірка ----------


async def test_build_pack_content(db_session, world, course, enqueued) -> None:
    built = await rebuild(db_session, world)
    # Пакети лише на дні з уроками в розкладі: сьогодні й завтра.
    assert sorted(p.pack_date for p in built) == [course.day, course.day + dt.timedelta(days=1)]
    pack = next(p for p in built if p.pack_date == course.day)
    assert pack.version == 1
    body = content(pack)
    assert body["id"] == str(pack.id) and body["content_hash"] == pack.content_hash
    assert pack.size_bytes == len(gzip.decompress(pack.content_gzip))
    assert body["timezone"] == "Europe/Kyiv" and body["explanations"] == []
    assert [i["lesson_id"] for i in body["schedule"]] == [str(course.lesson.id)]
    (lesson,) = body["lessons"]
    assert lesson["version"] == 1
    # Спершу укриттєва частина.
    assert [m["part"] for m in lesson["modules"]] == ["shelter", "main"]
    assert lesson["modules"][0]["cards"][0]["media_asset_id"] == str(course.video.id)
    question = lesson["tests"][0]["questions"][0]
    assert "answer_key" not in question and question["options"][0] == {"id": "a", "text": "3/4"}

    media_ids = set(
        await db_session.scalars(
            select(KnowledgePackMedia.media_asset_id).where(KnowledgePackMedia.pack_id == pack.id)
        )
    )
    assert media_ids == {course.video.id, course.vtt.id}
    versions = (
        await db_session.execute(
            select(KnowledgePackLesson.lesson_id, KnowledgePackLesson.lesson_version).where(
                KnowledgePackLesson.pack_id == pack.id
            )
        )
    ).all()
    assert versions == [(course.lesson.id, 1)]

    # Один push «рюкзак оновився» на клас за перезбірку.
    assert pushes(enqueued) == [
        {
            "type": "pack_updated",
            "class_id": str(world.class_a.id),
            "pack_id": str(pack.id),
            "pack_date": course.day.isoformat(),
        }
    ]


async def test_rebuild_without_changes_is_idempotent(db_session, world, course, enqueued) -> None:
    first = await rebuild(db_session, world)
    # Повторна доставка задачі / паралельна перезбірка: вміст той самий → нічого нового.
    assert await rebuild(db_session, world) == []
    assert await rebuild(db_session, world) == []
    total = await db_session.scalar(select(func.count()).select_from(KnowledgePack))
    assert total == len(first) == 2
    assert len(pushes(enqueued)) == 1


async def test_hash_is_deterministic(db_session, world, course) -> None:
    body1, _, _ = await service.build_content(db_session, world.class_a, course.day)
    body2, _, _ = await service.build_content(db_session, world.class_a, course.day)
    assert service.content_hash(body1) == service.content_hash(body2)
    assert service.canonical_json(body1) == service.canonical_json(body2)


async def test_lesson_change_creates_new_version_and_keeps_old(
    db_session, world, course, enqueued
) -> None:
    (v1, _) = sorted(await rebuild(db_session, world), key=lambda p: p.pack_date)
    # Вчитель зняв урок, змінив і знову опублікував (version + 1).
    course.lesson.title = "Дроби (оновлено)"
    course.lesson.version = 2
    await db_session.flush()
    (v2,) = await rebuild(db_session, world)
    assert v2.pack_date == course.day and v2.version == 2 and v2.id != v1.id
    assert v2.content_hash != v1.content_hash
    assert content(v2)["lessons"][0]["version"] == 2
    # Стара версія лишається: учень, що почав урок за нею, її не втрачає. Id модулів і
    # тестів стабільні між версіями, тож прогрес прив'язаний до них, а не до версії пакета.
    old = await db_session.get(KnowledgePack, v1.id)
    assert content(old)["lessons"][0]["title"] == "Дроби"
    assert content(old)["lessons"][0]["modules"][0]["id"] == str(course.shelter.id)
    assert content(v2)["lessons"][0]["modules"][0]["id"] == str(course.shelter.id)
    assert len(pushes(enqueued, "pack_updated")) == 2


async def test_unpublished_lesson_leaves_pack(db_session, world, course) -> None:
    await rebuild(db_session, world)
    course.lesson.status = "draft"
    await db_session.flush()
    (pack,) = await rebuild(db_session, world)
    body = content(pack)
    assert body["lessons"] == [] and body["schedule"][0]["lesson_id"] is None


async def test_no_pack_for_day_without_schedule(db_session, world) -> None:
    assert await rebuild(db_session, world) == []
    assert await db_session.scalar(select(func.count()).select_from(KnowledgePack)) == 0


async def test_rebuild_for_lesson_and_refresh_all(db_session, world, course) -> None:
    built = await service.rebuild_for_lesson(db_session, course.lesson.id, get_settings())
    assert {p.class_id for p in built} == {world.class_a.id}
    # Періодична перезбірка без змін нічого не створює.
    assert await service.refresh_all(db_session, get_settings()) == 0


async def test_size_limits_are_logged(db_session, world, course, caplog) -> None:
    settings = get_settings().model_copy(update={"pack_max_day_bytes": 1, "pack_max_week_bytes": 1})
    with caplog.at_level(logging.INFO, logger="app.services.packs"):
        await rebuild(db_session, world, settings=settings)
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("Pack built:") and "media_bytes=6000" in m for m in messages)
    assert any(m.startswith("Pack exceeds day limit") for m in messages)
    assert any(m.startswith("Class packs exceed week limit") for m in messages)


# ---------- тригери перезбірки ----------


def tasks(enqueued, name: str) -> list[list]:
    return [c.args for c in enqueued if c.name == name]


async def test_publish_and_unpublish_enqueue_rebuild(
    client: AsyncClient, world, course, enqueued
) -> None:
    headers = auth_header(world.teacher_a)
    lesson_id = str(course.lesson.id)
    assert (await client.post(f"/lessons/{lesson_id}/unpublish", headers=headers)).is_success
    assert (await client.post(f"/lessons/{lesson_id}/publish", headers=headers)).is_success
    assert tasks(enqueued, "packs.rebuild_for_lesson") == [[lesson_id], [lesson_id]]
    assert all(c.queue == "default" for c in enqueued if c.name.startswith("packs."))


async def test_schedule_change_enqueues_class_rebuild(
    client: AsyncClient, world, course, enqueued
) -> None:
    slot = course.slots[0]
    url = f"/classes/{world.class_a.id}/schedule/slots/{slot.id}/lessons/{course.day}"
    resp = await client.delete(url, headers=auth_header(world.teacher_a))
    assert resp.status_code == 204
    assert tasks(enqueued, "packs.rebuild_class") == [[str(world.class_a.id)]]
