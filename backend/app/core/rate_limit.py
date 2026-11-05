"""Rate limiting входу (B15.3): захист PIN учня і пароля дорослих від перебору.

Рахуються лише **невдалі** спроби (хибний PIN/пароль, невідомий код класу) у фіксованому
вікні на кожен ключ; коли лічильник досяг ліміту, наступні запити з цим ключем отримують
429 `RATE_LIMITED` з `Retry-After` до кінця вікна. Блокування акаунта немає: обмеження
знімається само, а вчитель може скинути PIN (рішення B3: діти могли б блокувати однокласників).

Ключі в Redis — sha256 від ідентифікатора (код класу + ім'я, email, IP), без персональних
даних у відкритому вигляді.

**Fail-open:** якщо Redis недоступний, вхід дозволяється, а в лог іде попередження. Для
офлайн-першого застосунку недоступність входу гірша за тимчасову відсутність ліміту (argon2
однаково робить перебір повільним).
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Rule:
    """Ліміт `limit` невдалих спроб за `window_s` секунд для ключа `key`."""

    key: str
    limit: int
    window_s: int


def rule(scope: str, identity: str, limit: int, window_s: int) -> Rule:
    digest = hashlib.sha256(identity.encode()).hexdigest()[:32]
    return Rule(f"rl:{scope}:{digest}", limit, window_s)


class RateLimiter(Protocol):
    async def retry_after(self, rules: list[Rule]) -> int | None:
        """Секунди до кінця вікна, якщо хоч один ключ вичерпав ліміт, інакше None."""
        ...

    async def hit(self, rules: list[Rule]) -> None:
        """Зарахувати невдалу спробу всім ключам."""
        ...


class RedisRateLimiter:
    """Фіксоване вікно в Redis: `SET key 0 EX window NX` + `INCR` (працює з будь-якою версією
    Redis). Короткі таймаути: повільний Redis не має гальмувати вхід."""

    def __init__(self, url: str, timeout_s: float = 0.5) -> None:
        self.redis = Redis.from_url(url, socket_timeout=timeout_s, socket_connect_timeout=timeout_s)

    async def retry_after(self, rules: list[Rule]) -> int | None:
        try:
            async with self.redis.pipeline(transaction=False) as pipe:
                for r in rules:
                    pipe.get(r.key)
                    pipe.ttl(r.key)
                values = await pipe.execute()
        except (RedisError, OSError) as exc:
            logger.warning("Rate limiter unavailable, allowing request: %s", type(exc).__name__)
            return None
        wait = [
            max(int(ttl), 1)
            for r, count, ttl in zip(rules, values[::2], values[1::2], strict=True)
            if count is not None and int(count) >= r.limit
        ]
        return max(wait) if wait else None

    async def hit(self, rules: list[Rule]) -> None:
        try:
            async with self.redis.pipeline(transaction=False) as pipe:
                for r in rules:
                    pipe.set(r.key, 0, ex=r.window_s, nx=True)
                    pipe.incr(r.key)
                await pipe.execute()
        except (RedisError, OSError) as exc:
            logger.warning("Rate limiter unavailable, attempt not counted: %s", type(exc).__name__)

    async def close(self) -> None:
        await self.redis.aclose()


class MemoryRateLimiter:
    """Те саме в пам'яті процесу: для тестів (і без Redis — не для кількох воркерів)."""

    def __init__(self) -> None:
        self.counters: dict[str, tuple[int, float]] = {}

    def _get(self, key: str) -> tuple[int, float] | None:
        item = self.counters.get(key)
        if item is not None and item[1] <= time.monotonic():
            del self.counters[key]
            return None
        return item

    async def retry_after(self, rules: list[Rule]) -> int | None:
        wait = []
        for r in rules:
            item = self._get(r.key)
            if item is not None and item[0] >= r.limit:
                wait.append(max(int(item[1] - time.monotonic()) + 1, 1))
        return max(wait) if wait else None

    async def hit(self, rules: list[Rule]) -> None:
        for r in rules:
            count, expires = self._get(r.key) or (0, time.monotonic() + r.window_s)
            self.counters[r.key] = (count + 1, expires)
