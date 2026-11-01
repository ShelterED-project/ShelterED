"""Тести таблиці ролей: кожне правило доступу з CLAUDE.md має перевірку."""

import datetime as dt

import pytest
from conftest import PASSWORD, auth_header
from fastapi import APIRouter, FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_auth import get_code, pkce_pair

from app.api.deps import AccessibleClass, AccessibleStudent, StaffClass
from app.core.security import hash_token
from app.models.auth import ParentLinkCode
from app.models.school import ClassMembership, ParentChild, User

pytestmark = pytest.mark.anyio

# Мінімальні ендпоінти лише для тестів: доменні ще не існують, а залежності вже є.
probe_router = APIRouter(prefix="/test")


@probe_router.get("/classes/{class_id}")
async def _class(klass: AccessibleClass) -> dict:
    return {"id": str(klass.id)}


@probe_router.get("/staff-classes/{class_id}")
async def _staff_class(klass: StaffClass) -> dict:
    return {"id": str(klass.id)}


@probe_router.get("/students/{student_id}")
async def _student(student: AccessibleStudent) -> dict:
    return {"id": str(student.id)}


@pytest.fixture(autouse=True)
def mount_test_router(app: FastAPI) -> None:
    app.include_router(probe_router)


async def status_of(client: AsyncClient, method: str, url: str, user: User | None, **kw) -> int:
    headers = auth_header(user) if user else {}
    return (await client.request(method, url, headers=headers, **kw)).status_code


# ---------- вчитель бачить лише свої класи ----------


async def test_teacher_sees_only_own_class(client: AsyncClient, world) -> None:
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_a.id}", world.teacher_a) == 200
    )
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_b.id}", world.teacher_a) == 403
    )
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_a.id}", world.teacher_b) == 403
    )
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_c.id}", world.teacher_a) == 403
    )


async def test_teacher_sees_only_own_students(client: AsyncClient, world) -> None:
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_a.id}", world.teacher_a)
        == 200
    )
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_b.id}", world.teacher_a)
        == 403
    )
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_a.id}", world.teacher_b)
        == 403
    )


async def test_teacher_in_two_classes_sees_both(client: AsyncClient, world, factory) -> None:
    factory.session.add(
        ClassMembership(
            class_id=world.class_b.id, user_id=world.teacher_a.id, member_role="teacher"
        )
    )
    await factory.session.flush()
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_b.id}", world.teacher_a) == 200
    )
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_b.id}", world.teacher_a)
        == 200
    )


# ---------- учень бачить лише себе ----------


async def test_student_sees_only_self(client: AsyncClient, world) -> None:
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_a.id}", world.student_a)
        == 200
    )
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_b.id}", world.student_a)
        == 403
    )
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_a.id}", world.student_a) == 200
    )
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_b.id}", world.student_a) == 403
    )
    assert (
        await status_of(client, "GET", f"/test/staff-classes/{world.class_a.id}", world.student_a)
        == 403
    )


# ---------- батьки бачать лише свою дитину ----------


async def test_parent_sees_only_own_child(client: AsyncClient, world) -> None:
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_a.id}", world.parent_a)
        == 200
    )
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_b.id}", world.parent_a)
        == 403
    )
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_a.id}", world.parent_free)
        == 403
    )
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_a.id}", world.parent_a) == 403
    )


# ---------- адмін обмежений своєю школою ----------


async def test_admin_limited_to_own_school(client: AsyncClient, world) -> None:
    for klass in (world.class_a, world.class_b):
        assert await status_of(client, "GET", f"/test/classes/{klass.id}", world.admin) == 200
        assert await status_of(client, "GET", f"/test/staff-classes/{klass.id}", world.admin) == 200
    assert await status_of(client, "GET", f"/test/classes/{world.class_c.id}", world.admin) == 403
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_a.id}", world.admin) == 200
    )
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_c.id}", world.admin) == 403
    )
    assert (
        await status_of(client, "GET", f"/test/classes/{world.class_a.id}", world.other_admin)
        == 403
    )


async def test_unauthenticated_and_missing_resources(client: AsyncClient, world) -> None:
    assert await status_of(client, "GET", f"/test/classes/{world.class_a.id}", None) == 401
    missing = "00000000-0000-0000-0000-000000000009"
    assert await status_of(client, "GET", f"/test/classes/{missing}", world.admin) == 404
    assert await status_of(client, "GET", f"/test/students/{missing}", world.admin) == 404
    # Вчитель — не «учень»: /test/students/{teacher_id} теж 404.
    assert (
        await status_of(client, "GET", f"/test/students/{world.teacher_a.id}", world.admin) == 404
    )


# ---------- адміністрація створює акаунти ----------


def new_user(role: str = "teacher", email: str = "new.teacher@example.com") -> dict:
    return {
        "email": email,
        "display_name": "Наталія",
        "last_name": "Шевченко",
        "role": role,
        "password": "initial-password",
    }


async def test_admin_creates_teacher_in_own_school(client: AsyncClient, world) -> None:
    resp = await client.post("/admin/users", json=new_user(), headers=auth_header(world.admin))
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "teacher"
    assert body["school_id"] == str(world.school.id)
    assert "password" not in body and "password_hash" not in body
    # Новий вчитель входить через PKCE зі своїм початковим паролем.
    _, challenge = pkce_pair()
    ok = await get_code(client, "new.teacher@example.com", challenge, "initial-password")
    assert ok.status_code == 200


async def test_admin_creates_parent_and_admin(client: AsyncClient, world) -> None:
    parent = await client.post(
        "/admin/users", json=new_user("parent", "p@example.com"), headers=auth_header(world.admin)
    )
    assert parent.status_code == 201
    assert parent.json()["school_id"] is None
    admin = await client.post(
        "/admin/users", json=new_user("admin", "a2@example.com"), headers=auth_header(world.admin)
    )
    assert admin.status_code == 201
    assert admin.json()["school_id"] == str(world.school.id)


async def test_admin_cannot_create_student_or_duplicate(client: AsyncClient, world) -> None:
    headers = auth_header(world.admin)
    assert (
        await client.post("/admin/users", json=new_user("student"), headers=headers)
    ).status_code == 422
    first = await client.post("/admin/users", json=new_user(), headers=headers)
    assert first.status_code == 201
    dup = await client.post(
        "/admin/users", json=new_user(email="NEW.teacher@example.com"), headers=headers
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "EMAIL_TAKEN"


async def test_non_admin_cannot_create_users(client: AsyncClient, world) -> None:
    for user in (world.teacher_a, world.parent_a, world.student_a):
        resp = await client.post("/admin/users", json=new_user(), headers=auth_header(user))
        assert resp.status_code == 403, user.role
    assert (await client.post("/admin/users", json=new_user())).status_code == 401


async def test_password_is_hashed(client: AsyncClient, world, db_session: AsyncSession) -> None:
    await client.post("/admin/users", json=new_user(), headers=auth_header(world.admin))
    user = await db_session.scalar(select(User).where(User.email == "new.teacher@example.com"))
    assert user.password_hash.startswith("$argon2")
    assert PASSWORD not in user.password_hash


# ---------- прив'язка батьків ----------


async def make_code(client: AsyncClient, creator: User, student: User) -> str:
    resp = await client.post(
        f"/students/{student.id}/parent-link-codes", headers=auth_header(creator)
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["code"]


async def test_parent_link_flow(client: AsyncClient, world, db_session: AsyncSession) -> None:
    code = await make_code(client, world.teacher_a, world.student_a)
    assert len(code) == 8
    # Код зберігається лише хешем.
    stored = (await db_session.scalars(select(ParentLinkCode.code_hash))).all()
    assert code not in stored and hash_token(code) in stored

    headers = auth_header(world.parent_free)
    # Батьки бачать дитину лише після прив'язки.
    url = f"/test/students/{world.student_a.id}"
    assert await status_of(client, "GET", url, world.parent_free) == 403
    resp = await client.post("/parent/link", json={"code": code.lower()}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["child_id"] == str(world.student_a.id)
    assert await status_of(client, "GET", url, world.parent_free) == 200
    # Своя дитина — не чужа.
    assert (
        await status_of(client, "GET", f"/test/students/{world.student_b.id}", world.parent_free)
        == 403
    )


async def test_parent_link_idempotent_and_single_use(client: AsyncClient, world, factory) -> None:
    code = await make_code(client, world.teacher_a, world.student_a)
    headers = auth_header(world.parent_free)
    assert (
        await client.post("/parent/link", json={"code": code}, headers=headers)
    ).status_code == 200
    assert (
        await client.post("/parent/link", json={"code": code}, headers=headers)
    ).status_code == 200
    links = (
        await factory.session.scalars(
            select(ParentChild).where(ParentChild.parent_id == world.parent_free.id)
        )
    ).all()
    assert len(links) == 1
    # Інші батьки той самий код використати не можуть.
    other = await factory.adult("parent", None)
    resp = await client.post("/parent/link", json={"code": code}, headers=auth_header(other))
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_LINK_CODE"


async def test_parent_link_already_linked_still_ok(client: AsyncClient, world) -> None:
    code = await make_code(client, world.admin, world.student_a)
    resp = await client.post(
        "/parent/link", json={"code": code}, headers=auth_header(world.parent_a)
    )
    assert resp.status_code == 200


async def test_parent_link_expired_or_unknown(
    client: AsyncClient, world, db_session: AsyncSession
) -> None:
    code = await make_code(client, world.teacher_a, world.student_a)
    row = await db_session.scalar(select(ParentLinkCode))
    assert row.expires_at - dt.datetime.now(dt.UTC) > dt.timedelta(days=6)
    row.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    headers = auth_header(world.parent_free)
    assert (
        await client.post("/parent/link", json={"code": code}, headers=headers)
    ).status_code == 400
    assert (
        await client.post("/parent/link", json={"code": "ZZZZZZZZ"}, headers=headers)
    ).status_code == 400


async def test_parent_link_code_creation_scope(client: AsyncClient, world) -> None:
    url = f"/students/{world.student_a.id}/parent-link-codes"
    assert await status_of(client, "POST", url, world.teacher_a) == 201
    assert await status_of(client, "POST", url, world.admin) == 201
    assert await status_of(client, "POST", url, world.teacher_b) == 403
    assert await status_of(client, "POST", url, world.other_admin) == 403
    assert await status_of(client, "POST", url, world.student_a) == 403
    assert await status_of(client, "POST", url, world.parent_a) == 403
    assert await status_of(client, "POST", url, None) == 401


async def test_only_parents_can_link(client: AsyncClient, world) -> None:
    code = await make_code(client, world.teacher_a, world.student_a)
    for user in (world.teacher_a, world.student_b, world.admin):
        resp = await client.post("/parent/link", json={"code": code}, headers=auth_header(user))
        assert resp.status_code == 403, user.role
