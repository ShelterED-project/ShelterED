from app.workers.celery_app import celery_app
from app.workers.system import ping


def test_queues():
    names = {queue.name for queue in celery_app.conf.task_queues}
    assert names == {"default", "push", "sync"}
    assert celery_app.conf.task_default_queue == "default"


def test_reliability_settings():
    assert celery_app.conf.task_acks_late is True
    assert celery_app.conf.worker_prefetch_multiplier == 1


def test_ping_runs_locally():
    # Виклик як звичайної функції — без брокера; з брокером перевіряється вручну.
    assert ping() == "pong"
