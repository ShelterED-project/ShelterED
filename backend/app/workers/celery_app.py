import logging
from functools import partial
from typing import Any

import anyio
from celery import Celery
from kombu import Queue

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

celery_app = Celery(
    "sheltered",
    broker=settings.redis_url,
    backend=settings.redis_result_url,
    # Модулі із задачами; новий домен додається сюди разом із файлом workers/<домен>.py.
    include=[
        "app.workers.system",
        "app.workers.push",
        "app.workers.alerts",
        "app.workers.packs",
        "app.workers.stats",
        "app.workers.sync",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_queues=[Queue("default"), Queue("push"), Queue("sync")],
    task_default_queue="default",
    # Задача підтверджується після виконання, а не при отриманні: якщо воркер
    # упаде посеред задачі, вона повернеться в чергу («нічого не губимо»).
    # Тому всі задачі мають бути ідемпотентними.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    # Періодичні задачі (процес `celery beat`). expires: прострочений запуск (воркер
    # лежав) не виконується пачкою — наступний однаково прийде за розкладом.
    beat_schedule={
        "alerts-poll": {
            "task": "alerts.poll",
            "schedule": float(settings.alerts_poll_interval_s),
            "options": {"queue": "default", "expires": settings.alerts_poll_interval_s},
        },
        "packs-refresh": {
            "task": "packs.refresh_all",
            "schedule": float(settings.packs_refresh_interval_s),
            "options": {"queue": "default", "expires": settings.packs_refresh_interval_s},
        },
        "stats-refresh": {
            "task": "stats.refresh_all",
            "schedule": float(settings.stats_refresh_interval_s),
            "options": {"queue": "default", "expires": settings.stats_refresh_interval_s},
        },
    },
)


# Публікація задачі: кілька коротких повторів замість типових (до ~хвилини), щоб недоступний
# брокер не тримав запит API.
PUBLISH_RETRY_POLICY = {
    "max_retries": 2,
    "interval_start": 0,
    "interval_step": 0.2,
    "interval_max": 0.5,
}


def _send(name: str, args: list[Any], queue: str, options: dict[str, Any]) -> None:
    options.setdefault("retry", True)
    options.setdefault("retry_policy", PUBLISH_RETRY_POLICY)
    celery_app.send_task(name, args=args, queue=queue, **options)


async def enqueue(
    name: str, *, args: list[Any] | None = None, queue: str = "default", **options: Any
) -> None:
    """Ставить задачу в чергу за іменем (без імпорту модуля задачі).

    Викликається ПІСЛЯ commit. `send_task` блокує (мережа до Redis, повтори), тож іде в пулі
    потоків, а не в циклі подій. Недоступний брокер не ламає вже збережену зміну: помилка
    логується, а наслідки підбирає повтор (ідемпотентні задачі, періодичні перезбірки,
    `GET /alerts/active` як запасний шлях для push).
    """
    try:
        await anyio.to_thread.run_sync(partial(_send, name, args or [], queue, options))
    except Exception:
        logger.exception("Failed to enqueue task %s", name)
