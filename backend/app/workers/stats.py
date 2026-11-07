"""Агрегати кабінетів (B14, черга `default`). Задачі ідемпотентні: повний перерахунок рядків
учня й класу під advisory lock, повтор чи паралельний запуск дає той самий результат.

Рядки класу рахуються окремою відкладеною задачею з дедуплікацією: коли весь клас
синхронізується разом, N задач учнів ставлять один перерахунок класу, а не N (було O(n²)).
"""

import asyncio
import logging
import uuid

from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import stats as stats_service
from app.workers.celery_app import LONG_TASK_LIMITS, celery_app, enqueue
from app.workers.redis_client import redis_client

logger = logging.getLogger(__name__)


async def enqueue_recompute_student(student_id: uuid.UUID) -> None:
    """Після commit пакета синхронізації: одна задача на пакет, а не на подію."""
    await enqueue("stats.recompute_student", args=[str(student_id)])


async def enqueue_recompute_alert_study(school_id: uuid.UUID) -> None:
    """Після commit відбою: навчання під час тривог школи одразу, а не за годину в
    `stats.refresh_all` (пізні синхронізації однаково доберуть періодичний перерахунок)."""
    await enqueue("stats.recompute_alert_study", args=[str(school_id)])


def _pending_key(class_id: uuid.UUID) -> str:
    return f"sheltered:stats:class_pending:{class_id}"


async def enqueue_recompute_class(class_id: uuid.UUID) -> None:
    """Перерахунок класу через `STATS_CLASS_DEBOUNCE_S`, не більше одного в очікуванні:
    ключ у Redis (`SET NX`, TTL з запасом) ставить задачу лише перший. Задача знімає ключ
    перед перерахунком, тож зміни учнів після її старту поставлять наступну. Redis
    недоступний — задача ставиться без дедуплікації (зайвий перерахунок краще пропущеного)."""
    delay = get_settings().stats_class_debounce_s
    first = True
    try:
        # Синхронний спільний клієнт: виклик короткий (таймаут 0,5 с), а задача — у воркері.
        first = bool(redis_client().set(_pending_key(class_id), 1, nx=True, ex=delay + 60))
    except (RedisError, OSError) as exc:
        logger.warning("Class recompute dedup unavailable: %s", type(exc).__name__)
    if first:
        await enqueue("stats.recompute_class", args=[str(class_id)], countdown=delay)


async def _clear_pending(class_id: uuid.UUID) -> None:
    try:
        redis_client().delete(_pending_key(class_id))
    except (RedisError, OSError) as exc:
        logger.warning("Class recompute dedup unavailable: %s", type(exc).__name__)


async def _recompute_student(student_id: uuid.UUID) -> int:
    async with standalone_session() as session:
        class_ids = await stats_service.recompute_student_rows(session, student_id)
    for class_id in class_ids:
        await enqueue_recompute_class(class_id)
    return len(class_ids)


async def _recompute_class(class_id: uuid.UUID) -> bool:
    await _clear_pending(class_id)
    async with standalone_session() as session:
        done = await stats_service.recompute_class(session, class_id, get_settings())
        await session.commit()
        return done


async def _recompute_alert_study(school_id: uuid.UUID) -> int:
    async with standalone_session() as session:
        rows = await stats_service.recompute_alert_study(session, school_id, get_settings())
        await session.commit()
        return rows


async def _refresh_all() -> dict[str, int]:
    async with standalone_session() as session:
        return await stats_service.refresh_all(session, get_settings())


@celery_app.task(name="stats.recompute_student")
def recompute_student(student_id: str) -> int:
    """Рядки учня; класам — відкладений перерахунок. Повертає кількість класів учня."""
    return asyncio.run(_recompute_student(uuid.UUID(student_id)))


@celery_app.task(name="stats.recompute_class")
def recompute_class(class_id: str) -> bool:
    """Рядки класу з уже закомічених рядків учнів (відкладено, одна в очікуванні на клас)."""
    return asyncio.run(_recompute_class(uuid.UUID(class_id)))


@celery_app.task(name="stats.recompute_alert_study")
def recompute_alert_study(school_id: str) -> int:
    """Навчання під час тривог школи (після відбою). Повертає кількість рядків тривог."""
    return asyncio.run(_recompute_alert_study(uuid.UUID(school_id)))


@celery_app.task(name="stats.refresh_all", **LONG_TASK_LIMITS)
def refresh_all() -> dict[str, int]:
    """Періодично (beat): новий день у розкладі, зміни уроків, пропущені задачі."""
    return asyncio.run(_refresh_all())
