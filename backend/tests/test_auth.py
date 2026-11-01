import base64
import datetime as dt
import hashlib
import secrets

import jwt
import pytest
from conftest import PASSWORD, PIN, auth_header
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_token
from app.models.auth import AuthCode, RefreshToken

pytestmark = pytest.mark.anyio

CLIENT_ID = "sheltered-pwa"


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


async def get_code(client: AsyncClient, email: str, challenge: str, password: str = PASSWORD):
    return await client.post(
        "/auth/authorize",
        json={
            "email": email,
            "password": password,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "client_id": CLIENT_ID,
        },
    )


async def login(client: AsyncClient, email: str) -> dict:
    verifier, challenge = pkce_pair()
    code = (await get_code(client, email, challenge)).json()["code"]
    resp = await client.post(
        "/auth/token",
        json={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def refresh(client: AsyncClient, token: str):
    return await client.post(
        "/auth/token", json={"grant_type": "refresh_token", "refresh_token": token}
    )


# ---------- PKCE ----------


async def test_pkce_happy_path(client: AsyncClient, world) -> None:
    tokens = await login(client, world.teacher_a.email)
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] == 15 * 60
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json() == {
        "id": str(world.teacher_a.id),
        "role": "teacher",
        "display_name": "Олена",
        "last_name": None,
        "school_id": str(world.school.id),
    }


async def test_access_token_claims(client: AsyncClient, world) -> None:
    tokens = await login(client, world.teacher_a.email)
    claims = jwt.decode(
        tokens["access_token"], get_settings().jwt_secret.get_secret_value(), ["HS256"]
    )
    assert claims["sub"] == str(world.teacher_a.id)
    assert claims["role"] == "teacher"
    assert claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == 15 * 60
    assert claims["jti"]


async def test_token_endpoint_accepts_form(client: AsyncClient, world) -> None:
    verifier, challenge = pkce_pair()
    code = (await get_code(client, world.admin.email, challenge)).json()["code"]
    resp = await client.post(
        "/auth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
        },
    )
    assert resp.status_code == 200
    assert "refresh_token" in resp.json()


async def test_wrong_verifier_rejected_and_burns_code(client: AsyncClient, world) -> None:
    verifier, challenge = pkce_pair()
    code = (await get_code(client, world.teacher_a.email, challenge)).json()["code"]
    body = {"grant_type": "authorization_code", "code": code, "client_id": CLIENT_ID}
    bad = await client.post("/auth/token", json={**body, "code_verifier": "x" * 50})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_GRANT"
    good = await client.post("/auth/token", json={**body, "code_verifier": verifier})
    assert good.status_code == 400


async def test_code_is_single_use(client: AsyncClient, world) -> None:
    verifier, challenge = pkce_pair()
    code = (await get_code(client, world.teacher_a.email, challenge)).json()["code"]
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": verifier,
        "client_id": CLIENT_ID,
    }
    assert (await client.post("/auth/token", json=body)).status_code == 200
    again = await client.post("/auth/token", json=body)
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "INVALID_GRANT"


async def test_expired_code_rejected(client: AsyncClient, world, db_session: AsyncSession) -> None:
    verifier, challenge = pkce_pair()
    code = (await get_code(client, world.teacher_a.email, challenge)).json()["code"]
    row = await db_session.scalar(select(AuthCode).where(AuthCode.code_hash == hash_token(code)))
    row.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    resp = await client.post(
        "/auth/token",
        json={
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "client_id": CLIENT_ID,
        },
    )
    assert resp.status_code == 400


async def test_code_is_stored_hashed(client: AsyncClient, world, db_session: AsyncSession) -> None:
    _, challenge = pkce_pair()
    code = (await get_code(client, world.teacher_a.email, challenge)).json()["code"]
    stored = (await db_session.scalars(select(AuthCode.code_hash))).all()
    assert code not in stored
    assert hash_token(code) in stored


async def test_authorize_bad_credentials(client: AsyncClient, world) -> None:
    _, challenge = pkce_pair()
    wrong = await get_code(client, world.teacher_a.email, challenge, password="nope-nope-nope")
    unknown = await get_code(client, "nobody@example.com", challenge)
    for resp in (wrong, unknown):
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_authorize_many_wrong_passwords_do_not_lock_account(
    client: AsyncClient, world
) -> None:
    _, challenge = pkce_pair()
    for _ in range(7):
        assert (
            await get_code(client, world.teacher_a.email, challenge, "bad-bad-bad")
        ).status_code == 401
    assert (await get_code(client, world.teacher_a.email, challenge)).status_code == 200


async def test_authorize_rejects_plain_method_and_unknown_client(
    client: AsyncClient, world
) -> None:
    _, challenge = pkce_pair()
    base = {
        "email": world.teacher_a.email,
        "password": PASSWORD,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "client_id": CLIENT_ID,
    }
    plain = await client.post("/auth/authorize", json={**base, "code_challenge_method": "plain"})
    assert plain.status_code == 422
    unknown = await client.post("/auth/authorize", json={**base, "client_id": "evil"})
    assert unknown.status_code == 400


async def test_unsupported_grant_type(client: AsyncClient) -> None:
    resp = await client.post("/auth/token", json={"grant_type": "password"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REQUEST"


async def test_inactive_user_cannot_login_or_use_token(client: AsyncClient, world) -> None:
    tokens = await login(client, world.teacher_a.email)
    world.teacher_a.is_active = False
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 401
    _, challenge = pkce_pair()
    assert (await get_code(client, world.teacher_a.email, challenge)).status_code == 401
    assert (await refresh(client, tokens["refresh_token"])).status_code == 400


# ---------- refresh-токени ----------


async def test_refresh_rotation(client: AsyncClient, world, db_session: AsyncSession) -> None:
    first = await login(client, world.teacher_a.email)
    resp = await refresh(client, first["refresh_token"])
    assert resp.status_code == 200
    second = resp.json()
    assert second["refresh_token"] != first["refresh_token"]
    rows = (await db_session.scalars(select(RefreshToken))).all()
    assert len(rows) == 2
    assert len({r.family_id for r in rows}) == 1
    assert first["refresh_token"] not in {r.token_hash for r in rows}
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert me.status_code == 200


async def test_reused_refresh_token_revokes_family(client: AsyncClient, world) -> None:
    first = await login(client, world.teacher_a.email)
    second = (await refresh(client, first["refresh_token"])).json()
    # Зловмисник (або старий клієнт) пред'являє вже ротований токен.
    reuse = await refresh(client, first["refresh_token"])
    assert reuse.status_code == 400
    assert reuse.json()["error"]["code"] == "INVALID_GRANT"
    # Законний наступний токен теж відкликано.
    assert (await refresh(client, second["refresh_token"])).status_code == 400


async def test_revocation_does_not_touch_other_families(client: AsyncClient, world) -> None:
    a = await login(client, world.teacher_a.email)
    b = await login(client, world.teacher_a.email)
    await refresh(client, a["refresh_token"])
    await refresh(client, a["refresh_token"])  # reuse -> родина a відкликана
    assert (await refresh(client, b["refresh_token"])).status_code == 200


async def test_expired_refresh_token(client: AsyncClient, world, db_session: AsyncSession) -> None:
    tokens = await login(client, world.teacher_a.email)
    row = await db_session.scalar(select(RefreshToken))
    row.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    assert (await refresh(client, tokens["refresh_token"])).status_code == 400


async def test_unknown_refresh_token(client: AsyncClient) -> None:
    assert (await refresh(client, "garbage")).status_code == 400


async def test_logout_revokes_family(client: AsyncClient, world) -> None:
    first = await login(client, world.teacher_a.email)
    second = (await refresh(client, first["refresh_token"])).json()
    out = await client.post("/auth/logout", json={"refresh_token": second["refresh_token"]})
    assert out.status_code == 204
    assert (await refresh(client, second["refresh_token"])).status_code == 400
    # Повторний і невідомий токен — теж 204.
    again = await client.post("/auth/logout", json={"refresh_token": second["refresh_token"]})
    assert again.status_code == 204
    unknown = await client.post("/auth/logout", json={"refresh_token": "garbage"})
    assert unknown.status_code == 204


# ---------- access JWT ----------


def forged(world, **overrides) -> str:
    now = dt.datetime.now(dt.UTC)
    claims = {
        "sub": str(world.teacher_a.id),
        "role": "teacher",
        "iat": now,
        "exp": now + dt.timedelta(minutes=5),
        "jti": "x",
        "type": "access",
        **overrides,
    }
    return jwt.encode(claims, get_settings().jwt_secret.get_secret_value(), algorithm="HS256")


async def test_missing_token_is_401(client: AsyncClient) -> None:
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


async def test_bad_jwts_are_401(client: AsyncClient, world) -> None:
    good = forged(world)
    now = dt.datetime.now(dt.UTC)
    cases = {
        "tampered": good[:-3] + ("AAA" if not good.endswith("AAA") else "BBB"),
        "expired": forged(
            world, iat=now - dt.timedelta(hours=1), exp=now - dt.timedelta(minutes=1)
        ),
        "wrong secret": jwt.encode(
            {"sub": str(world.teacher_a.id), "role": "teacher", "type": "access"},
            "another-secret-another-secret-123456",
            algorithm="HS256",
        ),
        "wrong type": forged(world, type="refresh"),
        "garbage": "not-a-jwt",
        "unknown user": forged(world, sub="00000000-0000-0000-0000-000000000001"),
        "non-uuid sub": forged(world, sub="abc"),
    }
    for name, token in cases.items():
        resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401, name
        assert resp.json()["error"]["code"] == "UNAUTHORIZED", name


async def test_alg_none_rejected(client: AsyncClient, world) -> None:
    token = jwt.encode(
        {"sub": str(world.admin.id), "role": "admin", "type": "access"}, None, algorithm="none"
    )
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ---------- вхід учня ----------


def join_body(klass, name="Дарина", last="Мельник", pin=PIN) -> dict:
    return {"join_code": klass.join_code, "display_name": name, "last_name": last, "pin": pin}


async def me_id(client: AsyncClient, tokens: dict) -> str:
    resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    return resp.json()["id"]


async def test_student_first_join_creates_student(client: AsyncClient, world) -> None:
    resp = await client.post("/auth/student/join", json=join_body(world.class_a))
    assert resp.status_code == 200
    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {resp.json()['access_token']}"}
    )
    assert me.json()["role"] == "student"
    assert me.json()["last_name"] == "Мельник"
    assert me.json()["school_id"] == str(world.school.id)


async def test_student_rejoin_with_right_pin(client: AsyncClient, world) -> None:
    first = (await client.post("/auth/student/join", json=join_body(world.class_a))).json()
    # Регістр і пробіли в імені не мають значення.
    body = join_body(world.class_a, " дАРИНА ", "МЕЛЬНИК ")
    second = await client.post("/auth/student/join", json=body)
    assert second.status_code == 200
    assert await me_id(client, second.json()) == await me_id(client, first)


async def test_student_wrong_pin_is_401_without_lockout(client: AsyncClient, world) -> None:
    await client.post("/auth/student/join", json=join_body(world.class_a))
    for _ in range(8):
        bad = await client.post("/auth/student/join", json=join_body(world.class_a, pin="9999"))
        assert bad.status_code == 401
        assert bad.json()["error"]["code"] == "INVALID_CREDENTIALS"
    ok = await client.post("/auth/student/join", json=join_body(world.class_a))
    assert ok.status_code == 200


async def test_student_pin_validation(client: AsyncClient, world) -> None:
    for pin in ("123", "1234567", "abcd", "12 34"):
        resp = await client.post("/auth/student/join", json=join_body(world.class_a, pin=pin))
        assert resp.status_code == 422, pin
    for pin in ("1234", "12345", "123456"):
        name = f"Н{pin}"
        resp = await client.post("/auth/student/join", json=join_body(world.class_a, name, pin=pin))
        assert resp.status_code == 200, pin


async def test_student_requires_last_name(client: AsyncClient, world) -> None:
    body = join_body(world.class_a)
    del body["last_name"]
    assert (await client.post("/auth/student/join", json=body)).status_code == 422


async def test_student_invalid_or_expired_join_code(client: AsyncClient, world, factory) -> None:
    bad = await client.post(
        "/auth/student/join", json={**join_body(world.class_a), "join_code": "NOPE"}
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_JOIN_CODE"
    expired = await factory.klass(
        world.school, "8-А", expires=dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
    )
    resp = await client.post("/auth/student/join", json=join_body(expired))
    assert resp.status_code == 400


async def test_student_credentials_do_not_work_in_another_class(client: AsyncClient, world) -> None:
    # Існуючий учень класу А.
    body_a = join_body(world.class_a, "Іван", "Петренко")
    assert (await client.post("/auth/student/join", json=body_a)).status_code == 200
    # Той самий код класу Б з іншим PIN дає НОВОГО учня класу Б, а не вхід у А.
    other_pin = {**join_body(world.class_b, "Іван", "Петренко"), "pin": "6543"}
    resp = await client.post("/auth/student/join", json=other_pin)
    assert resp.status_code == 200
    assert await me_id(client, resp.json()) != str(world.student_a.id)
    # Імʼя учня класу А з кодом класу Б і PIN-ом учня А не відкриває акаунт А.
    resp = await client.post(
        "/auth/student/join", json=join_body(world.class_b, "Іван", "Петренко")
    )
    assert resp.status_code == 401


async def test_inactive_student_cannot_join(client: AsyncClient, world) -> None:
    world.student_a.is_active = False
    resp = await client.post(
        "/auth/student/join", json=join_body(world.class_a, "Іван", "Петренко")
    )
    assert resp.status_code == 401


# ---------- скидання PIN ----------


async def test_pin_reset_by_class_teacher(client: AsyncClient, world) -> None:
    url = f"/classes/{world.class_a.id}/students/{world.student_a.id}/pin-reset"
    resp = await client.post(url, headers=auth_header(world.teacher_a))
    assert resp.status_code == 204
    assert world.student_a.pin_hash is None
    # Старий PIN більше не потрібен: перший вхід задає новий.
    body = join_body(world.class_a, "Іван", "Петренко", pin="5555")
    assert (await client.post("/auth/student/join", json=body)).status_code == 200
    assert (await client.post("/auth/student/join", json=body)).status_code == 200
    old = await client.post("/auth/student/join", json=join_body(world.class_a, "Іван", "Петренко"))
    assert old.status_code == 401


async def test_pin_reset_by_school_admin(client: AsyncClient, world) -> None:
    url = f"/classes/{world.class_a.id}/students/{world.student_a.id}/pin-reset"
    assert (await client.post(url, headers=auth_header(world.admin))).status_code == 204


async def test_pin_reset_forbidden_for_others(client: AsyncClient, world) -> None:
    url = f"/classes/{world.class_a.id}/students/{world.student_a.id}/pin-reset"
    for user in (world.teacher_b, world.other_admin, world.student_a, world.parent_a):
        resp = await client.post(url, headers=auth_header(user))
        assert resp.status_code == 403, user.role
    assert (await client.post(url)).status_code == 401
    assert world.student_a.pin_hash is not None


async def test_pin_reset_student_must_be_in_class(client: AsyncClient, world) -> None:
    url = f"/classes/{world.class_a.id}/students/{world.student_b.id}/pin-reset"
    resp = await client.post(url, headers=auth_header(world.teacher_a))
    assert resp.status_code == 404
    assert world.student_b.pin_hash is not None
