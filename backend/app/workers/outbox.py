"""Публікація задач із `task_outbox` (beat кожні 30 с, черга `default`).

Рядок з'являється, коли `enqueue` не зміг поставити задачу (брокер недоступний). Задача
бере неопубліковані рядки (`FOR UPDATE SKIP LOCKED`: паралельний запуск не публікує ті самі),
публікує по черзі й ставить `sent_at`. Перша помилка брокера зупиняє прохід (`attempts` + 1),
решту добере наступний запуск. Подвійна публікація (збій між публікацією й commit) безпечна:
усі задачі ідемпотентні (push дедуплікується за ключем).
"""

import asyncio
import datetime as dt
import logging

from sqlalchemy import select

from app.core.db import standalone_session
from app.models.outbox import TaskOutbox
from app.workers import celery_app as celery_module
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

FLUSH_BATCH = 100


def _pending() -> bool:
    """Чи є позначка «в outbox щось є». Redis недоступний — так (перевіряємо БД)."""
    from app.workers.redis_client import redis_client

    try:
        return bool(redis_client().exists(celery_module.OUTBOX_PENDING_KEY))
    except Exception:
        return True


async def _flush(batch_size: int = FLUSH_BATCH) -> int:
    # Без позначки в БД не ходимо: інакше запит кожні 30 с не дає Neon засинати.
    if not _pending():
        return 0
    _clear_pending()
    sent = 0
    left = True
    async with standalone_session() as session:
        rows = list(
            await session.scalars(
                select(TaskOutbox)
                .where(TaskOutbox.sent_at.is_(None))
                .order_by(TaskOutbox.created_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        for row in rows:
            try:
                celery_module._send(row.task_name, row.args, row.queue, {})
            except Exception:
                row.attempts += 1
                logger.exception("Outbox task %s still cannot be published", row.task_name)
                break
            row.sent_at = dt.datetime.now(dt.UTC)
            sent += 1
        else:
            left = len(rows) == batch_size
        await session.commit()
    if left:
        # Помилка брокера чи повна пачка: лишилось що публікувати — наступний запуск добере.
        celery_module.mark_outbox_pending()
    return sent


def _clear_pending() -> None:
    from app.workers.redis_client import redis_client

    try:
        redis_client().delete(celery_module.OUTBOX_PENDING_KEY)
    except Exception:
        logger.warning("Cannot clear outbox pending mark in Redis")


@celery_app.task(name="outbox.flush")
def flush() -> int:
    """Повертає кількість опублікованих задач."""
    return asyncio.run(_flush())
