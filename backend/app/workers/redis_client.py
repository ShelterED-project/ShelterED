"""Спільний клієнт Redis задач (дедуплікація push і відкладеного перерахунку класу).

Один клієнт із пулом з'єднань на процес (і на URL), а не нове з'єднання на кожен виклик.
Пул redis-py сам перевідкривається в дочірньому процесі після fork (prefork-воркер Celery).
Короткі таймаути: повільний Redis не має гальмувати задачі (виклики — fail-open).
"""

from functools import lru_cache

from redis import Redis

from app.core.config import get_settings


@lru_cache
def _client(url: str) -> Redis:
    return Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)


def redis_client() -> Redis:
    """Клієнт для `REDIS_URL`. Не закривати (`with`/`close()`): він спільний."""
    return _client(get_settings().redis_url)
