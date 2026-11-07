import logging
from functools import partial
from typing import Any

import anyio
from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.config import get_settings
from app.core.db import standalone_session
from app.models.outbox import TaskOutbox

logger = logging.getLogger(__name__)

settings = get_settings()

# Як часто beat публікує задачі з `task_outbox`.
OUTBOX_FLUSH_INTERVAL_S = 30

# Ліміти часу задач за замовчуванням і для довгих задач (усі класи, прибирання пакетами).
TASK_SOFT_TIME_LIMIT_S = 300
LONG_TASK_SOFT_TIME_LIMIT_S = 1800
LONG_TASK_LIMITS: dict[str, Any] = {
    "soft_time_limit": LONG_TASK_SOFT_TIME_LIMIT_S,
    "time_limit": LONG_TASK_SOFT_TIME_LIMIT_S + 60,
}

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
        "app.workers.wellbeing",
        "app.workers.retention",
        "app.workers.outbox",
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
    # Ліміти часу: завислий виклик (БД, push-сервіс, мережа) не тримає воркер вічно. М'який
    # ліміт кидає SoftTimeLimitExceeded у задачу (транзакція відкочується), жорсткий через 30 с
    # убиває процес. Задача, що перевищила ліміт, підтверджується (acks_on_failure_or_timeout)
    # і не повертається в чергу по колу; періодичні задачі добере наступний запуск beat.
    # Довгі задачі (перезбірки всіх класів, прибирання) мають свої ліміти — `LONG_TASK_LIMITS`.
    # На Windows із `--pool=solo` ліміти не діють (лише в prefork у Docker).
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT_S,
    task_time_limit=TASK_SOFT_TIME_LIMIT_S + 30,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    # Періодичні задачі (процес `celery beat`). expires: прострочений запуск (воркер
    # лежав) не виконується пачкою — наступний однаково прийде за розкладом.
    beat_schedule={
        # Задачі, які не вдалося поставити, поки брокер лежав (`task_outbox`).
        "outbox-flush": {
            "task": "outbox.flush",
            "schedule": float(OUTBOX_FLUSH_INTERVAL_S),
            "options": {"queue": "default", "expires": OUTBOX_FLUSH_INTERVAL_S},
        },
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
        # «Як ти зараз?»: сирі відповіді живуть 30 днів (docs/wellbeing-checkin.md). Щодня
        # о 01:30 UTC (03:30 за Києвом узимку, 04:30 улітку); пропущений запуск надолужує
        # старт воркера (`app.workers.wellbeing`).
        "wellbeing-purge": {
            "task": "wellbeing.purge",
            "schedule": crontab(hour=1, minute=30),
            "options": {"queue": "default", "expires": 6 * 3600},
        },
        # Строки зберігання (app/services/retention.py): щодня о 02:00 UTC. Пропущений запуск
        # не страшний — наступний прибере все прострочене.
        "retention-purge": {
            "task": "retention.purge",
            "schedule": crontab(hour=2, minute=0),
            "options": {"queue": "default", "expires": 6 * 3600},
        },
    },
)


# Повтори задачі без періодичного «добирання» (push.send, sync.regrade_test): збій БД чи брокера
# посеред задачі інакше губить її назавжди (acks_late повертає задачу лише при падінні воркера,
# а не при винятку). Задачі ідемпотентні, тож повтор безпечний. Відступ 5, 10, 20 с.
TRANSIENT_RETRY: dict[str, Any] = {
    "autoretry_for": (Exception,),
    "max_retries": 3,
    "retry_backoff": 5,
    "retry_jitter": False,
}


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
    потоків, а не в циклі подій. Недоступний брокер не ламає вже збережену зміну й не губить
    задачу: вона записується в `task_outbox`, і beat-задача `outbox.flush` опублікує її, щойно
    брокер повернеться (задачі ідемпотентні, повтор безпечний). Відкладення (`countdown`)
    при цьому не зберігається: задача з outbox іде одразу.
    """
    args = args or []
    try:
        await anyio.to_thread.run_sync(partial(_send, name, args, queue, options))
    except Exception:
        logger.exception("Failed to enqueue task %s, storing it in the outbox", name)
        try:
            await _store_in_outbox(name, args, queue)
        except Exception:
            logger.exception("Failed to store task %s in the outbox", name)


async def _store_in_outbox(name: str, args: list[Any], queue: str) -> None:
    async with standalone_session() as session:
        session.add(TaskOutbox(task_name=name, args=args, queue=queue))
        await session.commit()
