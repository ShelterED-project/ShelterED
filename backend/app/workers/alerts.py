"""Опитування API тривог за розкладом Celery beat (черга `default`)."""

import asyncio

from app.core.config import get_settings
from app.core.db import standalone_session
from app.services import alerts as alerts_service
from app.services.alert_provider import AlertProvider, AlertsInUaProvider
from app.workers.celery_app import celery_app


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
