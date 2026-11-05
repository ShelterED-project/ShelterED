"""Агрегати кабінетів (B14, черга `default`). Задачі ідемпотентні: повний перерахунок рядків
учня й класу під advisory lock, повтор чи паралельний запуск дає той самий результат."""

import asyncio
import uuid

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import stats as stats_service
from app.workers.celery_app import celery_app, enqueue


def enqueue_recompute_student(student_id: uuid.UUID) -> None:
    """Після commit пакета синхронізації: одна задача на пакет, а не на подію."""
    enqueue("stats.recompute_student", args=[str(student_id)])


async def _recompute_student(student_id: uuid.UUID) -> int:
    async with standalone_session() as session:
        return await stats_service.recompute_for_student(session, student_id, get_settings())


async def _refresh_all() -> dict[str, int]:
    async with standalone_session() as session:
        return await stats_service.refresh_all(session, get_settings())


@celery_app.task(name="stats.recompute_student")
def recompute_student(student_id: str) -> int:
    """Рядки учня, потім його класів. Повертає кількість перерахованих класів."""
    return asyncio.run(_recompute_student(uuid.UUID(student_id)))


@celery_app.task(name="stats.refresh_all")
def refresh_all() -> dict[str, int]:
    """Періодично (beat): новий день у розкладі, зміни уроків, пропущені задачі."""
    return asyncio.run(_refresh_all())
