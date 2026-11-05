"""Rate limiting входу (B15.3): захист PIN учня і пароля дорослих від перебору.

Рахуються лише **невдалі** спроби (хибний PIN/пароль, невідомий код класу) у фіксованому
вікні на кожен ключ; коли лічильник досяг ліміту, наступні запити з цим ключем отримують
429 `RATE_LIMITED` з `Retry-After` до кінця вікна. Блокування акаунта немає: обмеження
знімається само, а вчитель може скинути PIN (рішення B3: діти могли б блокувати однокласників).
Ліміт «на акаунт» рахується на пару (IP + акаунт), тож хто перебирає чужий PIN, блокує лише
себе; окремий ліміт на IP високий (увесь клас може бути за одним NAT). Ще один, дуже високий
ліміт на акаунт з усіх IP разом зупиняє перебір зі зміною IP (ботнет, проксі).

Ключі в Redis — sha256 від ідентифікатора (IP + код класу + ім'я, IP + email, IP, акаунт), без
персональних даних у відкритому вигляді.

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


# Атомарно для кожного ключа: INCR і TTL вікна в одному скрипті. Окремі `SET NX EX` + `INCR`
# могли б (ключ прострочився між ними) створити ключ без TTL — вічне блокування. TTL -1
# (ключ без строку з будь-якої причини) теж лікується: вікно ставиться заново.
_HIT_SCRIPT = """
for i, key in ipairs(KEYS) do
  local n = redis.call('INCR', key)
  if n == 1 or redis.call('TTL', key) < 0 then
    redis.call('EXPIRE', key, ARGV[i])
  end
end
return #KEYS
"""


class RedisRateLimiter:
    """Фіксоване вікно в Redis: атомарний Lua-скрипт `INCR` + `EXPIRE` на першій спробі вікна.
    Короткі таймаути: повільний Redis не має гальмувати вхід."""

    def __init__(self, url: str, timeout_s: float = 0.5) -> None:
        self.redis = Redis.from_url(url, socket_timeout=timeout_s, socket_connect_timeout=timeout_s)
        self._hit = self.redis.register_script(_HIT_SCRIPT)

    async def retry_after(self, rules: list[Rule]) -> int | None:
        try:
            async with self.redis.pipeline(transaction=False) as pipe:
                for r in rules:
                    pipe.get(r.key)
                    pipe.ttl(r.key)
                values = await pipe.execute()
            wait = []
            for r, count, ttl in zip(rules, values[::2], values[1::2], strict=True):
                if count is None or int(count) < r.limit:
                    continue
                if int(ttl) < 0:
                    # Ключ без строку не блокує назавжди: не обмежуємо й повертаємо вікно.
                    logger.warning("Rate limit key without TTL, restoring window")
                    await self.redis.expire(r.key, r.window_s)
                    continue
                wait.append(max(int(ttl), 1))
        except (RedisError, OSError) as exc:
            logger.warning("Rate limiter unavailable, allowing request: %s", type(exc).__name__)
            return None
        return max(wait) if wait else None

    async def hit(self, rules: list[Rule]) -> None:
        try:
            await self._hit(keys=[r.key for r in rules], args=[r.window_s for r in rules])
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
