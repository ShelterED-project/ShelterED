"""Строки зберігання даних (beat раз на добу, черга `default`; правила —
`app/services/retention.py`). Ідемпотентно: повтор чи паралельний запуск безпечні."""

import asyncio

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import retention as retention_service
from app.workers.celery_app import LONG_TASK_LIMITS, celery_app


async def _purge() -> dict[str, int]:
    async with standalone_session() as session:
        return await retention_service.purge(session, get_settings())


@celery_app.task(name="retention.purge", **LONG_TASK_LIMITS)
def purge() -> dict[str, int]:
    """Повертає кількість змінених рядків по кожному правилу."""
    return asyncio.run(_purge())
