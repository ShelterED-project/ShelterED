"""Кабінети й агрегати (B14): перерахунок Celery-задачею після синхронізації, ідемпотентність,
дані кабінетів учня/батьків/вчителя й права доступу (тест на кожне правило)."""

import datetime as dt

import pytest
from conftest import auth_header
from httpx import AsyncClient
from sqlalchemy import func, select
from test_sync import attempt, batch, content, now, progress, send

from app.core.config import get_settings
from app.models.stats import ClassLessonStat, StudentLessonStat, StudentStudyDay, StudentTestStat
from app.services import stats as stats_service
from app.workers import stats as stats_worker
from app.workers.celery_app import celery_app

pytestmark = pytest.mark.anyio

RIGHT = lambda c: {c.q1.id: ["a"], c.q2.id: ["a", "c"]}  # noqa: E731
WRONG = lambda c: {c.q1.id: ["b"], c.q2.id: ["a"]}  # noqa: E731


@pytest.fixture
async def c(db_session, factory, world):
    return await content(db_session, factory, world.class_a, world.teacher_a)


async def recompute(db_session, student) -> None:
    await stats_service.recompute_for_student(db_session, student.id, get_settings())


async def learn(client, db_session, student, c, answers, at=None) -> None:
    """Учень проходить модуль і тест; потім — задача перерахунку (як після синхронізації)."""
    at = at or now() - dt.timedelta(minutes=10)
    await send(
        client,
        student,
        batch(
            progress(c.module.id, 100, at),
            attempt(c.test.id, answers, at + dt.timedelta(minutes=2)),
        ),
    )
    await recompute(db_session, student)


async def get(client: AsyncClient, user, url: str) -> dict:
    r = await client.get(url, headers=auth_header(user))
    assert r.status_code == 200, r.text
    return r.json()


# ---------- перерахунок ----------


async def test_sync_batch_enqueues_one_recompute_after_commit(client, world, c, enqueued) -> None:
    at = now() - dt.timedelta(minutes=5)
    body = batch(progress(c.module.id, 50, at), progress(c.module.id, 100, at))
    await send(client, world.student_a, body)
    tasks = [e for e in enqueued if e.name == "stats.recompute_student"]
    assert [(t.args, t.queue) for t in tasks] == [([str(world.student_a.id)], "default")]
    # Повтор того самого пакета (лише duplicate) нічого не ставить.
    await send(client, world.student_a, body)
    assert len([e for e in enqueued if e.name == "stats.recompute_student"]) == 1


async def test_recompute_is_idempotent(client, db_session, world, c) -> None:
    await learn(client, db_session, world.student_a, c, RIGHT(c))
    counts = []
    for _ in range(2):
        await recompute(db_session, world.student_a)
        counts.append(
            [
                await db_session.scalar(select(func.count()).select_from(m))
                for m in (StudentLessonStat, StudentTestStat, StudentStudyDay, ClassLessonStat)
            ]
        )
    assert counts[0] == counts[1] == [1, 1, 1, 1]


async def test_refresh_all_covers_students_without_activity(db_session, world, c) -> None:
    result = await stats_service.refresh_all(db_session, get_settings())
    assert result["students"] >= 3 and result["classes"] >= 3
    row = await db_session.get(StudentLessonStat, (world.student_a.id, c.lesson.id))
    assert row is not None and row.progress_pct == 0 and row.completed_at is None


@pytest.fixture
def worker_session(db_session, monkeypatch):
    """Задачі Celery бачать тестову транзакцію замість власної сесії."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def session():
        yield db_session

    monkeypatch.setattr(stats_worker, "standalone_session", session)


async def test_class_sync_schedules_one_debounced_class_recompute(
    client, db_session, world, factory, c, enqueued, worker_session
) -> None:
    """Клас синхронізується разом: задачі учнів рахують лише рядки учня й ставлять один
    відкладений перерахунок класу (а не N повних перерахунків). Задача класу знімає позначку,
    тож наступна синхронізація ставить новий перерахунок."""
    if not await _redis_available():
        pytest.skip("Redis is not available")
    students = [world.student_a] + [
        await factory.student(world.class_a, f"Учень{i}", "Тест") for i in range(3)
    ]
    for student in students:
        await send(client, student, batch(progress(c.module.id, 100, now())))
        assert await stats_worker._recompute_student(student.id) == 1
    class_tasks = [e for e in enqueued if e.name == "stats.recompute_class"]
    assert [t.args for t in class_tasks] == [[str(world.class_a.id)]]
    # Задача учня клас не рахує.
    assert await db_session.scalar(select(func.count()).select_from(ClassLessonStat)) == 0

    assert await stats_worker._recompute_class(world.class_a.id) is True
    row = await db_session.get(ClassLessonStat, (world.class_a.id, c.lesson.id))
    assert row is not None and row.students_completed == len(students)
    await stats_worker._recompute_student(world.student_a.id)
    assert len([e for e in enqueued if e.name == "stats.recompute_class"]) == 2
    await stats_worker._clear_pending(world.class_a.id)


async def test_class_recompute_without_redis_is_still_scheduled(
    db_session, world, enqueued, monkeypatch
) -> None:
    """Redis для дедуплікації недоступний — перерахунок класу однаково ставиться."""
    from redis.asyncio import Redis

    monkeypatch.setattr(
        stats_worker,
        "_redis",
        lambda: Redis.from_url("redis://127.0.0.1:1/0", socket_connect_timeout=0.2),
    )
    for _ in range(2):
        await stats_worker.enqueue_recompute_class(world.class_a.id)
    assert len([e for e in enqueued if e.name == "stats.recompute_class"]) == 2


async def _redis_available() -> bool:
    redis = stats_worker._redis()
    try:
        await redis.ping()
        return True
    except Exception:
        return False
    finally:
        await redis.aclose()


def test_tasks_and_beat_are_registered() -> None:
    assert {"stats.recompute_student", "stats.recompute_class", "stats.refresh_all"} <= set(
        celery_app.tasks
    )
    beat = celery_app.conf.beat_schedule["stats-refresh"]
    assert beat["task"] == "stats.refresh_all" and beat["options"]["queue"] == "default"


# ---------- кабінети ----------


async def test_student_and_parent_see_progress_and_study_time(client, db_session, world, c) -> None:
    await learn(client, db_session, world.student_a, c, RIGHT(c))
    for user in (world.student_a, world.parent_a):
        data = await get(client, user, f"/students/{world.student_a.id}/progress")
        (lesson,) = data["lessons"]
        assert lesson["progress_pct"] == 100 and lesson["modules_done"] == 1
        assert lesson["completed_at"] is not None and lesson["study_minutes"] == 4
        (test,) = data["tests"]
        assert test["status"] == "passed" and test["score"] == 100.0 and test["deadline"] is None
        assert data["study"]["total_minutes"] == 4
        assert data["study"]["last_7_days_minutes"] == 4 and len(data["study"]["days"]) == 7
    kmap = await get(client, world.student_a, f"/students/{world.student_a.id}/knowledge-map")
    assert kmap["subjects"][0]["lessons_completed"] == 1
    assert kmap["subjects"][0]["avg_score"] == 100.0 and kmap["subjects"][0]["is_gap"] is False


async def test_teacher_sees_class_progress_failed_tests_and_gaps(
    client, db_session, factory, world, c
) -> None:
    second = await factory.student(world.class_a, "Олена", "Шевчук")
    await learn(client, db_session, world.student_a, c, RIGHT(c))
    await learn(client, db_session, second, c, WRONG(c))
    third = await factory.student(world.class_a, "Петро", "Яковенко")  # нічого не робив
    await recompute(db_session, third)

    progress_ = await get(client, world.teacher_a, f"/classes/{world.class_a.id}/progress")
    (lesson,) = progress_["lessons"]
    assert lesson["students_total"] == 3 and lesson["students_completed"] == 2
    assert lesson["tests_scored"] == 2 and lesson["tests_passed"] == 1
    assert lesson["avg_score"] == 50.0

    tests = await get(client, world.teacher_a, f"/classes/{world.class_a.id}/tests")
    (test,) = tests["tests"]
    by_name = {s["display_name"]: s["status"] for s in test["students"]}
    assert by_name == {"Іван": "passed", "Олена": "not_passed", "Петро": "pending"}
    assert test["counts"] == {"passed": 1, "not_passed": 1, "closing_soon": 0, "pending": 1}

    gaps = await get(client, world.teacher_a, f"/classes/{world.class_a.id}/gaps")
    (topic,) = gaps["topics"]
    assert topic["is_gap"] is True  # середня 50 < 60
    assert [(q["prompt"], q["correct_pct"]) for q in topic["questions"]] == [
        ("1/2 + 1/2?", 50),
        ("Парні?", 50),
    ]


async def test_window_test_statuses_for_teacher(client, db_session, factory, world, c) -> None:
    c.test.window_enabled, c.test.window_hours = True, 24
    await db_session.flush()
    # Урок завершено 20 год тому, спроби немає → вікно закривається менш ніж за 6 год.
    await send(
        client, world.student_a, batch(progress(c.module.id, 100, now() - dt.timedelta(hours=20)))
    )
    await recompute(db_session, world.student_a)
    # Інший учень завершив 30 год тому й не здав → не склав.
    late = await factory.student(world.class_a, "Олена", "Шевчук")
    await send(client, late, batch(progress(c.module.id, 100, now() - dt.timedelta(hours=30))))
    await recompute(db_session, late)

    tests = await get(client, world.teacher_a, f"/classes/{world.class_a.id}/tests")
    (test,) = tests["tests"]
    assert test["window_hours"] == 24
    by_name = {s["display_name"]: s for s in test["students"]}
    assert by_name["Іван"]["status"] == "closing_soon" and by_name["Іван"]["deadline"]
    assert by_name["Олена"]["status"] == "not_passed"
    mine = await get(client, world.student_a, f"/students/{world.student_a.id}/progress")
    assert mine["tests"][0]["status"] == "closing_soon"


async def test_unrecomputed_class_is_empty_not_error(client, world) -> None:
    data = await get(client, world.teacher_a, f"/classes/{world.class_a.id}/progress")
    assert data == {"class_id": str(world.class_a.id), "computed_at": None, "lessons": []}


# ---------- права доступу ----------


@pytest.mark.parametrize("path", ["progress", "tests", "gaps"])
async def test_class_cabinet_only_for_teacher_of_the_class(client, world, path) -> None:
    url = f"/classes/{world.class_a.id}/{path}"
    assert (await client.get(url, headers=auth_header(world.teacher_a))).status_code == 200
    # Чужий вчитель, учень, батьки, адміністрація — 403; без токена — 401.
    for user in (world.teacher_b, world.student_a, world.parent_a, world.admin):
        r = await client.get(url, headers=auth_header(user))
        assert r.status_code == 403, user.role
    assert (await client.get(url)).status_code == 401


@pytest.mark.parametrize("path", ["progress", "knowledge-map"])
async def test_student_cabinet_access_rules(client, world, path) -> None:
    url = f"/students/{world.student_a.id}/{path}"
    # Учень — себе, батьки — свою дитину, вчитель — учня свого класу.
    for user in (world.student_a, world.parent_a, world.teacher_a):
        assert (await client.get(url, headers=auth_header(user))).status_code == 200, user.role
    # Інший учень, чужі батьки, вчитель іншого класу, адміністрація — 403.
    for user in (world.student_b, world.parent_free, world.teacher_b, world.admin):
        r = await client.get(url, headers=auth_header(user))
        assert r.status_code == 403, user.role
    unknown = "/students/00000000-0000-0000-0000-000000000000/" + path
    assert (await client.get(unknown, headers=auth_header(world.teacher_a))).status_code == 404


async def test_module_full_at_is_earliest_completion_event(client, db_session, world, c) -> None:
    """Офлайн-подія з ранішим завершенням, що прийшла пізніше, зсуває момент завершення."""
    from app.models.sync import ModuleProgress

    t2 = now() - dt.timedelta(hours=1)
    t1 = t2 - dt.timedelta(hours=2)
    await send(
        client, world.student_a, batch(progress(c.module.id, 40, t1 - dt.timedelta(hours=1)))
    )
    await send(client, world.student_a, batch(progress(c.module.id, 100, t2)))
    await send(client, world.student_a, batch(progress(c.module.id, 100, t1)))
    row = await db_session.get(ModuleProgress, (world.student_a.id, c.module.id))
    await db_session.refresh(row)
    assert row.full_at == t1.replace(microsecond=t1.microsecond)


# ---------- дашборд адміністрації (P2) ----------


async def test_admin_sees_study_time_during_school_alerts(client, db_session, world, c) -> None:
    from app.models.alerts import AlertEvent

    t = now()
    api_alert = AlertEvent(
        region_code="kyiv",
        school_id=world.school.id,
        source="api",
        external_id="a1",
        started_at=t - dt.timedelta(hours=1),
        ended_at=t - dt.timedelta(minutes=10),
    )
    # Ручна тривога іншого класу: навчання учня 7-А на неї не припадає.
    class_alert = AlertEvent(
        region_code="kyiv",
        school_id=world.school.id,
        class_id=world.class_b.id,
        source="manual",
        started_at=t - dt.timedelta(hours=1),
        ended_at=t - dt.timedelta(minutes=10),
    )
    db_session.add_all([api_alert, class_alert])
    await db_session.flush()
    await send(
        client, world.student_a, batch(progress(c.module.id, 100, t - dt.timedelta(minutes=30)))
    )
    result = await stats_service.refresh_all(db_session, get_settings())
    assert result["schools"] >= 2

    data = await get(client, world.admin, "/alerts/study")
    by_id = {a["alert_id"]: a for a in data["alerts"]}
    assert (by_id[str(api_alert.id)]["students"], by_id[str(api_alert.id)]["study_minutes"]) == (
        1,
        4,
    )
    assert by_id[str(class_alert.id)]["study_minutes"] == 0
    assert by_id[str(api_alert.id)]["duration_minutes"] == 50
    assert data["study_minutes"] == 4 and data["alert_minutes"] == 100
    # Адмін іншої школи не бачить чужих тривог; інші ролі — 403.
    assert (await get(client, world.other_admin, "/alerts/study"))["alerts"] == []
    for user in (world.teacher_a, world.student_a, world.parent_a):
        r = await client.get("/alerts/study", headers=auth_header(user))
        assert r.status_code == 403, user.role
