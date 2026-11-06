"""Видалення даних учня на запит батьків або школи (B15.5): запит, підтвердження, відхилення,
повне видалення пов'язаних даних, журнал без персональних даних, доступ за ролями."""

import datetime as dt
import uuid

import pytest
from conftest import auth_header
from sqlalchemy import func, select
from test_sync import attempt, batch, content, event, progress, rollcall, send

from app.models import Base
from app.models.auth import AuthCode, ParentLinkCode, RefreshToken
from app.models.privacy import DataDeletionLog, DataDeletionRequest
from app.models.push import PushSubscription
from app.models.school import User
from app.models.wellbeing import WellbeingViewLog
from app.services import stats as stats_service
from app.services.privacy import student_hash

pytestmark = pytest.mark.anyio


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def create(client, user, student, request_id=None, reason="left_school"):
    body = {"id": str(request_id or uuid.uuid4()), "reason": reason}
    return await client.post(
        f"/students/{student.id}/deletion-requests", json=body, headers=auth_header(user)
    )


async def fill_student_data(db, factory, world) -> None:
    """Дані учня в усіх таблицях, що на нього посилаються."""
    student = world.student_a
    c = await content(db, factory, world.class_a, world.teacher_a)
    t = now()
    events = [
        progress(c.module.id, 100, t - dt.timedelta(minutes=5), completed=t),
        attempt(c.test.id, {c.q1.id: ["a"], c.q2.id: ["a", "c"]}, t - dt.timedelta(minutes=1)),
        rollcall(c.rc.id, "in_shelter", t),
        event("survey_answer", {"value": 4}),
    ]
    results = await send(world.client, student, batch(*events))
    assert all(r["status"] == "accepted" for r in results)
    await stats_service.recompute_student_rows(db, student.id)
    expires = t + dt.timedelta(days=1)
    db.add_all(
        [
            RefreshToken(
                user_id=student.id,
                family_id=uuid.uuid4(),
                token_hash=uuid.uuid4().hex,
                expires_at=expires,
            ),
            AuthCode(
                code_hash=uuid.uuid4().hex,
                user_id=student.id,
                code_challenge="x",
                client_id="sheltered-pwa",
                expires_at=expires,
            ),
            ParentLinkCode(code_hash=uuid.uuid4().hex, child_id=student.id, expires_at=expires),
            WellbeingViewLog(viewer_id=world.parent_a.id, student_id=student.id),
            PushSubscription(
                user_id=student.id, endpoint="https://fcm.googleapis.com/x", p256dh="p", auth="a"
            ),
        ]
    )
    await db.flush()


async def rows_referencing(db, user_id: uuid.UUID) -> dict[str, int]:
    """Кількість рядків у кожній таблиці, де будь-який FK на app_user дорівнює user_id."""
    found: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if any(fk.column.table.name == "app_user" for fk in column.foreign_keys) or (
                table.name == "app_user" and column.name == "id"
            ):
                n = await db.scalar(
                    select(func.count()).select_from(table).where(column == user_id)
                )
                if n:
                    found[f"{table.name}.{column.name}"] = n
    return found


@pytest.fixture
def w(world, client):
    world.client = client
    return world


async def test_parent_requests_admin_confirms_and_all_child_data_is_gone(
    client, db_session, factory, w, enqueued
) -> None:
    await fill_student_data(db_session, factory, w)
    student_id = w.student_a.id
    before = await rows_referencing(db_session, student_id)
    for table in (
        "sync_event.user_id",
        "attempt.student_id",
        "module_progress.student_id",
        "rollcall_status.student_id",
        "wellbeing_answer.student_id",
        "student_lesson_stat.student_id",
        "parent_child.child_id",
        "class_membership.user_id",
    ):
        assert before.get(table), table

    r = await create(client, w.parent_a, w.student_a)
    assert r.status_code == 201, r.text
    req = r.json()
    assert req["status"] == "pending" and req["requested_by_role"] == "parent"
    assert req["student_name"] == "Іван Петренко"

    pending = await client.get(
        "/deletion-requests", params={"status": "pending"}, headers=auth_header(w.admin)
    )
    assert [x["id"] for x in pending.json()] == [req["id"]]

    r = await client.post(f"/deletion-requests/{req['id']}/confirm", headers=auth_header(w.admin))
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "confirmed" and done["student_id"] is None
    assert done["student_name"] is None

    assert await rows_referencing(db_session, student_id) == {}
    assert await db_session.get(User, w.parent_a.id) is not None
    row = await db_session.get(DataDeletionRequest, uuid.UUID(req["id"]))
    assert row.student_id is None and row.student_hash == student_hash(student_id)
    log = await db_session.scalar(select(DataDeletionLog))
    assert log.request_id == row.id and log.confirmed_by == w.admin.id
    assert log.student_hash == student_hash(student_id) and log.requested_by_role == "parent"
    assert any(
        c.name == "stats.recompute_class" and c.args == [str(w.class_a.id)] for c in enqueued
    )

    # Повтор підтвердження — той самий результат, без нового запису журналу.
    again = await client.post(
        f"/deletion-requests/{req['id']}/confirm", headers=auth_header(w.admin)
    )
    assert again.status_code == 200 and again.json() == done
    assert await db_session.scalar(select(func.count()).select_from(DataDeletionLog)) == 1
    # Батьки бачать статус свого запиту.
    mine = await client.get("/deletion-requests", headers=auth_header(w.parent_a))
    assert [(x["id"], x["status"]) for x in mine.json()] == [(req["id"], "confirmed")]
    # Повтор створення тим самим id після видалення — той самий запит.
    repeat = await create(client, w.parent_a, w.student_a, req["id"])
    assert repeat.status_code == 200 and repeat.json()["status"] == "confirmed"
    # Видалений учень більше не автентифікується.
    me = await client.get("/auth/me", headers=auth_header(w.student_a))
    assert me.status_code == 401


async def test_create_is_idempotent_and_one_pending_per_student(client, w) -> None:
    request_id = uuid.uuid4()
    first = await create(client, w.admin, w.student_a, request_id)
    assert first.status_code == 201 and first.json()["requested_by_role"] == "admin"
    repeat = await create(client, w.admin, w.student_a, request_id)
    assert repeat.status_code == 200 and repeat.json() == first.json()
    changed = await create(client, w.admin, w.student_a, request_id, reason="other")
    assert changed.status_code == 409 and changed.json()["error"]["code"] == "ID_CONFLICT"
    other = await create(client, w.parent_a, w.student_a)
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "DELETION_REQUEST_EXISTS"
    # Інший учень — свій запит.
    assert (await create(client, w.admin, w.student_b)).status_code == 201


async def test_reject_keeps_data_and_allows_new_request(client, db_session, w) -> None:
    req = (await create(client, w.parent_a, w.student_a)).json()
    url = f"/deletion-requests/{req['id']}"
    r = await client.post(f"{url}/reject", headers=auth_header(w.admin))
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert (await client.post(f"{url}/reject", headers=auth_header(w.admin))).status_code == 200
    r = await client.post(f"{url}/confirm", headers=auth_header(w.admin))
    assert r.status_code == 409 and r.json()["error"]["code"] == "DELETION_REQUEST_DECIDED"
    assert await db_session.get(User, w.student_a.id) is not None
    assert (await create(client, w.parent_a, w.student_a)).status_code == 201


async def test_cannot_reject_confirmed(client, w) -> None:
    req = (await create(client, w.admin, w.student_b)).json()
    url = f"/deletion-requests/{req['id']}"
    assert (await client.post(f"{url}/confirm", headers=auth_header(w.admin))).status_code == 200
    r = await client.post(f"{url}/reject", headers=auth_header(w.admin))
    assert r.status_code == 409


async def test_roles(client, factory, w) -> None:
    other_parent = await factory.parent_of(w.student_b)
    for user in (other_parent, w.parent_free, w.other_admin):
        assert (await create(client, user, w.student_a)).status_code == 403
    for user in (w.teacher_a, w.student_a, w.student_b):
        assert (await create(client, user, w.student_a)).status_code == 403
    assert (await create(client, w.admin, w.teacher_a)).status_code == 404
    unknown = await client.post(
        f"/students/{uuid.uuid4()}/deletion-requests",
        json={"id": str(uuid.uuid4())},
        headers=auth_header(w.admin),
    )
    assert unknown.status_code == 404

    req = (await create(client, w.parent_a, w.student_a)).json()
    for action in ("confirm", "reject"):
        url = f"/deletion-requests/{req['id']}/{action}"
        for user in (w.parent_a, w.teacher_a, w.student_a):
            assert (await client.post(url, headers=auth_header(user))).status_code == 403
        assert (await client.post(url, headers=auth_header(w.other_admin))).status_code == 403
        assert (await client.post(url)).status_code == 401
    missing = f"/deletion-requests/{uuid.uuid4()}/confirm"
    assert (await client.post(missing, headers=auth_header(w.admin))).status_code == 404

    # Список: чужа школа й інші батьки запиту не бачать; вчитель і учень — 403.
    for user in (w.other_admin, other_parent, w.parent_free):
        r = await client.get("/deletion-requests", headers=auth_header(user))
        assert r.status_code == 200 and r.json() == []
    for user in (w.teacher_a, w.student_a):
        r = await client.get("/deletion-requests", headers=auth_header(user))
        assert r.status_code == 403


async def test_reason_is_enum_only(client, w) -> None:
    r = await create(client, w.parent_a, w.student_a, reason="Іван переїхав до Львова")
    assert r.status_code == 422
    assert (await create(client, w.parent_a, w.student_a, reason=None)).status_code == 201
