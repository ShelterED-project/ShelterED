"""«Як ти зараз?»: видалення відповідей і записів `sync_event` типу `survey_answer`, старших
за 30 днів (beat раз на добу, черга `default`). Ідемпотентно: повторний запуск видаляє лише
те, що ще лишилось."""

import asyncio
from typing import Any

from celery.signals import worker_ready

from app.core.db import standalone_session
from app.services import wellbeing as wellbeing_service
from app.workers.celery_app import celery_app


async def _purge() -> dict[str, int]:
    async with standalone_session() as session:
        return await wellbeing_service.purge_old(session)


@celery_app.task(name="wellbeing.purge")
def purge() -> dict[str, int]:
    """Повертає кількість видалених відповідей і записів журналу подій (значень не логує)."""
    return asyncio.run(_purge())


@worker_ready.connect
def purge_on_startup(**_: Any) -> None:
    """Видалення ще й при старті воркера: якщо beat чи воркер лежали в час за розкладом,
    прострочені відповіді не чекатимуть наступної доби. Кілька воркерів — кілька запусків,
    це безпечно (ідемпотентно)."""
    purge.apply_async(queue="default")
