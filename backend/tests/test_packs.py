"""«Рюкзак»: збірка пакетів, версії, перезбірка, маніфест і завантаження."""

import datetime as dt
import gzip
import json
import logging
import uuid
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import brotli
import pytest
from conftest import auth_header, pushes
from httpx import AsyncClient
from sqlalchemy import event, func, inspect, select

from app.core.config import get_settings
from app.models.lessons import Card, Lesson, MediaAsset, Module, Question, Test
from app.models.packs import KnowledgePack, KnowledgePackLesson, KnowledgePackMedia
from app.models.school import LessonAssignment, ScheduleOverride, ScheduleSlot
from app.services import packs as service
from app.services import school as school_service

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
        source_sha256="ab" * 32,
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
    # Тест без вікна — тренувальний: ключ у пакеті для миттєвої перевірки офлайн.
    assert question["answer_key"] == ["a"] and question["options"][0] == {"id": "a", "text": "3/4"}

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


def keys(data) -> set[str]:
    """Усі ключі словників на будь-якій глибині."""
    if isinstance(data, dict):
        return set(data) | {k for v in data.values() for k in keys(v)}
    if isinstance(data, list):
        return {k for v in data for k in keys(v)}
    return set()


async def graded_test(db, course) -> Test:
    test = Test(
        lesson_id=course.lesson.id, title="Контрольна", window_enabled=True, window_hours=48
    )
    db.add(test)
    await db.flush()
    db.add(
        Question(
            test_id=test.id,
            position=1,
            kind="multiple",
            prompt="Які дроби дорівнюють 1/2?",
            options=[
                {"id": "a", "text": "2/4"},
                {"id": "b", "text": "3/6"},
                {"id": "c", "text": "1/3"},
            ],
            answer_key=["a", "b"],
        )
    )
    await db.flush()
    return test


async def test_lesson_repeated_in_week_is_read_once_per_rebuild(
    db_session, world, course, enqueued
) -> None:
    """Урок, що стоїть у кількох днях тижня, читається з БД раз за перезбірку, а вміст у
    пакетах однаковий."""
    day = course.day + dt.timedelta(days=2)
    slot = ScheduleSlot(
        class_id=world.class_a.id,
        subject_id=course.subject.id,
        weekday=day.isoweekday(),
        starts_at=dt.time(10, 0),
        ends_at=dt.time(10, 45),
        valid_from=course.day - dt.timedelta(days=7),
    )
    db_session.add(slot)
    await db_session.flush()
    db_session.add(LessonAssignment(slot_id=slot.id, date=day, lesson_id=course.lesson.id))
    await db_session.flush()

    statements: list[str] = []

    def record(conn, cursor, statement, *args) -> None:
        statements.append(statement)

    engine = db_session.bind.engine.sync_engine
    event.listen(engine, "before_cursor_execute", record)
    try:
        built = await rebuild(db_session, world)
    finally:
        event.remove(engine, "before_cursor_execute", record)
    by_day = {p.pack_date: content(p) for p in built}
    assert by_day[day]["lessons"] == by_day[course.day]["lessons"]
    # Один запит модулів на кожен день із новими уроками (сьогодні й завтра), а не на кожен урок.
    assert sum("FROM module" in s and "lesson_id IN" in s for s in statements) == 2


async def test_answer_key_only_for_practice_tests(db_session, world, course) -> None:
    graded = await graded_test(db_session, course)
    body, _, _ = await service.build_content(db_session, world.class_a, course.day)
    tests = {t["id"]: t for t in body["lessons"][0]["tests"]}
    practice = tests[str(course.test.id)]
    assert [q["answer_key"] for q in practice["questions"]] == [["a"]]
    # Оцінюваний тест із вікном: жодного поля з правильними відповідями на будь-якій глибині.
    graded_part = tests[str(graded.id)]
    assert len(graded_part["questions"]) == 1
    assert not keys(graded_part) & {"answer_key", "correct", "is_correct", "answers", "score"}
    assert b"answer_key" not in service.canonical_json(graded_part)


async def test_answer_key_change_changes_hash_only_for_practice(db_session, world, course) -> None:
    graded = await graded_test(db_session, course)
    body, _, _ = await service.build_content(db_session, world.class_a, course.day)
    digest = service.content_hash(body)
    # Ключ оцінюваного тесту в пакет не йде — хеш не змінюється.
    question = await db_session.scalar(select(Question).where(Question.test_id == graded.id))
    question.answer_key = ["a"]
    await db_session.flush()
    body, _, _ = await service.build_content(db_session, world.class_a, course.day)
    assert service.content_hash(body) == digest
    # Виправлений ключ тренувального тесту — новий хеш, а отже нова версія пакета.
    course.question.answer_key = ["b"]
    await db_session.flush()
    body, _, _ = await service.build_content(db_session, world.class_a, course.day)
    assert service.content_hash(body) != digest
    practice = next(t for t in body["lessons"][0]["tests"] if t["id"] == str(course.test.id))
    assert practice["questions"][0]["answer_key"] == ["b"]


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


# ---------- маніфест ----------


async def test_manifest(client: AsyncClient, db_session, world, course, media_storage) -> None:
    built = await rebuild(db_session, world)
    resp = await client.get(
        f"/packs/manifest?class_id={world.class_a.id}", headers=auth_header(world.student_a)
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["date_from"] == course.day.isoformat()
    assert data["date_to"] == (course.day + dt.timedelta(days=6)).isoformat()
    by_date = {p["pack_date"]: p for p in data["packs"]}
    for pack in built:
        item = by_date[pack.pack_date.isoformat()]
        assert item["id"] == str(pack.id) and item["version"] == pack.version
        assert item["content_hash"] == pack.content_hash
        assert item["size_bytes"] == pack.size_bytes
    # Медіа сьогоднішнього уроку: відео й субтитри окремими URL.
    media = {m["id"]: m for m in data["media"]}
    assert set(media) == {str(course.video.id), str(course.vtt.id)}
    video = media[str(course.video.id)]
    assert video["url"] == f"/media/{course.video.storage_key}"
    assert video["subtitles_id"] == str(course.vtt.id)
    assert video["needed_on"] == course.day.isoformat() and video["size_bytes"] == 5000


async def test_manifest_returns_latest_version(
    client: AsyncClient, db_session, world, course, media_storage
) -> None:
    await rebuild(db_session, world)
    course.lesson.version = 2
    await db_session.flush()
    (v2,) = await rebuild(db_session, world)
    resp = await client.get(
        f"/packs/manifest?class_id={world.class_a.id}&from={course.day}&to={course.day}",
        headers=auth_header(world.teacher_a),
    )
    assert [p["id"] for p in resp.json()["packs"]] == [str(v2.id)]


async def test_manifest_media_horizon(
    client: AsyncClient, db_session, world, course, media_storage
) -> None:
    # Відео стоїть післязавтра: текст пакета вже в маніфесті, медіа — ще ні.
    later = course.day + dt.timedelta(days=2)
    await db_session.execute(
        LessonAssignment.__table__.update()
        .where(LessonAssignment.lesson_id == course.lesson.id)
        .values(date=later)
    )
    slot = course.slots[0]
    slot.weekday = later.isoweekday()
    await db_session.flush()
    await rebuild(db_session, world)
    resp = await client.get(
        f"/packs/manifest?class_id={world.class_a.id}", headers=auth_header(world.admin)
    )
    data = resp.json()
    assert later.isoformat() in {p["pack_date"] for p in data["packs"]}
    assert data["media"] == []


@pytest.mark.parametrize(
    "query",
    ["from=2026-11-10&to=2026-11-09", "from=2026-11-01&to=2026-11-08"],
)
async def test_manifest_invalid_range(client: AsyncClient, world, query) -> None:
    resp = await client.get(
        f"/packs/manifest?class_id={world.class_a.id}&{query}",
        headers=auth_header(world.teacher_a),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.parametrize(
    ("role", "status"),
    [
        ("student_a", 200),
        ("teacher_a", 200),
        ("admin", 200),
        ("student_b", 403),
        ("teacher_b", 403),
        ("other_admin", 403),
        ("parent_a", 403),
    ],
)
async def test_manifest_access(client: AsyncClient, world, media_storage, role, status) -> None:
    resp = await client.get(
        f"/packs/manifest?class_id={world.class_a.id}", headers=auth_header(getattr(world, role))
    )
    assert resp.status_code == status


# ---------- завантаження пакета ----------


async def test_get_pack_etag_and_gzip(client: AsyncClient, db_session, world, course) -> None:
    pack = next(p for p in await rebuild(db_session, world) if p.pack_date == course.day)
    headers = {**auth_header(world.student_a), "Accept-Encoding": "gzip"}
    resp = await client.get(f"/packs/{pack.id}", headers=headers)
    assert resp.status_code == 200
    # httpx сам розпаковує gzip: тіло — JSON пакета.
    assert resp.headers["content-encoding"] == "gzip"
    assert resp.headers["etag"] == f'"{pack.content_hash}"'
    assert "Accept-Encoding" in resp.headers["vary"]
    # Власний кеш пакета, а не `no-store` за замовчуванням.
    assert resp.headers["cache-control"] == "private, no-cache"
    body = resp.json()
    assert body["id"] == str(pack.id) and body["version"] == 1
    assert body["lessons"][0]["id"] == str(course.lesson.id)

    plain = await client.get(
        f"/packs/{pack.id}", headers={**headers, "Accept-Encoding": "identity"}
    )
    assert "content-encoding" not in plain.headers and plain.json() == body

    cached = await client.get(
        f"/packs/{pack.id}", headers={**headers, "If-None-Match": resp.headers["etag"]}
    )
    assert cached.status_code == 304 and cached.content == b""
    assert cached.headers["etag"] == resp.headers["etag"]

    stale = await client.get(f"/packs/{pack.id}", headers={**headers, "If-None-Match": '"x"'})
    assert stale.status_code == 200


async def test_old_pack_version_still_downloadable(
    client: AsyncClient, db_session, world, course
) -> None:
    v1 = next(p for p in await rebuild(db_session, world) if p.pack_date == course.day)
    course.lesson.version = 2
    await db_session.flush()
    await rebuild(db_session, world)
    resp = await client.get(f"/packs/{v1.id}", headers=auth_header(world.student_a))
    assert resp.status_code == 200 and resp.json()["version"] == 1


@pytest.mark.parametrize(
    ("role", "status"),
    [
        ("student_a", 200),
        ("teacher_a", 200),
        ("admin", 200),
        ("student_b", 403),
        ("teacher_b", 403),
        ("other_admin", 403),
        ("parent_a", 403),
    ],
)
async def test_get_pack_access(
    client: AsyncClient, db_session, world, course, role, status
) -> None:
    pack = (await rebuild(db_session, world))[0]
    resp = await client.get(f"/packs/{pack.id}", headers=auth_header(getattr(world, role)))
    assert resp.status_code == status


async def test_get_pack_not_found(client: AsyncClient, world) -> None:
    resp = await client.get(f"/packs/{uuid.uuid4()}", headers=auth_header(world.teacher_a))
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


# ---------- регресії ----------


async def test_subtitle_change_rebuilds_packs_of_published_lessons(
    client: AsyncClient, db_session, world, course, enqueued
) -> None:
    (v1, _) = sorted(await rebuild(db_session, world), key=lambda p: p.pack_date)
    new_vtt = await media(db_session, world, "subtitles", "text/vtt", 1200)
    url = f"/media/{course.video.id}"
    body = {"subtitles_id": str(new_vtt.id)}
    resp = await client.patch(url, json=body, headers=auth_header(world.teacher_a))
    assert resp.status_code == 200, resp.text
    assert tasks(enqueued, "packs.rebuild_for_lesson") == [[str(course.lesson.id)]]
    # Повтор того самого запиту нічого не змінює й перезбірку не ставить.
    again = await client.patch(url, json=body, headers=auth_header(world.teacher_a))
    assert again.status_code == 200
    assert len(tasks(enqueued, "packs.rebuild_for_lesson")) == 1

    # Нові субтитри змінюють хеш → нова версія з новим файлом.
    built = await rebuild(db_session, world)
    v2 = next(p for p in built if p.pack_date == course.day)
    assert v2.version == 2 and v2.content_hash != v1.content_hash
    assert str(new_vtt.id) in content(v2)["media"]
    assert str(course.vtt.id) not in content(v2)["media"]


async def test_version_conflict_rebuilds_from_latest_data(
    db_session, world, course, monkeypatch
) -> None:
    (v1, _) = sorted(await rebuild(db_session, world), key=lambda p: p.pack_date)
    course.lesson.title = "Дроби (новіше)"
    course.lesson.version = 2
    await db_session.flush()

    # Емулюємо гонку: перше читання «не бачить» v1, тож спроба вставити v1 дає конфлікт.
    real = service.latest_pack
    calls = {"n": 0}

    async def stale_once(session, class_id, day):
        calls["n"] += 1
        return None if calls["n"] == 1 else await real(session, class_id, day)

    monkeypatch.setattr(service, "latest_pack", stale_once)
    pack, created = await service.build_pack(db_session, world.class_a, course.day, get_settings())
    assert created is True and pack.version == 2
    assert content(pack)["lessons"][0]["title"] == "Дроби (новіше)"
    assert pack.content_hash != v1.content_hash


async def test_rebuild_reads_schedule_once(db_session, world, course, monkeypatch) -> None:
    real = service.school_service.class_schedule
    calls: list[int] = []

    async def counting(session, klass, start, days):
        calls.append(days)
        return await real(session, klass, start, days)

    monkeypatch.setattr(service.school_service, "class_schedule", counting)
    await rebuild(db_session, world)
    assert calls == [service.HORIZON_DAYS]


async def test_pack_metadata_queries_skip_content(db_session, world, course) -> None:
    await rebuild(db_session, world)
    db_session.expunge_all()
    latest = await service.latest_pack(db_session, world.class_a.id, course.day)
    assert "content_gzip" in inspect(latest).unloaded
    week = await service._latest_packs(
        db_session, world.class_a.id, course.day, course.day + dt.timedelta(days=6)
    )
    assert len(week) == 2 and all("content_gzip" in inspect(p).unloaded for p in week)
    assert await service._week_size(db_session, world.class_a.id, course.day, course.day) > 0


@pytest.mark.parametrize(
    ("accept", "encoding"),
    [
        ("gzip", "gzip"),
        ("br, gzip;q=0.5", "br"),
        ("gzip, deflate, br", "br"),
        ("br;q=0.5, gzip", "gzip"),
        ("br;q=0, gzip", "gzip"),
        ("BR", "br"),
        ("GZIP; q=1.0", "gzip"),
        ("gzip;q=0", None),
        ("gzip;q=0.0, identity", None),
        ("*", "gzip"),
        ("*;q=0", None),
        ("identity, *;q=0", None),
        ("gzip;q=0, *", None),
        ("x-gzip", "gzip"),
        ("deflate, br", "br"),
        ("notgzip", None),
    ],
)
async def test_get_pack_accept_encoding_q_values(
    client: AsyncClient, db_session, world, course, accept, encoding
) -> None:
    pack = (await rebuild(db_session, world))[0]
    headers = {**auth_header(world.student_a), "Accept-Encoding": accept}
    resp = await client.get(f"/packs/{pack.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("content-encoding") == encoding
    # httpx розпаковує і brotli, і gzip.
    assert resp.json()["id"] == str(pack.id)


async def test_get_pack_brotli_smaller_and_gzip_fallback_for_old_packs(
    client: AsyncClient, db_session, world, course
) -> None:
    pack = (await rebuild(db_session, world))[0]
    assert pack.content_br is not None
    assert brotli.decompress(pack.content_br) == gzip.decompress(pack.content_gzip)
    assert len(pack.content_br) < len(pack.content_gzip)

    # Пакет, зібраний до появи brotli: клієнт просить br — отримує gzip.
    pack.content_br = None
    await db_session.commit()
    headers = {**auth_header(world.student_a), "Accept-Encoding": "br, gzip"}
    resp = await client.get(f"/packs/{pack.id}", headers=headers)
    assert resp.headers["content-encoding"] == "gzip"
    assert resp.json()["id"] == str(pack.id)
    only_br = await client.get(f"/packs/{pack.id}", headers={**headers, "Accept-Encoding": "br"})
    assert "content-encoding" not in only_br.headers and only_br.json()["id"] == str(pack.id)


async def test_day_lesson_ids_counts_only_effective_assignments(db_session, world, course) -> None:
    db = db_session
    assert await school_service.day_lesson_ids(db, world.class_a, course.day) == {course.lesson.id}

    # Прив'язка до слота, який цього дня не діє (інший день тижня), не рахується.
    other_day = ScheduleSlot(
        class_id=world.class_a.id,
        subject_id=course.subject.id,
        weekday=(course.day + dt.timedelta(days=1)).isoweekday(),
        starts_at=dt.time(11, 0),
        ends_at=dt.time(11, 45),
        valid_from=course.day - dt.timedelta(days=7),
    )
    db.add(other_day)
    await db.flush()
    db.add(LessonAssignment(slot_id=other_day.id, date=course.day, lesson_id=course.lesson2.id))
    # Скасований цього дня слот — теж.
    db.add(
        ScheduleOverride(
            class_id=world.class_a.id, slot_id=course.slots[0].id, date=course.day, kind="cancel"
        )
    )
    await db.flush()
    assert await school_service.day_lesson_ids(db, world.class_a, course.day) == set()
    tomorrow = course.day + dt.timedelta(days=1)
    assert (
        await school_service.day_lesson_ids(
            db, world.class_a, tomorrow, exclude_slot_id=course.slots[1].id
        )
        == set()
    )
