"""Rate limiting входу (B15.3): лише невдалі спроби, 429 + Retry-After для вичерпаного ключа,
без блокування акаунта; Redis-реалізація й fail-open при недоступному Redis."""

import logging
import uuid

import pytest
from conftest import PASSWORD, PIN
from fastapi import FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis

from app.api.deps import get_rate_limiter
from app.core.config import get_settings
from app.core.rate_limit import MemoryRateLimiter, RedisRateLimiter, rule

pytestmark = pytest.mark.anyio

ACCOUNT_LIMIT = 10  # RATE_LIMIT_JOIN_ACCOUNT / RATE_LIMIT_LOGIN_ACCOUNT у conftest


def join(klass, name="Іван", last="Петренко", pin=PIN) -> dict:
    return {"join_code": klass.join_code, "display_name": name, "last_name": last, "pin": pin}


def authorize(email: str, password: str) -> dict:
    return {
        "email": email,
        "password": password,
        "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
        "code_challenge_method": "S256",
        "client_id": "sheltered-pwa",
    }


async def test_pin_guessing_is_limited_per_class_code_and_name(client: AsyncClient, world) -> None:
    for _ in range(ACCOUNT_LIMIT):
        r = await client.post("/auth/student/join", json=join(world.class_a, pin="9999"))
        assert r.status_code == 401
    r = await client.post("/auth/student/join", json=join(world.class_a, pin="9999"))
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMITED"
    retry_after = int(r.headers["Retry-After"])
    assert 0 < retry_after <= get_settings().rate_limit_window_s
    assert r.json()["error"]["details"] == {"retry_after": retry_after}
    # Ключ вичерпано: навіть вірний PIN чекає до кінця вікна (PIN не перевіряється).
    r = await client.post("/auth/student/join", json=join(world.class_a))
    assert r.status_code == 429
    # Ім'я нормалізується так само, як при вході: регістр і пробіли не обходять ліміт.
    r = await client.post("/auth/student/join", json=join(world.class_a, " іВАН ", "петренко"))
    assert r.status_code == 429
    # Інший учень того ж класу входить: блокування акаунтів однокласників немає.
    second = await client.post("/auth/student/join", json=join(world.class_a, "Нова", "Учениця"))
    assert second.status_code == 200


async def test_successful_logins_are_not_counted(client: AsyncClient, world) -> None:
    for _ in range(ACCOUNT_LIMIT + 3):
        r = await client.post("/auth/student/join", json=join(world.class_a))
        assert r.status_code == 200


async def test_per_ip_limit_across_names_and_codes(client: AsyncClient, world) -> None:
    """Перебір кодів класів з однієї адреси: кожен код — новий ключ акаунта, але IP один."""
    ip_limit = get_settings().rate_limit_join_ip
    for i in range(ip_limit):
        body = {**join(world.class_a, f"Учень{i}"), "join_code": f"BAD{i:05d}"}
        r = await client.post("/auth/student/join", json=body)
        assert r.status_code == 400
    r = await client.post("/auth/student/join", json=join(world.class_a, "Ще", "Один"))
    assert r.status_code == 429


async def test_adult_password_guessing_is_limited(client: AsyncClient, world) -> None:
    email = world.teacher_a.email
    for _ in range(ACCOUNT_LIMIT):
        r = await client.post("/auth/authorize", json=authorize(email, "wrong-password-123"))
        assert r.status_code == 401
    r = await client.post("/auth/authorize", json=authorize(email.upper(), PASSWORD))
    assert r.status_code == 429 and "Retry-After" in r.headers
    # Інший акаунт не зачеплено.
    r = await client.post("/auth/authorize", json=authorize(world.admin.email, PASSWORD))
    assert r.status_code == 200


async def test_memory_limiter_window_expires(monkeypatch) -> None:
    import app.core.rate_limit as rl

    clock = [1000.0]
    monkeypatch.setattr(rl.time, "monotonic", lambda: clock[0])
    limiter = MemoryRateLimiter()
    rules = [rule("t", "k", 2, 60)]
    await limiter.hit(rules)
    assert await limiter.retry_after(rules) is None
    await limiter.hit(rules)
    assert await limiter.retry_after(rules) == 61
    clock[0] += 61
    assert await limiter.retry_after(rules) is None


async def test_redis_limiter_counts_in_fixed_window() -> None:
    """Справжній Redis (docker-compose.dev.yml, порт 6380); у CI без Redis — пропуск."""
    settings = get_settings()
    limiter = RedisRateLimiter(settings.rate_limit_redis_url)
    try:
        await limiter.redis.ping()
    except Exception:
        await limiter.close()
        pytest.skip("Redis is not available")
    rules = [rule("test", uuid.uuid4().hex, 3, 30)]
    try:
        for _ in range(3):
            assert await limiter.retry_after(rules) is None
            await limiter.hit(rules)
        assert 0 < await limiter.retry_after(rules) <= 30
        # У Redis — хеш, а не ідентифікатор.
        assert rules[0].key.startswith("rl:test:") and len(rules[0].key) == len("rl:test:") + 32
    finally:
        await limiter.redis.delete(rules[0].key)
        await limiter.close()


async def test_redis_down_fails_open(caplog, app: FastAPI, client: AsyncClient, world) -> None:
    # Порт без Redis: ліміт не діє, вхід працює, у лог — попередження без ключів.
    limiter = RedisRateLimiter("redis://127.0.0.1:1/0", timeout_s=0.2)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with caplog.at_level(logging.WARNING, logger="app.core.rate_limit"):
        for _ in range(ACCOUNT_LIMIT + 1):
            r = await client.post("/auth/student/join", json=join(world.class_a, pin="9999"))
            assert r.status_code == 401
        r = await client.post("/auth/student/join", json=join(world.class_a))
        assert r.status_code == 200
    assert any("Rate limiter unavailable" in m for m in caplog.messages)
    assert not any("rl:" in m for m in caplog.messages)
    await limiter.close()


async def test_redis_client_is_separate_from_celery_db() -> None:
    client = Redis.from_url(get_settings().rate_limit_redis_url)
    assert client.connection_pool.connection_kwargs["db"] == 2
    await client.aclose()
