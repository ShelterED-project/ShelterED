from app.workers.celery_app import celery_app


@celery_app.task(name="system.ping")
def ping() -> str:
    """Тестова задача: перевіряє, що воркер отримує й виконує задачі (B1.4)."""
    return "pong"
