import threading

import pytest

from app.workers import celery_app as celery_module
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


@pytest.mark.anyio
async def test_enqueue_publishes_off_the_event_loop_with_short_retries(monkeypatch):
    """`send_task` блокує (Redis, повтори публікації): з async-обробника він іде в потоці, а
    повтори короткі, тож недоступний брокер не тримає запит API; помилка не пробивається."""
    loop_thread = threading.get_ident()
    calls = []

    def send_task(name, args=None, queue=None, **options):
        calls.append((threading.get_ident(), name, options))
        if name == "broken":
            raise ConnectionError("broker down")

    monkeypatch.setattr(celery_app, "send_task", send_task)
    await celery_module.enqueue("stats.recompute_student", args=["x"])
    await celery_module.enqueue("broken")
    assert [c[1] for c in calls] == ["stats.recompute_student", "broken"]
    thread, _, options = calls[0]
    assert thread != loop_thread
    assert options["retry"] is True and options["retry_policy"]["max_retries"] <= 2


def test_tasks_without_catch_up_retry_transient_errors():
    """push.send (push тривоги) і sync.regrade_test не мають періодичного добирання: виняток
    (БД чи брокер недоступні) має дати повтор, а не загубити задачу."""
    for name in ("push.send", "sync.regrade_test"):
        task = celery_app.tasks[name]
        assert Exception in task.autoretry_for, name
        assert task.max_retries and task.max_retries > 0, name


def test_tasks_have_time_limits():
    """Завислий виклик не тримає воркер вічно; довгі періодичні задачі мають більший ліміт."""
    celery_app.loader.import_default_modules()
    conf = celery_app.conf
    assert 0 < conf.task_soft_time_limit < conf.task_time_limit
    for name in ("packs.refresh_all", "stats.refresh_all", "retention.purge"):
        task = celery_app.tasks[name]
        assert conf.task_soft_time_limit < task.soft_time_limit < task.time_limit, name
    # Прибирання журналу подій зупиняється само раніше за м'який ліміт.
    from app.services.retention import SYNC_EVENT_MAX_S

    assert SYNC_EVENT_MAX_S < celery_app.tasks["retention.purge"].soft_time_limit
