"""Закешовані пояснення ШІ-репетитора для пакета «Рюкзак» (B13.3, черга `default`).

Після публікації уроку `tutor.explain_lesson` просить AI пояснити кожен модуль з текстом і
зберігає відповіді (`tutor_explanation`), після чого перезбирає пакети класів з цим уроком.
AI-сервіс працює на ПК розробника й буває вимкнений: тоді задача повторюється кожні
15 хв до доби, а beat `tutor.explain_missing` раз на `TUTOR_EXPLANATIONS_INTERVAL_S` добирає
опубліковані уроки без пояснень. Усе ідемпотентне (унікальний ключ урок + версія + модуль).
"""

import asyncio
import logging
import uuid

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import tutor as tutor_service
from app.services.ai import AIClient
from app.workers.celery_app import celery_app, enqueue
from app.workers.packs import enqueue_rebuild_for_lesson

logger = logging.getLogger(__name__)

EXPLAIN_RETRY_COUNTDOWN_S = 15 * 60
# 96 × 15 хв = доба; далі урок добере beat.
EXPLAIN_MAX_RETRIES = 96


def ai_client() -> AIClient:
    """Клієнт AI для задач (тести підміняють транспорт)."""
    return AIClient.from_settings(get_settings())


async def enqueue_explain_lesson(lesson_id: uuid.UUID) -> None:
    """Після публікації уроку (після commit)."""
    await enqueue("tutor.explain_lesson", args=[str(lesson_id)])


async def _explain_lesson(lesson_id: uuid.UUID) -> tuple[int, bool]:
    client = ai_client()
    if not client.enabled:
        return 0, False
    async with standalone_session() as session:
        created, failed = await tutor_service.generate_explanations(session, lesson_id, client)
    if created:
        await enqueue_rebuild_for_lesson(lesson_id)
    return created, failed


async def _explain_missing() -> int:
    if not ai_client().enabled:
        return 0
    async with standalone_session() as session:
        lesson_ids = await tutor_service.lessons_missing_explanations(session)
    for lesson_id in lesson_ids:
        await enqueue_explain_lesson(lesson_id)
    return len(lesson_ids)


@celery_app.task(name="tutor.explain_lesson", bind=True, max_retries=EXPLAIN_MAX_RETRIES)
def explain_lesson(self, lesson_id: str) -> int:
    """Пояснення модулів уроку. AI недоступний — повтор через 15 хв (отримані вже збережені)."""
    created, failed = asyncio.run(_explain_lesson(uuid.UUID(lesson_id)))
    if failed:
        logger.info("AI unavailable, explanations postponed: lesson=%s", lesson_id)
        raise self.retry(countdown=EXPLAIN_RETRY_COUNTDOWN_S)
    return created


@celery_app.task(name="tutor.explain_missing")
def explain_missing() -> int:
    """Періодично (beat): опубліковані уроки без пояснень поточної версії."""
    return asyncio.run(_explain_missing())
