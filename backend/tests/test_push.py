"""Web Push (B8): ключ VAPID, підписки, одержувачі, доставка, повтори й дедуплікація."""

import base64
import datetime as dt
import json
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from celery.exceptions import Retry
from conftest import auth_header
from py_vapid import Vapid
from pydantic import SecretStr
from sqlalchemy import func, select

from app.cli import gen_vapid, main
from app.core.config import Settings, get_settings
from app.models.push import PushSubscription
from app.services import push as service
from app.services.push import SendResult
from app.workers import push as worker

pytestmark = pytest.mark.anyio

P256DH = "BBJFmkZC5F0jfP24cPgJUCB45eRrVp1-DWnDyMYoxVXhkPqlJDq98HcVnf0xelE_ZbzOfuy3yave_sTvQf3qH8M"
AUTH = "dGKjugWk0qMwRUW6A0jvNQ"


def body(endpoint: str | None = None, sub_id: uuid.UUID | None = None) -> dict:
    return {
        "id": str(sub_id or uuid.uuid4()),
        "endpoint": endpoint or f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}",
        "keys": {"p256dh": P256DH, "auth": AUTH},
    }


def vapid_settings(**overrides) -> Settings:
    public, private = gen_vapid()
    values = {
        "vapid_public_key": public,
        "vapid_private_key": SecretStr(private),
        "vapid_subject": "mailto:admin@example.com",
        **overrides,
    }
    return get_settings().model_copy(update=values)


@pytest.fixture
def vapid(app, monkeypatch) -> Settings:
    settings = vapid_settings()
    app.dependency_overrides[get_settings] = lambda: settings
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    return settings


# ---------- VAPID ----------


def test_gen_vapid_pair_is_valid(capsys) -> None:
    assert main(["gen-vapid"]) == 0
    out = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    key = Vapid.from_string(out["VAPID_PRIVATE_KEY"])
    raw = base64.urlsafe_b64decode(out["VAPID_PUBLIC_KEY"] + "==")
    assert len(raw) == 65 and raw[0] == 4
    from cryptography.hazmat.primitives import serialization

    assert (
        key.public_key.public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
        )
        == raw
    )


async def test_vapid_key_requires_auth_and_config(client, app, world) -> None:
    assert (await client.get("/push/vapid-key")).status_code == 401
    response = await client.get("/push/vapid-key", headers=auth_header(world.parent_a))
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PUSH_NOT_CONFIGURED"
    settings = vapid_settings()
    app.dependency_overrides[get_settings] = lambda: settings
    response = await client.get("/push/vapid-key", headers=auth_header(world.parent_a))
    assert response.status_code == 200
    assert response.json() == {"public_key": settings.vapid_public_key}


# ---------- підписки ----------


@pytest.mark.parametrize("role", ["student_a", "teacher_a", "parent_a", "admin"])
async def test_any_role_subscribes_idempotently(client, db_session, world, role) -> None:
    user = getattr(world, role)
    data = body()
    first = await client.post("/push/subscriptions", json=data, headers=auth_header(user))
    assert first.status_code == 201, first.text
    assert first.json()["id"] == data["id"]
    again = await client.post("/push/subscriptions", json=data, headers=auth_header(user))
    assert again.status_code == 200
    assert again.json()["id"] == data["id"]
    count = await db_session.scalar(
        select(func.count())
        .select_from(PushSubscription)
        .where(PushSubscription.user_id == user.id)
    )
    assert count == 1


async def test_same_endpoint_new_id_returns_existing_and_rebinds(client, db_session, world) -> None:
    data = body()
    await client.post("/push/subscriptions", json=data, headers=auth_header(world.student_a))
    # На тому ж пристрої увійшли батьки: підписка переходить до них, id лишається.
    other = {**body(data["endpoint"]), "keys": {"p256dh": P256DH, "auth": "AAAAAAAAAAAAAAAAAAAAAA"}}
    response = await client.post(
        "/push/subscriptions", json=other, headers=auth_header(world.parent_a)
    )
    assert response.status_code == 200
    assert response.json()["id"] == data["id"]
    sub = await db_session.get(PushSubscription, uuid.UUID(data["id"]), populate_existing=True)
    assert sub.user_id == world.parent_a.id and sub.auth == "AAAAAAAAAAAAAAAAAAAAAA"


async def test_same_id_new_endpoint_updates_own_but_conflicts_for_other(
    client, db_session, world
) -> None:
    data = body()
    await client.post("/push/subscriptions", json=data, headers=auth_header(world.student_a))
    renewed = body(sub_id=uuid.UUID(data["id"]))
    response = await client.post(
        "/push/subscriptions", json=renewed, headers=auth_header(world.student_a)
    )
    assert response.status_code == 200
    assert response.json()["endpoint"] == renewed["endpoint"]
    stolen = body(sub_id=uuid.UUID(data["id"]))
    response = await client.post(
        "/push/subscriptions", json=stolen, headers=auth_header(world.student_b)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ID_CONFLICT"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fcm.googleapis.com/fcm/send/x",
        "https://127.0.0.1/push",
        "https://localhost/push",
        "https://[::1]/push",
        "https://intranet/push",
        "https://user:pass@fcm.googleapis.com/x",
        "https://evil.example.com/fcm/send/x",
        "https://fcm.googleapis.com.evil.com/x",
        "https://notfcm.googleapis.com/x",
        "https://storage.googleapis.com/x",
    ],
)
async def test_subscription_rejects_unsafe_endpoint(client, world, endpoint) -> None:
    response = await client.post(
        "/push/subscriptions", json=body(endpoint), headers=auth_header(world.student_a)
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://fcm.googleapis.com/fcm/send/abc",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://web.push.apple.com/QGm9abc",
        "https://wns2-par02p.notify.windows.com/w/?token=abc",
        "https://FCM.googleapis.com/fcm/send/abc",
    ],
)
async def test_subscription_accepts_known_push_services(client, world, endpoint) -> None:
    response = await client.post(
        "/push/subscriptions", json=body(endpoint), headers=auth_header(world.student_a)
    )
    assert response.status_code == 201, response.text


async def test_allowed_push_hosts_come_from_settings(client, world, monkeypatch) -> None:
    settings = get_settings().model_copy(
        update={"push_allowed_host_suffixes": ["push.example.org"]}
    )
    monkeypatch.setattr("app.schemas.push.get_settings", lambda: settings)
    headers = auth_header(world.student_a)
    ok = await client.post(
        "/push/subscriptions", json=body("https://eu.push.example.org/x"), headers=headers
    )
    assert ok.status_code == 201, ok.text
    denied = await client.post("/push/subscriptions", json=body(), headers=headers)
    assert denied.status_code == 422


async def test_subscription_rejects_bad_keys(client, world) -> None:
    data = body()
    data["keys"] = {"p256dh": "BNcRdreALRFX", "auth": AUTH}
    headers = auth_header(world.student_a)
    assert (await client.post("/push/subscriptions", json=data, headers=headers)).status_code == 422
    data["keys"] = {"p256dh": P256DH, "auth": "tBHI"}
    assert (await client.post("/push/subscriptions", json=data, headers=headers)).status_code == 422


@pytest.mark.parametrize("padded", [False, True])
async def test_subscription_accepts_padded_and_unpadded_keys(client, world, padded) -> None:
    """Ключі з `=` у кінці (стандартний base64url) і без нього: p256dh 65 байт, auth 16."""
    raw_point = base64.urlsafe_b64decode(P256DH + "=")
    raw_auth = base64.urlsafe_b64decode(AUTH + "==")
    assert (len(raw_point), len(raw_auth)) == (65, 16)
    p256dh = base64.urlsafe_b64encode(raw_point).decode()
    auth = base64.urlsafe_b64encode(raw_auth).decode()
    if not padded:
        p256dh, auth = p256dh.rstrip("="), auth.rstrip("=")
    assert p256dh.endswith("=") == padded and auth.endswith("=") == padded
    data = body()
    data["keys"] = {"p256dh": p256dh, "auth": auth}
    response = await client.post(
        "/push/subscriptions", json=data, headers=auth_header(world.student_a)
    )
    assert response.status_code == 201


async def test_subscription_rejects_p256dh_off_curve(client, world) -> None:
    """65 байт із префіксом 0x04, але не точка P-256 — 422 (а не вічні збої шифрування)."""
    raw = bytearray(base64.urlsafe_b64decode(P256DH + "="))
    raw[-1] ^= 1
    data = body()
    data["keys"] = {
        "p256dh": base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("="),
        "auth": AUTH,
    }
    response = await client.post(
        "/push/subscriptions", json=data, headers=auth_header(world.student_a)
    )
    assert response.status_code == 422


async def _subscribe_with_times(client, db_session, user, count: int) -> list[uuid.UUID]:
    """`count` підписок; created_at — година тому + 1, 2, ... с (у тесті все в одній транзакції
    з тим самим now(), тож нова підписка завжди новіша). updated_at найстарішої — найновіший,
    ніби її щойно чіпала спроба доставки."""
    ids = []
    for i in range(count):
        data = body()
        ids.append(uuid.UUID(data["id"]))
        await client.post("/push/subscriptions", json=data, headers=auth_header(user))
        sub = await db_session.get(PushSubscription, ids[-1])
        base = sub.created_at - dt.timedelta(hours=1)
        sub.created_at = base + dt.timedelta(seconds=i + 1)
        sub.updated_at = base + dt.timedelta(seconds=59 - i)
        await db_session.flush()
    return ids


async def _left(db_session, user) -> set[uuid.UUID]:
    return set(
        await db_session.scalars(
            select(PushSubscription.id).where(PushSubscription.user_id == user.id)
        )
    )


async def test_subscription_limit_removes_oldest_by_creation(
    client, db_session, world, app
) -> None:
    """Витісняється найдавніша за created_at, навіть якщо її updated_at свіжий (доставка)."""
    settings = get_settings().model_copy(update={"push_max_subscriptions_per_user": 3})
    app.dependency_overrides[get_settings] = lambda: settings
    ids = await _subscribe_with_times(client, db_session, world.teacher_a, 3)
    await client.post("/push/subscriptions", json=body(), headers=auth_header(world.teacher_a))
    left = await _left(db_session, world.teacher_a)
    assert len(left) == 3 and ids[0] not in left and set(ids[1:]) <= left


async def test_subscription_limit_removes_failed_first(client, db_session, world, app) -> None:
    settings = get_settings().model_copy(update={"push_max_subscriptions_per_user": 3})
    app.dependency_overrides[get_settings] = lambda: settings
    ids = await _subscribe_with_times(client, db_session, world.teacher_a, 3)
    failed = await db_session.get(PushSubscription, ids[2])
    failed.failed_at = failed.created_at
    await db_session.flush()
    await client.post("/push/subscriptions", json=body(), headers=auth_header(world.teacher_a))
    left = await _left(db_session, world.teacher_a)
    assert len(left) == 3 and ids[2] not in left and set(ids[:2]) <= left


async def test_delete_is_idempotent_and_own_only(client, db_session, world) -> None:
    data = body()
    await client.post("/push/subscriptions", json=data, headers=auth_header(world.parent_a))
    url = f"/push/subscriptions/{data['id']}"
    assert (await client.delete(url)).status_code == 401
    # Чужа підписка — та сама відповідь, що й неіснуюча (204), і вона не видаляється.
    response = await client.delete(url, headers=auth_header(world.student_a))
    missing = await client.delete(
        f"/push/subscriptions/{uuid.uuid4()}", headers=auth_header(world.student_a)
    )
    assert response.status_code == missing.status_code == 204
    assert response.content == missing.content == b""
    assert (
        await db_session.get(PushSubscription, uuid.UUID(data["id"]), populate_existing=True)
        is not None
    )
    assert (await client.delete(url, headers=auth_header(world.parent_a))).status_code == 204
    assert (
        await db_session.get(PushSubscription, uuid.UUID(data["id"]), populate_existing=True)
        is None
    )
    # Повтор (відповідь загубилася в мережі) — теж 204.
    assert (await client.delete(url, headers=auth_header(world.parent_a))).status_code == 204


# ---------- одержувачі ----------


async def _subscribe(db_session, *users) -> dict[uuid.UUID, uuid.UUID]:
    """Підписка на кожного користувача: user_id → subscription_id."""
    out = {}
    for user in users:
        sub = PushSubscription(
            id=uuid.uuid4(),
            user_id=user.id,
            endpoint=f"https://fcm.googleapis.com/fcm/send/{uuid.uuid4().hex}",
            p256dh=P256DH,
            auth=AUTH,
        )
        db_session.add(sub)
        out[user.id] = sub.id
    await db_session.flush()
    return out


@pytest.fixture
async def people(factory, world) -> SimpleNamespace:
    p = SimpleNamespace()
    p.student_a2 = await factory.student(world.class_a, "Ольга", "Іваненко")
    p.parent_a2 = await factory.parent_of(p.student_a2)
    p.parent_b = await factory.parent_of(world.student_b)
    p.inactive = await factory.student(world.class_a, "Петро", "Сидоренко")
    p.inactive.is_active = False
    return p


async def test_recipients_per_type(db_session, world, people) -> None:
    class_a = str(world.class_a.id)
    students_teachers = {
        world.student_a.id,
        people.student_a2.id,
        world.teacher_a.id,
    }
    parents = {world.parent_a.id, people.parent_a2.id}
    for push_type in ("alert", "all_clear"):
        got = await service.recipients(db_session, {"type": push_type, "class_id": class_a})
        assert set(got) == students_teachers | parents
    got = await service.recipients(db_session, {"type": "pack_updated", "class_id": class_a})
    assert set(got) == students_teachers
    got = await service.recipients(
        db_session, {"type": "rollcall_status", "student_id": str(world.student_a.id)}
    )
    assert got == [world.parent_a.id]
    assert await service.recipients(db_session, {"type": "unknown", "class_id": class_a}) == []
    assert await service.recipients(db_session, {"type": "alert"}) == []


async def test_fan_out_enqueues_delivery_per_subscription(
    db_session, world, people, monkeypatch, vapid
) -> None:
    subs = await _subscribe(db_session, world.student_a, world.parent_a, world.student_b)
    # Друга підписка того самого батька (інший пристрій).
    extra = await _subscribe(db_session, world.parent_a)

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr(worker, "standalone_session", session)
    got = await worker._fan_out({"type": "rollcall_status", "student_id": str(world.student_a.id)})
    assert set(got) == {subs[world.parent_a.id], extra[world.parent_a.id]}
    got = await worker._fan_out({"type": "pack_updated", "class_id": str(world.class_a.id)})
    assert got == [subs[world.student_a.id]]


def test_send_task_skips_without_vapid(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(worker.deliver, "apply_async", lambda *a, **k: called.append(a))
    assert worker.send.run({"type": "alert", "class_id": str(uuid.uuid4())}, "k") == 0
    assert called == []


def test_send_task_fans_out_with_same_key(monkeypatch) -> None:
    settings = vapid_settings()
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    subs = [uuid.uuid4(), uuid.uuid4()]

    async def fan_out(payload):
        return subs

    monkeypatch.setattr(worker, "_fan_out", fan_out)
    calls = []
    monkeypatch.setattr(worker.deliver, "apply_async", lambda **k: calls.append(k))
    payload = {"type": "alert", "class_id": str(uuid.uuid4())}
    assert worker.send.run(payload, "key-1") == 2
    assert [c["args"] for c in calls] == [[str(s), payload, "key-1"] for s in subs]
    assert all(c["queue"] == "push" for c in calls)


async def test_enqueue_push_payload_and_key(enqueued) -> None:
    class_id, alert_id = uuid.uuid4(), uuid.uuid4()
    await worker.enqueue_push("alert", class_id=class_id, alert_id=alert_id, lesson_id=None)
    await worker.enqueue_push("alert", class_id=class_id, alert_id=alert_id, lesson_id=None)
    await worker.enqueue_push(
        "rollcall_status", student_id=class_id, session_id=alert_id, status="safe", key="ev-1"
    )
    first, second, third = enqueued
    assert first.queue == "push" and first.name == "push.send"
    assert first.args[0] == {
        "type": "alert",
        "class_id": str(class_id),
        "alert_id": str(alert_id),
        "lesson_id": None,
    }
    # Те саме повідомлення — той самий ключ дедуплікації.
    assert first.args[1] == second.args[1]
    assert third.args == [
        {
            "type": "rollcall_status",
            "student_id": str(class_id),
            "session_id": str(alert_id),
            "status": "safe",
        },
        "ev-1",
    ]


# ---------- доставка ----------


class FakeSender:
    def __init__(self, *statuses: SendResult) -> None:
        self.statuses = list(statuses)
        self.calls: list[tuple[str, str, int, str]] = []

    def __call__(self, sub, data, settings, options) -> SendResult:
        self.calls.append((sub.endpoint, data, options.ttl, options.urgency))
        return self.statuses.pop(0)


async def test_deliver_success_options_and_payload(db_session, world) -> None:
    sub_id = (await _subscribe(db_session, world.parent_a))[world.parent_a.id]
    sender = FakeSender(SendResult(201))
    payload = {"type": "alert", "class_id": str(world.class_a.id), "alert_id": "a"}
    outcome = await service.deliver(db_session, sub_id, payload, vapid_settings(), sender)
    assert outcome == "sent"
    (_, data, ttl, urgency) = sender.calls[0]
    assert json.loads(data) == payload
    assert (ttl, urgency) == (600, "high")
    sub = await db_session.get(PushSubscription, sub_id)
    assert sub.last_success_at is not None
    sender = FakeSender(SendResult(201))
    await service.deliver(db_session, sub_id, {"type": "pack_updated"}, vapid_settings(), sender)
    assert sender.calls[0][2:] == (12 * 3600, "normal")


async def test_deliver_without_vapid_is_skipped(db_session, world) -> None:
    sub_id = (await _subscribe(db_session, world.parent_a))[world.parent_a.id]
    sender = FakeSender()
    outcome = await service.deliver(db_session, sub_id, {"type": "alert"}, get_settings(), sender)
    assert outcome == "disabled" and sender.calls == []


@pytest.mark.parametrize("status", [404, 410])
async def test_deliver_gone_removes_subscription(db_session, world, status) -> None:
    sub_id = (await _subscribe(db_session, world.parent_a))[world.parent_a.id]
    outcome = await service.deliver(
        db_session, sub_id, {"type": "alert"}, vapid_settings(), FakeSender(SendResult(status))
    )
    assert outcome == "gone"
    assert await db_session.get(PushSubscription, sub_id) is None
    assert (
        await service.deliver(db_session, sub_id, {"type": "alert"}, vapid_settings(), FakeSender())
        == "missing"
    )


@pytest.mark.parametrize("status", [0, 429, 500, 503])
async def test_deliver_temporary_error_raises_retry(db_session, world, status) -> None:
    sub_id = (await _subscribe(db_session, world.parent_a))[world.parent_a.id]
    with pytest.raises(service.PushRetry) as exc:
        await service.deliver(
            db_session,
            sub_id,
            {"type": "alert"},
            vapid_settings(),
            FakeSender(SendResult(status, 120)),
        )
    assert exc.value.retry_after == 120
    assert await db_session.get(PushSubscription, sub_id) is not None


async def test_deliver_permanent_error_marks_failed(db_session, world) -> None:
    sub_id = (await _subscribe(db_session, world.parent_a))[world.parent_a.id]
    outcome = await service.deliver(
        db_session, sub_id, {"type": "alert"}, vapid_settings(), FakeSender(SendResult(403))
    )
    assert outcome == "failed"
    sub = await db_session.get(PushSubscription, sub_id)
    assert sub is not None and sub.failed_at is not None


async def test_deliver_invalid_keys_removes_subscription(db_session, world) -> None:
    """Ключі, якими не зашифрувати payload, — постійна помилка: підписка видаляється, повтору
    немає (а не нескінченні збої на кожному push)."""
    sub_id = (await _subscribe(db_session, world.parent_a))[world.parent_a.id]
    outcome = await service.deliver(
        db_session,
        sub_id,
        {"type": "alert"},
        vapid_settings(),
        FakeSender(SendResult(service.INVALID_KEYS)),
    )
    assert outcome == "invalid"
    assert await db_session.get(PushSubscription, sub_id) is None


async def test_deliver_sends_in_thread_and_ignores_resubscribed_row(
    db_session, world, monkeypatch
) -> None:
    """Відправка — у потоці поза транзакцією; якщо під час неї підписку перевидали (інший
    endpoint), результат старої відправки (410) нову підписку не видаляє."""
    import threading

    import anyio

    sub_id = (await _subscribe(db_session, world.parent_a))[world.parent_a.id]
    sub = await db_session.get(PushSubscription, sub_id)
    old_endpoint = sub.endpoint
    in_main_thread = []

    def sender(target, data, settings, options):
        in_main_thread.append(threading.current_thread() is threading.main_thread())
        assert isinstance(target, service.PushTarget) and target.endpoint == old_endpoint
        return SendResult(410)

    real_run_sync = anyio.to_thread.run_sync

    async def run_sync(func, *args, **kwargs):
        result = await real_run_sync(func, *args, **kwargs)
        # Поки йшов HTTP-запит, браузер перевидав підписку з тим самим id.
        sub.endpoint = old_endpoint + "-new"
        await db_session.flush()
        return result

    monkeypatch.setattr(anyio.to_thread, "run_sync", run_sync)
    outcome = await service.deliver(db_session, sub_id, {"type": "alert"}, vapid_settings(), sender)
    assert in_main_thread == [False]
    assert outcome == "missing"
    kept = await db_session.get(PushSubscription, sub_id, populate_existing=True)
    assert kept is not None and kept.endpoint == old_endpoint + "-new"


def test_retry_delay_is_bounded() -> None:
    assert worker.retry_delay(0, None) == 30
    assert worker.retry_delay(2, None) == 120
    assert worker.retry_delay(0, 300) == 300
    assert worker.retry_delay(10, None) == worker.MAX_RETRY_DELAY_S
    assert worker.retry_delay(0, 10**6) == worker.MAX_RETRY_DELAY_S


class FakeRedis:
    store: dict[str, int] = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def delete(self, key):
        self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch) -> dict:
    FakeRedis.store = {}
    monkeypatch.setattr(worker, "redis_client", FakeRedis)
    return FakeRedis.store


def test_deliver_task_dedupes_repeats(monkeypatch, fake_redis) -> None:
    sent = []

    async def deliver(sub_id, payload):
        sent.append(sub_id)
        return "sent"

    monkeypatch.setattr(worker, "_deliver", deliver)
    sub = str(uuid.uuid4())
    assert worker.deliver.run(sub, {"type": "alert"}, "k1") == "sent"
    # Повтор задачі (повторна доставка брокером) — не надсилає вдруге.
    assert worker.deliver.run(sub, {"type": "alert"}, "k1") == "duplicate"
    # Інше повідомлення тій самій підписці — надсилається.
    assert worker.deliver.run(sub, {"type": "alert"}, "k2") == "sent"
    assert len(sent) == 2


def test_deliver_task_retries_temporary_error_and_releases_key(monkeypatch, fake_redis) -> None:
    attempts = []

    async def deliver(sub_id, payload):
        attempts.append(sub_id)
        if len(attempts) == 1:
            raise service.PushRetry(503)
        return "sent"

    monkeypatch.setattr(worker, "_deliver", deliver)
    sub = str(uuid.uuid4())
    with pytest.raises(Retry):
        worker.deliver.apply(args=[sub, {"type": "alert"}, "k1"], throw=True)
    assert fake_redis == {}
    # Повтор після тимчасової помилки надсилає.
    assert worker.deliver.run(sub, {"type": "alert"}, "k1") == "sent"


def test_deliver_task_gives_up_after_max_retries(monkeypatch, fake_redis) -> None:
    async def deliver(sub_id, payload):
        raise service.PushRetry(500)

    failed = []

    async def mark_failed(sub_id):
        failed.append(sub_id)

    monkeypatch.setattr(worker, "_deliver", deliver)
    monkeypatch.setattr(worker, "_mark_failed", mark_failed)
    sub = str(uuid.uuid4())
    result = worker.deliver.apply(
        args=[sub, {"type": "alert"}, "k1"], retries=worker.MAX_RETRIES, throw=True
    )
    assert result.get() == "failed"
    assert failed == [uuid.UUID(sub)]


def test_deliver_task_fails_open_without_redis(monkeypatch) -> None:
    class Down:
        def set(self, *args, **kwargs):
            raise ConnectionError("down")

        def delete(self, *args):
            raise ConnectionError("down")

    monkeypatch.setattr(worker, "redis_client", Down)
    sent = []

    async def deliver(sub_id, payload):
        sent.append(sub_id)
        return "sent"

    monkeypatch.setattr(worker, "_deliver", deliver)
    sub = str(uuid.uuid4())
    assert worker.deliver.run(sub, {"type": "alert"}, "k1") == "sent"
    assert worker.deliver.run(sub, {"type": "alert"}, "k1") == "sent"
    assert len(sent) == 2


def test_webpush_sender_maps_errors(monkeypatch) -> None:
    from pywebpush import WebPushException

    settings = vapid_settings()
    sub = PushSubscription(endpoint="https://fcm.googleapis.com/x", p256dh=P256DH, auth=AUTH)
    options = service.PUSH_OPTIONS["alert"]
    captured = {}

    def ok(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(status_code=201)

    monkeypatch.setattr(worker, "webpush", ok)
    assert worker.webpush_sender(sub, "{}", settings, options) == SendResult(201)
    assert captured["ttl"] == 600 and captured["headers"] == {"Urgency": "high"}
    assert captured["vapid_claims"] == {"sub": "mailto:admin@example.com"}

    def gone(**kwargs):
        response = SimpleNamespace(status_code=429, headers={"Retry-After": "60"})
        raise WebPushException("Push failed", response=response)

    monkeypatch.setattr(worker, "webpush", gone)
    assert worker.webpush_sender(sub, "{}", settings, options) == SendResult(429, 60)

    def network(**kwargs):
        import requests

        raise requests.ConnectionError("boom")

    monkeypatch.setattr(worker, "webpush", network)
    assert worker.webpush_sender(sub, "{}", settings, options) == SendResult(0)


def test_webpush_sender_invalid_keys_are_permanent(monkeypatch) -> None:
    """Справжній pywebpush: p256dh не на кривій P-256 (записаний до перевірки) — ValueError під
    час шифрування, ще до HTTP → `INVALID_KEYS`; без ключів — теж. Зламаний ключ VAPID — збій
    конфігурації: виняток, а не видалення підписки."""
    raw = bytearray(base64.urlsafe_b64decode(P256DH + "="))
    raw[-1] ^= 1
    bad = base64.urlsafe_b64encode(bytes(raw)).decode().rstrip("=")
    settings = vapid_settings()
    options = service.PUSH_OPTIONS["alert"]
    target = service.PushTarget(uuid.uuid4(), "https://fcm.googleapis.com/x", bad, AUTH)
    assert worker.webpush_sender(target, "{}", settings, options) == SendResult(
        service.INVALID_KEYS
    )

    def missing_keys(**kwargs):
        from pywebpush import WebPushException

        raise WebPushException("Missing keys")

    monkeypatch.setattr(worker, "webpush", missing_keys)
    assert worker.webpush_sender(target, "{}", settings, options) == SendResult(
        service.INVALID_KEYS
    )
    broken = settings.model_copy(update={"vapid_private_key": SecretStr("not-a-key")})
    with pytest.raises(Exception):  # noqa: B017 — будь-який виняток розбору ключа VAPID
        worker.webpush_sender(target, "{}", broken, options)


def test_workers_share_one_cached_redis_client() -> None:
    """Дедуплікація push і перерахунку класу — один клієнт (пул) на процес, а не нове
    з'єднання на кожен виклик; claim/release його не закривають."""
    from app.workers import redis_client as shared
    from app.workers import stats as stats_worker

    assert worker.redis_client is shared.redis_client is stats_worker.redis_client
    client = shared.redis_client()
    pool = client.connection_pool
    sub, key = str(uuid.uuid4()), f"test-{uuid.uuid4()}"
    worker.claim(key, sub)
    worker.release(key, sub)
    assert shared.redis_client() is client and client.connection_pool is pool
