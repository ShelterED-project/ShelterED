"""Rate limiting входу (B15.3): лише невдалі спроби, 429 + Retry-After для вичерпаного ключа,
ключ акаунта = IP + акаунт (перебір з одного IP не блокує власника на іншому IP);
Redis-реалізація й fail-open при недоступному Redis."""

import logging
import uuid

import pytest
from conftest import PASSWORD, PIN
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.api.deps import get_rate_limiter
from app.core.config import get_settings
from app.core.rate_limit import MemoryRateLimiter, RedisRateLimiter, rule

pytestmark = pytest.mark.anyio

ACCOUNT_LIMIT = 10  # RATE_LIMIT_JOIN_ACCOUNT / RATE_LIMIT_LOGIN_ACCOUNT у conftest


def join(klass, name="Іван", last="Петренко", pin=PIN) -> dict:
    return {"join_code": klass.join_code, "display_name": name, "last_name": last, "pin": pin}


def from_ip(app: FastAPI, ip: str) -> AsyncClient:
    """Клієнт, запити якого приходять з адреси `ip` (той самий застосунок і rate limiter)."""
    return AsyncClient(transport=ASGITransport(app=app, client=(ip, 50000)), base_url="http://test")


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


async def test_pin_guessing_from_one_ip_does_not_block_owner_on_another_ip(
    app: FastAPI, world
) -> None:
    """Однокласник перебирає PIN з телефона (IP A) — блокує лише себе; власник з IP B входить."""
    async with from_ip(app, "10.0.0.1") as attacker, from_ip(app, "10.0.0.2") as owner:
        for _ in range(ACCOUNT_LIMIT):
            r = await attacker.post("/auth/student/join", json=join(world.class_a, pin="9999"))
            assert r.status_code == 401
        r = await attacker.post("/auth/student/join", json=join(world.class_a))
        assert r.status_code == 429
        r = await owner.post("/auth/student/join", json=join(world.class_a))
        assert r.status_code == 200
        # Невдачі власника рахуються окремо від невдач нападника.
        r = await owner.post("/auth/student/join", json=join(world.class_a, pin="9999"))
        assert r.status_code == 401


async def test_password_guessing_from_one_ip_does_not_block_owner_on_another_ip(
    app: FastAPI, world
) -> None:
    email = world.teacher_a.email
    async with from_ip(app, "10.0.0.1") as attacker, from_ip(app, "10.0.0.2") as owner:
        for _ in range(ACCOUNT_LIMIT):
            r = await attacker.post("/auth/authorize", json=authorize(email, "wrong-password-123"))
            assert r.status_code == 401
        r = await attacker.post("/auth/authorize", json=authorize(email, PASSWORD))
        assert r.status_code == 429
        r = await owner.post("/auth/authorize", json=authorize(email, PASSWORD))
        assert r.status_code == 200


async def test_ip_limit_is_high_enough_for_a_class_behind_one_nat(
    client: AsyncClient, world
) -> None:
    """Уся школа за одним NAT: ліміт на IP (300) не менший за десятки помилок класу."""
    settings = get_settings()
    assert settings.rate_limit_join_ip >= 300 and settings.rate_limit_login_ip >= 300
    for i in range(30):
        r = await client.post(
            "/auth/student/join", json=join(world.class_a, f"Учень{i}", pin="9999")
        )
        assert r.status_code in (200, 401)
    r = await client.post("/auth/student/join", json=join(world.class_a))
    assert r.status_code == 200


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


async def test_client_ip_comes_from_trusted_proxy_header(app: FastAPI, world) -> None:
    """За Nginx (довірений проксі uvicorn, Dockerfile: --proxy-headers + FORWARDED_ALLOW_IPS)
    клієнти з різними X-Forwarded-For мають окремі лічильники, а не один на IP Nginx."""
    from pathlib import Path

    from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text()
    assert '"--proxy-headers"' in dockerfile and "ENV FORWARDED_ALLOW_IPS=" in dockerfile

    proxied = ProxyHeadersMiddleware(app, trusted_hosts="172.18.0.2")
    transport = ASGITransport(app=proxied, client=("172.18.0.2", 50000))
    async with AsyncClient(transport=transport, base_url="http://test") as nginx:
        attacker = {"X-Forwarded-For": "203.0.113.1"}
        owner = {"X-Forwarded-For": "203.0.113.2"}
        for _ in range(ACCOUNT_LIMIT):
            r = await nginx.post(
                "/auth/student/join", json=join(world.class_a, pin="9999"), headers=attacker
            )
            assert r.status_code == 401
        r = await nginx.post("/auth/student/join", json=join(world.class_a), headers=attacker)
        assert r.status_code == 429
        r = await nginx.post("/auth/student/join", json=join(world.class_a), headers=owner)
        assert r.status_code == 200


async def test_redis_limiter_never_leaves_a_key_without_ttl() -> None:
    """Ключ без TTL (старий неатомарний SET NX + INCR) не блокує назавжди: `hit` ставить
    вікно атомарно, а `retry_after` не обмежує за ключем без строку й повертає йому вікно."""
    settings = get_settings()
    limiter = RedisRateLimiter(settings.rate_limit_redis_url)
    try:
        await limiter.redis.ping()
    except Exception:
        await limiter.close()
        pytest.skip("Redis is not available")
    stuck = rule("test", uuid.uuid4().hex, 3, 30)
    fresh = rule("test", uuid.uuid4().hex, 3, 30)
    try:
        await limiter.redis.set(stuck.key, 99)  # без EX: TTL -1
        assert await limiter.retry_after([stuck]) is None
        assert 0 < await limiter.redis.ttl(stuck.key) <= 30
        await limiter.redis.set(stuck.key, 1)
        await limiter.hit([stuck, fresh])
        assert int(await limiter.redis.get(stuck.key)) == 2
        assert int(await limiter.redis.get(fresh.key)) == 1
        assert 0 < await limiter.redis.ttl(stuck.key) <= 30
        assert 0 < await limiter.redis.ttl(fresh.key) <= 30
    finally:
        await limiter.redis.delete(stuck.key, fresh.key)
        await limiter.close()
