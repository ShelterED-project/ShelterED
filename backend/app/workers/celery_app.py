from celery import Celery
from kombu import Queue

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "sheltered",
    broker=settings.redis_url,
    backend=settings.redis_result_url,
    # Модулі із задачами; новий домен додається сюди разом із файлом workers/<домен>.py.
    include=["app.workers.system"],
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
)
