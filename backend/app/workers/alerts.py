"""Опитування API тривог за розкладом Celery beat (черга `default`)."""

import asyncio
import datetime as dt

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import alerts as alerts_service
from app.services.alert_provider import AlertProvider, AlertsInUaProvider
from app.workers.celery_app import ALERTS_LESSON_START_INTERVAL_S, celery_app


async def _poll(provider: AlertProvider) -> dict[str, int | str]:
    async with standalone_session() as session:
        return await alerts_service.poll(session, provider)


@celery_app.task(name="alerts.poll")
def poll() -> dict[str, int | str]:
    """Ідемпотентна: повторний чи паралельний запуск не дублює тривоги, перекличку й push.
    Без ALERTS_API_TOKEN нічого не робить (лишається ручна кнопка)."""
    settings = get_settings()
    if not settings.alerts_polling_enabled:
        return {"skipped": "disabled"}
    return asyncio.run(_poll(AlertsInUaProvider(settings)))


async def _auto_close() -> dict[str, int]:
    async with standalone_session() as session:
        return await alerts_service.auto_close_stale(session, get_settings())


@celery_app.task(name="alerts.auto_close")
def auto_close() -> dict[str, int]:
    """Забуті ручні тривоги й переклички (ALERTS_MANUAL_MAX_HOURS). Ідемпотентна."""
    return asyncio.run(_auto_close())


# Вікно «урок щойно почався» — два інтервали beat: запас на затримку beat чи черги, щоб
# старт уроку між двома запусками не загубився. Дублів немає: клас із перекличкою цієї
# тривоги пропускається.
LESSON_START_WINDOW = dt.timedelta(seconds=2 * ALERTS_LESSON_START_INTERVAL_S)


async def _lesson_starts() -> dict[str, int]:
    async with standalone_session() as session:
        return await alerts_service.react_lesson_starts(session, LESSON_START_WINDOW)


@celery_app.task(name="alerts.lesson_starts")
def lesson_starts() -> dict[str, int]:
    """Урок почався під час активної тривоги → перекличка + push `alert`, як на початку
    тривоги. Ідемпотентна: повтор чи паралельний запуск не дублює перекличку й push."""
    return asyncio.run(_lesson_starts())
