"""Перезбірка пакетів «Рюкзак» (черга `default`). Усі задачі ідемпотентні: без змін вмісту
нова версія не створюється й push не ставиться."""

import asyncio
import uuid

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import packs as packs_service
from app.workers.celery_app import celery_app, enqueue


def enqueue_rebuild_class(class_id: uuid.UUID) -> None:
    enqueue("packs.rebuild_class", args=[str(class_id)])


def enqueue_rebuild_for_lesson(lesson_id: uuid.UUID) -> None:
    enqueue("packs.rebuild_for_lesson", args=[str(lesson_id)])


async def _rebuild_class(class_id: uuid.UUID) -> int:
    async with standalone_session() as session:
        return len(await packs_service.rebuild_class(session, class_id, get_settings()))


async def _rebuild_for_lesson(lesson_id: uuid.UUID) -> int:
    async with standalone_session() as session:
        return len(await packs_service.rebuild_for_lesson(session, lesson_id, get_settings()))


async def _refresh_all() -> int:
    async with standalone_session() as session:
        return await packs_service.refresh_all(session, get_settings())


@celery_app.task(name="packs.rebuild_class")
def rebuild_class(class_id: str) -> int:
    """Пакети класу на 7 днів (зміна розкладу чи прив'язки уроку). Повертає к-сть нових версій."""
    return asyncio.run(_rebuild_class(uuid.UUID(class_id)))


@celery_app.task(name="packs.rebuild_for_lesson")
def rebuild_for_lesson(lesson_id: str) -> int:
    """Публікація чи зняття з публікації уроку: пакети класів, де він стоїть."""
    return asyncio.run(_rebuild_for_lesson(uuid.UUID(lesson_id)))


@celery_app.task(name="packs.refresh_all")
def refresh_all() -> int:
    """Періодично (beat): новий день у горизонті 7 днів, зміни, що не поставили перезбірку."""
    return asyncio.run(_refresh_all())
