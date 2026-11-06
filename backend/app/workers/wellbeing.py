"""«Як ти зараз?»: видалення відповідей, старших за 30 днів (beat раз на добу, черга
`default`). Ідемпотентно: повторний запуск видаляє лише те, що ще лишилось."""

import asyncio

from app.core.db import standalone_session
from app.services import wellbeing as wellbeing_service
from app.workers.celery_app import celery_app


async def _purge() -> int:
    async with standalone_session() as session:
        return await wellbeing_service.purge_old(session)


@celery_app.task(name="wellbeing.purge")
def purge() -> int:
    """Повертає кількість видалених відповідей (саме значення не логується)."""
    return asyncio.run(_purge())
