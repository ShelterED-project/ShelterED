"""Класи (адміністрація), вчителі класу, код класу, розклад і прив'язка уроків."""

import datetime as dt
import uuid

import pytest
from conftest import auth_header
from httpx import AsyncClient
from sqlalchemy import select

from app.models.lessons import Card, Lesson, MediaAsset, Module
from app.models.school import ClassMembership, LessonAssignment, SchoolClass

pytestmark = pytest.mark.anyio

MONDAY = dt.date(2026, 11, 9)


def class_body(name: str = "8-А", **kw) -> dict:
    return {
        "id": str(kw.get("id", uuid.uuid4())),
        "name": name,
        "grade": 8,
        "academic_year": "2026/2027",
    }


# ---------- класи ----------


async def test_admin_creates_class_idempotently(client: AsyncClient, world, db_session) -> None:
    headers = auth_header(world.admin)
    body = class_body()
    first = await client.post("/classes", json=body, headers=headers)
    assert first.status_code == 201, first.text
    data = first.json()
    assert data["school_id"] == str(world.school.id)
    assert data["join_code"].isalnum() and data["join_code"].isupper()
    # Повтор (обрив до відповіді) — той самий клас, код не змінився.
    again = await client.post("/classes", json=body, headers=headers)
    assert again.status_code == 200
    assert again.json() == data
    count = await db_session.scalar(
        select(SchoolClass.id).where(SchoolClass.id == uuid.UUID(body["id"]))
    )
    assert count is not None
    # Той самий id з іншими даними — 409.
    conflict = await client.post("/classes", json={**body, "grade": 9}, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "ID_CONFLICT"
    # Чужа школа не може «перехопити» id.
    other = await client.post("/classes", json=body, headers=auth_header(world.other_admin))
    assert other.status_code == 409


async def test_class_name_unique_per_year(client: AsyncClient, world) -> None:
    headers = auth_header(world.admin)
    dup = await client.post("/classes", json=class_body("7-А"), headers=headers)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "CLASS_NAME_TAKEN"
    # Та сама назва в іншій школі — можна.
    ok = await client.post(
        "/classes", json=class_body("7-А"), headers=auth_header(world.other_admin)
    )
    assert ok.status_code == 201


async def test_only_admin_manages_classes(client: AsyncClient, world) -> None:
    for user in (world.teacher_a, world.student_a, world.parent_a):
        assert (
            await client.post("/classes", json=class_body(), headers=auth_header(user))
        ).status_code == 403
        assert (
            await client.patch(
                f"/classes/{world.class_a.id}", json={"name": "X"}, headers=auth_header(user)
            )
        ).status_code == 403
    assert (await client.post("/classes", json=class_body())).status_code == 401


async def test_cross_school_admin_denied(client: AsyncClient, world) -> None:
    headers = auth_header(world.other_admin)
    cid = world.class_a.id
    assert (await client.get(f"/classes/{cid}", headers=headers)).status_code == 403
    assert (
        await client.patch(f"/classes/{cid}", json={"name": "X"}, headers=headers)
    ).status_code == 403
    assert (await client.delete(f"/classes/{cid}", headers=headers)).status_code == 403
    assert (await client.post(f"/classes/{cid}/join-code", headers=headers)).status_code == 403
    assert (
        await client.put(f"/classes/{cid}/teachers/{world.teacher_a.id}", headers=headers)
    ).status_code == 403


async def test_list_and_update_class(client: AsyncClient, world) -> None:
    admin = await client.get("/classes", headers=auth_header(world.admin))
    assert {c["name"] for c in admin.json()} == {"7-А", "7-Б"}
    teacher = await client.get("/classes", headers=auth_header(world.teacher_a))
    assert [c["id"] for c in teacher.json()] == [str(world.class_a.id)]
    assert teacher.json()[0]["teacher_ids"] == [str(world.teacher_a.id)]
    resp = await client.patch(
        f"/classes/{world.class_a.id}", json={"name": "7-В"}, headers=auth_header(world.admin)
    )
    assert resp.status_code == 200 and resp.json()["name"] == "7-В"
    taken = await client.patch(
        f"/classes/{world.class_a.id}", json={"name": "7-Б"}, headers=auth_header(world.admin)
    )
    assert taken.status_code == 409


async def test_delete_class_only_without_students(client: AsyncClient, world, factory) -> None:
    headers = auth_header(world.admin)
    busy = await client.delete(f"/classes/{world.class_a.id}", headers=headers)
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "CLASS_NOT_EMPTY"
    empty = await factory.klass(world.school, "11-Б")
    assert (await client.delete(f"/classes/{empty.id}", headers=headers)).status_code == 204
    assert (await client.get(f"/classes/{empty.id}", headers=headers)).status_code == 404


async def test_regenerate_join_code(client: AsyncClient, world) -> None:
    old = world.class_a.join_code
    resp = await client.post(
        f"/classes/{world.class_a.id}/join-code",
        json={"expires_in_days": 7},
        headers=auth_header(world.admin),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["join_code"] != old and body["join_code_expires_at"] is not None
    # Старим кодом новий учень не увійде.
    join = await client.post(
        "/auth/student/join",
        json={"join_code": old, "display_name": "Нова", "last_name": "Учениця", "pin": "1111"},
    )
    assert join.status_code == 400
    ok = await client.post(
        "/auth/student/join",
        json={
            "join_code": body["join_code"],
            "display_name": "Нова",
            "last_name": "Учениця",
            "pin": "1111",
        },
    )
    assert ok.status_code == 200
    # Вчитель класу код не генерує.
    assert (
        await client.post(
            f"/classes/{world.class_a.id}/join-code", headers=auth_header(world.teacher_a)
        )
    ).status_code == 403


async def test_assign_and_unassign_teacher(client: AsyncClient, world, db_session) -> None:
    headers = auth_header(world.admin)
    url = f"/classes/{world.class_a.id}/teachers/{world.teacher_b.id}"
    assert (await client.put(url, headers=headers)).status_code == 204
    assert (await client.put(url, headers=headers)).status_code == 204  # ідемпотентно
    # Тепер вчитель B бачить клас A.
    assert (
        await client.get(f"/classes/{world.class_a.id}", headers=auth_header(world.teacher_b))
    ).status_code == 200
    assert (await client.delete(url, headers=headers)).status_code == 204
    assert (await client.delete(url, headers=headers)).status_code == 204
    assert (
        await client.get(f"/classes/{world.class_a.id}", headers=auth_header(world.teacher_b))
    ).status_code == 403
    # Учня, батьків чи вчителя іншої школи призначити не можна.
    for user_id in (world.student_a.id, world.parent_a.id, uuid.uuid4()):
        resp = await client.put(f"/classes/{world.class_a.id}/teachers/{user_id}", headers=headers)
        assert resp.status_code == 404
    rows = await db_session.scalars(
        select(ClassMembership).where(ClassMembership.class_id == world.class_a.id)
    )
    assert {r.member_role for r in rows} == {"teacher", "student"}


# ---------- розклад ----------


async def make_slot(client: AsyncClient, world, subject, **kw) -> dict:
    body = {
        "id": str(uuid.uuid4()),
        "subject_id": str(subject.id),
        "weekday": kw.get("weekday", 1),
        "starts_at": kw.get("starts_at", "09:00:00"),
        "ends_at": kw.get("ends_at", "09:45:00"),
        "valid_from": "2026-09-01",
        "valid_to": None,
    }
    klass = kw.get("klass", world.class_a)
    resp = await client.post(
        f"/classes/{klass.id}/schedule/slots", json=body, headers=auth_header(world.admin)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_slot_crud_and_roles(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    slot = await make_slot(client, world, subject)
    base = f"/classes/{world.class_a.id}/schedule/slots"
    admin = auth_header(world.admin)
    # Повтор створення — 200, той самий слот.
    body = {
        k: slot[k]
        for k in ("id", "subject_id", "weekday", "starts_at", "ends_at", "valid_from", "valid_to")
    }
    assert (await client.post(base, json=body, headers=admin)).status_code == 200
    assert (await client.post(base, json={**body, "weekday": 2}, headers=admin)).status_code == 409
    # Читають вчитель і учень класу, пише лише адмін.
    for user in (world.teacher_a, world.student_a):
        listed = await client.get(base, headers=auth_header(user))
        assert listed.status_code == 200 and len(listed.json()) == 1
        assert (
            await client.post(
                base, json={**body, "id": str(uuid.uuid4())}, headers=auth_header(user)
            )
        ).status_code == 403
    for user in (world.teacher_b, world.parent_a, world.other_admin):
        assert (await client.get(base, headers=auth_header(user))).status_code == 403
    # Оновлення з перевіркою часу.
    patched = await client.patch(
        f"{base}/{slot['id']}", json={"ends_at": "09:50:00"}, headers=admin
    )
    assert patched.status_code == 200 and patched.json()["ends_at"] == "09:50:00"
    bad = await client.patch(f"{base}/{slot['id']}", json={"ends_at": "08:00:00"}, headers=admin)
    assert bad.status_code == 422
    # Слот іншого класу через цей клас не знайти.
    assert (
        await client.patch(
            f"/classes/{world.class_b.id}/schedule/slots/{slot['id']}", json={}, headers=admin
        )
    ).status_code == 404
    assert (await client.delete(f"{base}/{slot['id']}", headers=admin)).status_code == 204
    assert (await client.get(base, headers=admin)).json() == []


async def test_slot_rejects_foreign_subject(client: AsyncClient, world, factory) -> None:
    foreign = await factory.subject(world.other_school, "Чужий предмет")
    resp = await client.post(
        f"/classes/{world.class_a.id}/schedule/slots",
        json={
            "id": str(uuid.uuid4()),
            "subject_id": str(foreign.id),
            "weekday": 1,
            "starts_at": "09:00:00",
            "ends_at": "09:45:00",
            "valid_from": "2026-09-01",
        },
        headers=auth_header(world.admin),
    )
    assert resp.status_code == 404


async def test_week_schedule_with_overrides(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    other = await factory.subject(world.school, "Історія")
    s1 = await make_slot(client, world, subject)
    s2 = await make_slot(client, world, subject, starts_at="10:00:00", ends_at="10:45:00")
    admin = auth_header(world.admin)
    base = f"/classes/{world.class_a.id}/schedule/overrides"
    cancel = {"id": str(uuid.uuid4()), "date": str(MONDAY), "kind": "cancel", "slot_id": s1["id"]}
    assert (await client.post(base, json=cancel, headers=admin)).status_code == 201
    assert (await client.post(base, json=cancel, headers=admin)).status_code == 200
    # Друге перевизначення того самого слота на дату — 409.
    dup = {**cancel, "id": str(uuid.uuid4())}
    assert (await client.post(base, json=dup, headers=admin)).json()["error"][
        "code"
    ] == "OVERRIDE_EXISTS"
    # Слот не в цей день тижня — 422.
    wrong_day = {**cancel, "id": str(uuid.uuid4()), "date": str(MONDAY + dt.timedelta(days=1))}
    assert (await client.post(base, json=wrong_day, headers=admin)).status_code == 422
    replace = {
        "id": str(uuid.uuid4()),
        "date": str(MONDAY),
        "kind": "replace",
        "slot_id": s2["id"],
        "subject_id": str(other.id),
    }
    assert (await client.post(base, json=replace, headers=admin)).status_code == 201
    extra = {
        "id": str(uuid.uuid4()),
        "date": str(MONDAY + dt.timedelta(days=2)),
        "kind": "extra",
        "subject_id": str(subject.id),
        "starts_at": "14:00:00",
        "ends_at": "14:45:00",
    }
    assert (await client.post(base, json=extra, headers=admin)).status_code == 201
    # Невалідне перевизначення: extra без часу.
    assert (
        await client.post(
            base,
            json={**extra, "id": str(uuid.uuid4()), "starts_at": None, "ends_at": None},
            headers=admin,
        )
    ).status_code == 422

    resp = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": str(MONDAY)},
        headers=auth_header(world.student_a),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["timezone"] == "Europe/Kyiv"
    days = body["days"]
    assert len(days) == 7 and days[0]["date"] == str(MONDAY)
    assert [(i["kind"], i["subject_id"]) for i in days[0]["items"]] == [("replaced", str(other.id))]
    assert days[0]["items"][0]["starts_at_utc"] == "2026-11-09T08:00:00Z"
    assert [i["kind"] for i in days[2]["items"]] == ["extra"]
    assert days[1]["items"] == []
    # Наступний понеділок — звичайний.
    nxt = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": str(MONDAY + dt.timedelta(days=7)), "days": 1},
        headers=auth_header(world.admin),
    )
    assert [i["kind"] for i in nxt.json()["days"][0]["items"]] == ["regular", "regular"]
    listed = await client.get(base, params={"from": str(MONDAY), "to": str(MONDAY)}, headers=admin)
    assert len(listed.json()) == 2
    assert (await client.delete(f"{base}/{cancel['id']}", headers=admin)).status_code == 204
    assert (await client.delete(f"{base}/{cancel['id']}", headers=admin)).status_code == 204
    # Батьки й чужий вчитель розклад класу не бачать.
    for user in (world.parent_a, world.teacher_b):
        assert (
            await client.get(f"/classes/{world.class_a.id}/schedule", headers=auth_header(user))
        ).status_code == 403


async def test_current_lesson_endpoint_dst(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    slot = await make_slot(client, world, subject)
    url = f"/classes/{world.class_a.id}/schedule/current"
    headers = auth_header(world.teacher_a)
    # Понеділок 26.10.2026, 07:30 UTC = 09:30 EET (після переходу 25.10) — урок іде.
    after = await client.get(url, params={"at": "2026-10-26T07:30:00Z"}, headers=headers)
    assert after.status_code == 200
    assert after.json()["item"]["slot_id"] == slot["id"]
    assert after.json()["date"] == "2026-10-26"
    # Тиждень тому 07:30 UTC = 10:30 EEST — уже ні.
    before = await client.get(url, params={"at": "2026-10-19T07:30:00Z"}, headers=headers)
    assert before.json()["item"] is None
    # Без поясу — 422; без параметра — поточний момент.
    assert (
        await client.get(url, params={"at": "2026-10-26T07:30:00"}, headers=headers)
    ).status_code == 422
    assert (await client.get(url, headers=headers)).status_code == 200


# ---------- прив'язка уроку до слота ----------


async def published_lesson(factory, teacher, subject, title: str = "Урок") -> Lesson:
    lesson = Lesson(
        subject_id=subject.id,
        author_id=teacher.id,
        title=title,
        shelter_part="Укриття",
        main_part="",
        status="published",
        published_at=dt.datetime.now(dt.UTC),
    )
    factory.session.add(lesson)
    await factory.session.flush()
    return lesson


async def test_teacher_assigns_lesson_to_slot(
    client: AsyncClient, world, factory, db_session
) -> None:
    subject = await factory.subject()
    slot = await make_slot(client, world, subject)
    lesson = await published_lesson(factory, world.teacher_a, subject)
    url = f"/classes/{world.class_a.id}/schedule/slots/{slot['id']}/lessons/{MONDAY}"
    headers = auth_header(world.teacher_a)
    resp = await client.put(url, json={"lesson_id": str(lesson.id)}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["pack_day_bytes"] > 0
    assert (
        await client.put(url, json={"lesson_id": str(lesson.id)}, headers=headers)
    ).status_code == 200
    rows = list(await db_session.scalars(select(LessonAssignment)))
    assert len(rows) == 1
    sched = await client.get(
        f"/classes/{world.class_a.id}/schedule",
        params={"from": str(MONDAY), "days": 1},
        headers=headers,
    )
    assert sched.json()["days"][0]["items"][0]["lesson_id"] == str(lesson.id)
    # Не той день тижня — 422; адмін, вчитель іншого класу, учень — 403.
    wrong = url.replace(str(MONDAY), str(MONDAY + dt.timedelta(days=1)))
    assert (
        await client.put(wrong, json={"lesson_id": str(lesson.id)}, headers=headers)
    ).status_code == 422
    for user in (world.admin, world.teacher_b, world.student_a, world.parent_a):
        assert (
            await client.put(url, json={"lesson_id": str(lesson.id)}, headers=auth_header(user))
        ).status_code == 403
    assert (await client.delete(url, headers=headers)).status_code == 204
    assert list(await db_session.scalars(select(LessonAssignment))) == []


async def test_assignment_requires_published_and_not_cancelled(
    client: AsyncClient, world, factory
) -> None:
    subject = await factory.subject()
    slot = await make_slot(client, world, subject)
    lesson = await published_lesson(factory, world.teacher_a, subject)
    lesson.status = "draft"
    await factory.session.flush()
    url = f"/classes/{world.class_a.id}/schedule/slots/{slot['id']}/lessons/{MONDAY}"
    headers = auth_header(world.teacher_a)
    resp = await client.put(url, json={"lesson_id": str(lesson.id)}, headers=headers)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "LESSON_NOT_PUBLISHED"
    lesson.status = "published"
    await factory.session.flush()
    await client.post(
        f"/classes/{world.class_a.id}/schedule/overrides",
        json={
            "id": str(uuid.uuid4()),
            "date": str(MONDAY),
            "kind": "cancel",
            "slot_id": slot["id"],
        },
        headers=auth_header(world.admin),
    )
    resp = await client.put(url, json={"lesson_id": str(lesson.id)}, headers=headers)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "SLOT_CANCELLED"
    # Урок вчителя іншої школи — 404.
    foreign_teacher = await factory.teacher(world.other_school)
    foreign = await published_lesson(factory, foreign_teacher, subject)
    url2 = url.replace(str(MONDAY), str(MONDAY + dt.timedelta(days=7)))
    assert (
        await client.put(url2, json={"lesson_id": str(foreign.id)}, headers=headers)
    ).status_code == 404


async def test_day_pack_limit(client: AsyncClient, world, factory) -> None:
    subject = await factory.subject()
    s1 = await make_slot(client, world, subject)
    s2 = await make_slot(client, world, subject, starts_at="10:00:00", ends_at="10:45:00")
    headers = auth_header(world.teacher_a)
    lessons = []
    for n in range(2):
        lesson = await published_lesson(factory, world.teacher_a, subject, f"Урок {n}")
        # Великий файл (30 МБ) у кожному уроці — без справжнього файла на диску.
        media = MediaAsset(
            kind="image",
            storage_key=f"image/{uuid.uuid4()}.png",
            mime_type="image/png",
            size_bytes=30 * 1024 * 1024,
            sha256="0" * 64,
            uploaded_by=world.teacher_a.id,
        )
        factory.session.add(media)
        await factory.session.flush()
        module = Module(lesson_id=lesson.id, part="shelter", position=1, title="М", duration_min=4)
        factory.session.add(module)
        await factory.session.flush()
        factory.session.add(
            Card(module_id=module.id, position=1, kind="image", body={}, media_asset_id=media.id)
        )
        await factory.session.flush()
        lessons.append(lesson)
    base = f"/classes/{world.class_a.id}/schedule/slots"
    ok = await client.put(
        f"{base}/{s1['id']}/lessons/{MONDAY}",
        json={"lesson_id": str(lessons[0].id)},
        headers=headers,
    )
    assert ok.status_code == 200
    over = await client.put(
        f"{base}/{s2['id']}/lessons/{MONDAY}",
        json={"lesson_id": str(lessons[1].id)},
        headers=headers,
    )
    assert over.status_code == 422
    err = over.json()["error"]
    assert err["code"] == "PACK_DAY_LIMIT_EXCEEDED"
    assert err["details"]["limit_bytes"] == 50 * 1024 * 1024
    # Той самий урок двічі на день рахується один раз; заміна уроку в слоті не додає старий.
    same = await client.put(
        f"{base}/{s2['id']}/lessons/{MONDAY}",
        json={"lesson_id": str(lessons[0].id)},
        headers=headers,
    )
    assert same.status_code == 200
    replace = await client.put(
        f"{base}/{s1['id']}/lessons/{MONDAY + dt.timedelta(days=7)}",
        json={"lesson_id": str(lessons[1].id)},
        headers=headers,
    )
    assert replace.status_code == 200


# ---------- користувачі школи (вибір вчителя для класу) ----------


async def test_admin_lists_school_users_by_role(client: AsyncClient, world) -> None:
    headers = auth_header(world.admin)
    response = await client.get("/admin/users", params={"role": "teacher"}, headers=headers)
    assert response.status_code == 200, response.text
    ids = {u["id"] for u in response.json()}
    assert ids == {str(world.teacher_a.id), str(world.teacher_b.id)}
    assert all(u["role"] == "teacher" for u in response.json())
    # Пагінація.
    page = await client.get(
        "/admin/users", params={"role": "teacher", "limit": 1, "offset": 1}, headers=headers
    )
    assert len(page.json()) == 1 and page.json()[0]["id"] in ids
    # Без фільтра — уся школа, без користувачів іншої школи й батьків.
    everyone = {u["id"] for u in (await client.get("/admin/users", headers=headers)).json()}
    assert str(world.student_a.id) in everyone
    assert str(world.student_c.id) not in everyone and str(world.other_admin.id) not in everyone
    assert str(world.parent_a.id) not in everyone
    # Інша школа бачить лише своїх.
    other = await client.get(
        "/admin/users", params={"role": "teacher"}, headers=auth_header(world.other_admin)
    )
    assert other.json() == []


async def test_only_admin_lists_users(client: AsyncClient, world) -> None:
    for user in (world.teacher_a, world.student_a, world.parent_a):
        response = await client.get("/admin/users", headers=auth_header(user))
        assert response.status_code == 403
    assert (await client.get("/admin/users")).status_code == 401
    bad = await client.get(
        "/admin/users", params={"role": "parent"}, headers=auth_header(world.admin)
    )
    assert bad.status_code == 422
