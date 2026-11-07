"""Уроки вчителя: CRUD, ідемпотентність, права, публікація з перевірками."""

import datetime as dt
import uuid

import pytest
from conftest import auth_header
from httpx import AsyncClient
from test_media import MP4, VTT, upload

from app.models.lessons import MediaAsset
from app.models.sync import ModuleProgress, SyncEvent

pytestmark = pytest.mark.anyio


def lesson_body(subject, **kw) -> dict:
    return {
        "id": str(kw.get("id", uuid.uuid4())),
        "subject_id": str(subject.id),
        "title": kw.get("title", "Звичайні дроби"),
        "shelter_part": kw.get("shelter_part", "Переглянь відео й розв'яжи задачі."),
        "main_part": "Розбір на уроці.",
        "grade": 7,
    }


async def create_lesson(client: AsyncClient, teacher, subject, **kw) -> dict:
    resp = await client.post(
        "/lessons", json=lesson_body(subject, **kw), headers=auth_header(teacher)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def add_module(
    client: AsyncClient, teacher, lesson_id: str, position: int = 1, part: str = "shelter"
):
    return await client.post(
        f"/lessons/{lesson_id}/modules",
        json={
            "id": str(uuid.uuid4()),
            "part": part,
            "position": position,
            "title": "Модуль",
            "duration_min": 4,
        },
        headers=auth_header(teacher),
    )


async def add_card(
    client: AsyncClient,
    teacher,
    module_id: str,
    kind: str = "text",
    media_id=None,
    position: int = 1,
):
    return await client.post(
        f"/modules/{module_id}/cards",
        json={
            "id": str(uuid.uuid4()),
            "position": position,
            "kind": kind,
            "body": {"text": "Дріб — це частина цілого"},
            "media_asset_id": media_id,
        },
        headers=auth_header(teacher),
    )


QUESTION = {
    "position": 1,
    "kind": "single",
    "prompt": "1/2 + 1/4 = ?",
    "options": [{"id": "a", "text": "3/4"}, {"id": "b", "text": "2/6"}],
    "answer_key": ["a"],
    "points": 1,
}


async def test_create_lesson_idempotent_and_roles(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    body = lesson_body(subject)
    headers = auth_header(world.teacher_a)
    first = await client.post("/lessons", json=body, headers=headers)
    assert first.status_code == 201
    assert first.json()["status"] == "draft" and first.json()["version"] == 1
    again = await client.post("/lessons", json=body, headers=headers)
    assert again.status_code == 200 and again.json()["id"] == body["id"]
    assert (
        await client.post("/lessons", json={**body, "title": "Інше"}, headers=headers)
    ).status_code == 409
    # Той самий id від іншого вчителя — конфлікт, а не чужий урок.
    assert (
        await client.post("/lessons", json=body, headers=auth_header(world.teacher_b))
    ).status_code == 409
    for user in (world.admin, world.student_a, world.parent_a):
        assert (
            await client.post("/lessons", json=lesson_body(subject), headers=auth_header(user))
        ).status_code == 403
    foreign = await factory.subject(world.other_school, "Чужий")
    assert (
        await client.post("/lessons", json=lesson_body(foreign), headers=headers)
    ).status_code == 404


async def test_lesson_tree_and_access(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    lesson = await create_lesson(client, world.teacher_a, subject)
    lid = lesson["id"]
    module = (await add_module(client, world.teacher_a, lid)).json()
    assert (await add_module(client, world.teacher_a, lid)).json()["error"][
        "code"
    ] == "POSITION_TAKEN"
    card = await add_card(client, world.teacher_a, module["id"])
    assert card.status_code == 201
    test = await client.post(
        f"/lessons/{lid}/tests",
        json={
            "id": str(uuid.uuid4()),
            "title": "Перевір себе",
            "window_enabled": True,
            "window_hours": 48,
        },
        headers=auth_header(world.teacher_a),
    )
    assert test.status_code == 201
    question = {**QUESTION, "id": str(uuid.uuid4())}
    q = await client.post(
        f"/tests/{test.json()['id']}/questions", json=question, headers=auth_header(world.teacher_a)
    )
    assert q.status_code == 201
    bad = {**QUESTION, "id": str(uuid.uuid4()), "position": 2, "answer_key": ["z"]}
    assert (
        await client.post(
            f"/tests/{test.json()['id']}/questions", json=bad, headers=auth_header(world.teacher_a)
        )
    ).status_code == 422

    full = await client.get(f"/lessons/{lid}", headers=auth_header(world.teacher_a))
    assert full.status_code == 200
    data = full.json()
    assert data["modules"][0]["cards"][0]["id"] == card.json()["id"]
    assert data["tests"][0]["questions"][0]["answer_key"] == ["a"]
    assert data["size_bytes"] > 0

    # Читають вчителі й адмін школи; інша школа, учень і батьки — ні.
    for user in (world.admin, world.teacher_b):
        assert (await client.get(f"/lessons/{lid}", headers=auth_header(user))).status_code == 200
    other_teacher = await factory.teacher(world.other_school)
    for user in (other_teacher, world.other_admin, world.student_a, world.parent_a):
        assert (await client.get(f"/lessons/{lid}", headers=auth_header(user))).status_code == 403
    # Пише лише автор: адмін не редагує контент вчителя, інший вчитель — теж.
    for user in (world.admin, world.teacher_b, world.student_a):
        h = auth_header(user)
        assert (
            await client.patch(f"/lessons/{lid}", json={"title": "X"}, headers=h)
        ).status_code == 403
        assert (
            await client.patch(f"/modules/{module['id']}", json={"title": "X"}, headers=h)
        ).status_code == 403
        assert (
            await client.patch(f"/cards/{card.json()['id']}", json={"body": {}}, headers=h)
        ).status_code == 403
        assert (await client.delete(f"/questions/{question['id']}", headers=h)).status_code == 403
        assert (await client.post(f"/lessons/{lid}/publish", headers=h)).status_code == 403
        assert (await client.delete(f"/lessons/{lid}", headers=h)).status_code == 403

    # Списки: вчитель — свої, адмін — школи.
    assert [
        x["id"] for x in (await client.get("/lessons", headers=auth_header(world.teacher_a))).json()
    ] == [lid]
    assert (await client.get("/lessons", headers=auth_header(world.teacher_b))).json() == []
    assert len((await client.get("/lessons", headers=auth_header(world.admin))).json()) == 1
    assert (await client.get("/lessons", headers=auth_header(world.other_admin))).json() == []

    # Правки чернетки й видалення вкладених елементів.
    h = auth_header(world.teacher_a)
    assert (
        await client.patch(
            f"/questions/{question['id']}",
            json={"kind": "multiple", "answer_key": ["a", "b"]},
            headers=h,
        )
    ).status_code == 200
    assert (
        await client.patch(f"/questions/{question['id']}", json={"kind": "single"}, headers=h)
    ).status_code == 422
    assert (
        await client.patch(f"/tests/{test.json()['id']}", json={"window_hours": None}, headers=h)
    ).status_code == 422
    assert (await client.delete(f"/questions/{question['id']}", headers=h)).status_code == 204
    assert (await client.delete(f"/modules/{module['id']}", headers=h)).status_code == 204
    assert (await client.get(f"/lessons/{lid}", headers=h)).json()["modules"] == []


async def test_card_media_rules(client: AsyncClient, world, factory, media_storage) -> None:
    subject = await factory.subject()
    lesson = await create_lesson(client, world.teacher_a, subject)
    module = (await add_module(client, world.teacher_a, lesson["id"])).json()
    video = (await upload(client, world.teacher_a, "video", "video/mp4", MP4)).json()
    foreign = (await upload(client, world.teacher_b, "video", "video/mp4", MP4)).json()
    assert (
        await add_card(client, world.teacher_a, module["id"], "image", video["id"])
    ).status_code == 422
    assert (
        await add_card(client, world.teacher_a, module["id"], "video", foreign["id"])
    ).status_code == 404
    assert (await add_card(client, world.teacher_a, module["id"], "video", None)).status_code == 422
    assert (
        await add_card(client, world.teacher_a, module["id"], "video", video["id"])
    ).status_code == 201


async def test_publish_checks_and_edit_cycle(
    client: AsyncClient, world, factory, media_storage
) -> None:
    subject = await factory.subject()
    h = auth_header(world.teacher_a)
    lesson = await create_lesson(client, world.teacher_a, subject, shelter_part="   ")
    lid = lesson["id"]
    module = (await add_module(client, world.teacher_a, lid)).json()
    video = (await upload(client, world.teacher_a, "video", "video/mp4", MP4)).json()
    card = (await add_card(client, world.teacher_a, module["id"], "video", video["id"])).json()

    failed = await client.post(f"/lessons/{lid}/publish", headers=h)
    assert failed.status_code == 422
    err = failed.json()["error"]
    assert err["code"] == "LESSON_NOT_PUBLISHABLE"
    # Усі провалені перевірки разом.
    assert {d["check"] for d in err["details"]} == {"shelter_part", "video_subtitles"}
    sub_detail = next(d for d in err["details"] if d["check"] == "video_subtitles")
    assert sub_detail["card_id"] == card["id"] and sub_detail["media_asset_id"] == video["id"]

    vtt = (await upload(client, world.teacher_a, "subtitles", "text/vtt", VTT)).json()
    await client.patch(f"/media/{video['id']}", json={"subtitles_id": vtt["id"]}, headers=h)
    await client.patch(f"/lessons/{lid}", json={"shelter_part": "Переглянь відео"}, headers=h)
    published = await client.post(f"/lessons/{lid}/publish", headers=h)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published" and published.json()["version"] == 1
    # Ідемпотентно.
    again = await client.post(f"/lessons/{lid}/publish", headers=h)
    assert again.status_code == 200 and again.json()["version"] == 1

    # Опублікований урок незмінний.
    locked = await client.patch(f"/lessons/{lid}", json={"title": "Нове"}, headers=h)
    assert locked.status_code == 409 and locked.json()["error"]["code"] == "LESSON_PUBLISHED"
    assert (await add_module(client, world.teacher_a, lid, 2)).status_code == 409
    assert (await client.delete(f"/cards/{card['id']}", headers=h)).status_code == 409
    assert (await client.delete(f"/lessons/{lid}", headers=h)).status_code == 409
    # Відв'язати субтитри від відео опублікованого уроку не можна.
    assert (
        await client.patch(f"/media/{video['id']}", json={"subtitles_id": None}, headers=h)
    ).status_code == 409

    # Зняти з публікації → правка → нова публікація = нова версія.
    assert (await client.post(f"/lessons/{lid}/unpublish", headers=h)).json()["status"] == "draft"
    assert (
        await client.patch(f"/lessons/{lid}", json={"title": "Нове"}, headers=h)
    ).status_code == 200
    republished = await client.post(f"/lessons/{lid}/publish", headers=h)
    assert republished.json()["version"] == 2
    # Адмін не публікує й не знімає з публікації.
    assert (
        await client.post(f"/lessons/{lid}/unpublish", headers=auth_header(world.admin))
    ).status_code == 403


async def test_publish_size_limit(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    lesson = await create_lesson(client, world.teacher_a, subject)
    module = (await add_module(client, world.teacher_a, lesson["id"])).json()
    media = MediaAsset(
        kind="image",
        storage_key=f"image/{uuid.uuid4()}.png",
        mime_type="image/png",
        size_bytes=51 * 1024 * 1024,
        sha256="0" * 64,
        source_sha256="0" * 64,
        uploaded_by=world.teacher_a.id,
    )
    factory.session.add(media)
    await factory.session.flush()
    assert (
        await add_card(client, world.teacher_a, module["id"], "image", str(media.id))
    ).status_code == 201
    resp = await client.post(
        f"/lessons/{lesson['id']}/publish", headers=auth_header(world.teacher_a)
    )
    assert resp.status_code == 422
    (detail,) = resp.json()["error"]["details"]
    assert detail["check"] == "lesson_size" and detail["limit_bytes"] == 50 * 1024 * 1024


async def test_scheduled_lesson_cannot_be_deleted(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    h = auth_header(world.teacher_a)
    draft = await create_lesson(client, world.teacher_a, subject)
    assert (await client.delete(f"/lessons/{draft['id']}", headers=h)).status_code == 204
    assert (await client.get(f"/lessons/{draft['id']}", headers=h)).status_code == 404

    lesson = await create_lesson(client, world.teacher_a, subject)
    assert (await client.post(f"/lessons/{lesson['id']}/publish", headers=h)).status_code == 200
    slot = await client.post(
        f"/classes/{world.class_a.id}/schedule/slots",
        json={
            "id": str(uuid.uuid4()),
            "subject_id": str(subject.id),
            "weekday": 1,
            "starts_at": "09:00:00",
            "ends_at": "09:45:00",
            "valid_from": "2026-09-01",
        },
        headers=auth_header(world.admin),
    )
    day = dt.date(2026, 11, 9)
    assigned = await client.put(
        f"/classes/{world.class_a.id}/schedule/slots/{slot.json()['id']}/lessons/{day}",
        json={"lesson_id": lesson["id"]},
        headers=h,
    )
    assert assigned.status_code == 200
    await client.post(f"/lessons/{lesson['id']}/unpublish", headers=h)
    resp = await client.delete(f"/lessons/{lesson['id']}", headers=h)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "LESSON_IN_USE"
    # Після відмови сесія робоча, урок на місці.
    assert (await client.get(f"/lessons/{lesson['id']}", headers=h)).status_code == 200


async def test_subjects(client: AsyncClient, world, factory) -> None:
    await factory.subject(None, "Українська мова")
    await factory.subject(world.other_school, "Чужий")
    body = {"id": str(uuid.uuid4()), "name": "Робототехніка"}
    assert (
        await client.post("/subjects", json=body, headers=auth_header(world.admin))
    ).status_code == 201
    assert (
        await client.post("/subjects", json=body, headers=auth_header(world.admin))
    ).status_code == 200
    assert (
        await client.post("/subjects", json=body, headers=auth_header(world.teacher_a))
    ).status_code == 403
    names = {
        s["name"]
        for s in (await client.get("/subjects", headers=auth_header(world.teacher_a))).json()
    }
    assert names == {"Українська мова", "Робототехніка"}


async def test_module_with_progress_cannot_be_deleted(client: AsyncClient, world, factory) -> None:
    """Прогрес учнів — результати: видалення модуля (каскад на `module_progress`) чи уроку
    не має його тихо стерти."""
    subject = await factory.subject()
    h = auth_header(world.teacher_a)
    lesson = await create_lesson(client, world.teacher_a, subject)
    module = (await add_module(client, world.teacher_a, lesson["id"])).json()
    spare = (await add_module(client, world.teacher_a, lesson["id"], position=2)).json()
    event_id = uuid.uuid4()
    now = dt.datetime.now(dt.UTC)
    factory.session.add(
        SyncEvent(
            client_event_id=event_id,
            type="module_progress",
            user_id=world.student_a.id,
            device_id=uuid.uuid4(),
            occurred_at=now,
            payload={},
            status="accepted",
        )
    )
    await factory.session.flush()
    factory.session.add(
        ModuleProgress(
            student_id=world.student_a.id,
            module_id=uuid.UUID(module["id"]),
            progress_pct=50,
            last_event_id=event_id,
        )
    )
    await factory.session.flush()

    resp = await client.delete(f"/modules/{module['id']}", headers=h)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "IN_USE"
    resp = await client.delete(f"/lessons/{lesson['id']}", headers=h)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "LESSON_IN_USE"
    # Модуль без прогресу видаляється як і раніше.
    assert (await client.delete(f"/modules/{spare['id']}", headers=h)).status_code == 204
    assert (
        await factory.session.get(ModuleProgress, (world.student_a.id, uuid.UUID(module["id"])))
    ) is not None
