"""AI-аналіз тесту класу (черга `default`): `test_analysis.run` після кнопки вчителя.

Задача одна на аналіз: збирає спроби, викликає AI (до `AI_ANALYSIS_TIMEOUT_S`) і переводить
аналіз у `draft` або `failed`. Повторів немає: AI-сервіс сам підставляє шаблони, коли LLM
недоступна, тож помилка тут — сервіс вимкнений; вчитель натисне кнопку ще раз. Аналіз, що
завис (воркер упав), API переведе у `failed` через `AI_ANALYSIS_STALE_S`. Ідемпотентно:
аналіз не в `processing` задача не чіпає.
"""

import asyncio
import uuid

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import test_analysis as service
from app.services.ai import AIClient
from app.workers.celery_app import celery_app, enqueue


def ai_client() -> AIClient:
    """Клієнт AI для задачі (тести підміняють транспорт)."""
    return AIClient.from_settings(get_settings())


async def enqueue_run(analysis_id: uuid.UUID) -> None:
    """Після commit нового аналізу."""
    await enqueue("test_analysis.run", args=[str(analysis_id)])


async def _run(analysis_id: uuid.UUID) -> str | None:
    async with standalone_session() as session:
        return await service.run(session, analysis_id, ai_client(), get_settings())


@celery_app.task(name="test_analysis.run")
def run(analysis_id: str) -> str | None:
    return asyncio.run(_run(uuid.UUID(analysis_id)))
