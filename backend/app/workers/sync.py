"""Переоцінка спроб після правок тесту вчителем (черга `sync`). Задача ідемпотентна: оцінка й
зарахування — чиста функція від спроб, ключа й вікна; повтор нічого не змінює."""

import asyncio
import uuid

from app.core.db import standalone_session
from app.services import sync as sync_service
from app.workers.celery_app import TRANSIENT_RETRY, celery_app, enqueue
from app.workers.stats import enqueue_recompute_student


async def enqueue_regrade_test(test_id: uuid.UUID) -> None:
    """Після commit правки вікна тесту, ключа чи балів питань."""
    await enqueue("sync.regrade_test", args=[str(test_id)], queue="sync")


async def _regrade_test(test_id: uuid.UUID) -> int:
    async with standalone_session() as session:
        students = await sync_service.regrade_test(session, test_id)
    # Кабінети (B14) читають агрегати: перерахувати учнів, чиї спроби могли змінитися.
    for student_id in students:
        await enqueue_recompute_student(student_id)
    return len(students)


@celery_app.task(name="sync.regrade_test", **TRANSIENT_RETRY)
def regrade_test(test_id: str) -> int:
    """Переоцінює спроби тесту й перераховує зарахування. Повертає кількість учнів."""
    return asyncio.run(_regrade_test(uuid.UUID(test_id)))
