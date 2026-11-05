"""Тест із вікном (B11): вікно від завершення останнього модуля уроку, зарахування першої
спроби в межах вікна за часом пристрою, спроби поза вікном зберігаються без зарахування,
порядок надходження подій не важливий, підозрілий час — позначка, а не блокування."""

import datetime as dt

import pytest
from conftest import auth_header
from sqlalchemy import select
from test_sync import attempt, batch, content, now, progress, send, statuses

from app.core.config import get_settings
from app.models.lessons import Module
from app.models.sync import Attempt
from app.services import stats as stats_service

pytestmark = pytest.mark.anyio

RIGHT = lambda c: {c.q1.id: ["a"], c.q2.id: ["a", "c"]}  # noqa: E731


@pytest.fixture
async def c(db_session, factory, world):
    c = await content(db_session, factory, world.class_a, world.teacher_a)
    c.test.window_enabled, c.test.window_hours = True, 48
    await db_session.flush()
    return c


async def attempts(db_session, student, c) -> list[tuple[str, float | None]]:
    rows = await db_session.execute(
        select(Attempt.credit_status, Attempt.score)
        .where(Attempt.student_id == student.id, Attempt.test_id == c.test.id)
        .order_by(Attempt.completed_at_client)
        .execution_options(populate_existing=True)
    )
    return [(s, None if v is None else float(v)) for s, v in rows]


async def test_offline_attempt_within_window_is_credited_after_late_sync(
    client, db_session, world, c
) -> None:
    """Урок завершено й тест здано офлайн 3 дні тому (в межах 48 год), синхронізація зараз."""
    done = now() - dt.timedelta(days=3)
    body = batch(
        progress(c.module.id, 100, done),
        attempt(c.test.id, RIGHT(c), done + dt.timedelta(hours=47)),
    )
    assert statuses(await send(client, world.student_a, body)) == [("accepted", None)] * 2
    assert await attempts(db_session, world.student_a, c) == [("credited", 100.0)]
    # Дубль пакета дає той самий один результат.
    assert statuses(await send(client, world.student_a, body)) == [("duplicate", None)] * 2
    assert await attempts(db_session, world.student_a, c) == [("credited", 100.0)]


async def test_attempt_after_deadline_is_stored_but_not_credited(
    client, db_session, world, c
) -> None:
    done = now() - dt.timedelta(days=3)
    await send(client, world.student_a, batch(progress(c.module.id, 100, done)))
    late = done + dt.timedelta(hours=48, seconds=1)
    assert statuses(
        await send(client, world.student_a, batch(attempt(c.test.id, RIGHT(c), late)))
    ) == [("accepted", None)]
    assert await attempts(db_session, world.student_a, c) == [("not_credited_late", 100.0)]
    # Вчитель бачить «не склав»: вікно минуло без зарахованої спроби.
    await stats_service.recompute_for_student(db_session, world.student_a.id, get_settings())
    r = await client.get(f"/classes/{world.class_a.id}/tests", headers=auth_header(world.teacher_a))
    (student,) = r.json()["tests"][0]["students"]
    assert student["status"] == "not_passed" and student["attempts"] == 1


async def test_first_attempt_within_window_wins_over_later_ones(
    client, db_session, world, c
) -> None:
    done = now() - dt.timedelta(days=4)
    wrong = {c.q1.id: ["b"], c.q2.id: ["a"]}
    await send(
        client,
        world.student_a,
        batch(
            progress(c.module.id, 100, done),
            attempt(c.test.id, wrong, done + dt.timedelta(hours=1)),
            attempt(c.test.id, RIGHT(c), done + dt.timedelta(hours=2)),
            attempt(c.test.id, RIGHT(c), done + dt.timedelta(hours=50)),
        ),
    )
    assert await attempts(db_session, world.student_a, c) == [
        ("credited", 0.0),
        ("not_credited_repeat", 100.0),
        ("not_credited_late", 100.0),
    ]


async def test_arrival_order_does_not_matter(client, db_session, world, c) -> None:
    """Спроба прийшла раніше за подію завершення модуля: поки завершення невідоме, спроба
    зарахована; подія модуля, що прийшла пізніше, робить її запізнілою (UPDATE рядка — тож
    зміна потрапляє в `GET /sync/changes`)."""
    done = now() - dt.timedelta(days=5)
    await send(
        client,
        world.student_a,
        batch(attempt(c.test.id, RIGHT(c), done + dt.timedelta(hours=60))),
    )
    assert await attempts(db_session, world.student_a, c) == [("credited", 100.0)]
    await send(client, world.student_a, batch(progress(c.module.id, 100, done)))
    assert await attempts(db_session, world.student_a, c) == [("not_credited_late", 100.0)]


async def test_window_starts_when_the_last_module_is_completed(
    client, db_session, world, c
) -> None:
    second = Module(lesson_id=c.lesson.id, part="main", position=1, title="М2", duration_min=3)
    db_session.add(second)
    await db_session.flush()
    first_done = now() - dt.timedelta(days=5)
    last_done = first_done + dt.timedelta(days=2)
    await send(
        client,
        world.student_a,
        batch(
            progress(c.module.id, 100, first_done),
            progress(second.id, 100, last_done),
            # 3 дні після першого модуля, але лише 1 день після останнього — у вікні.
            attempt(c.test.id, RIGHT(c), first_done + dt.timedelta(days=3)),
        ),
    )
    assert await attempts(db_session, world.student_a, c) == [("credited", 100.0)]


async def test_suspicious_device_time_is_flagged_not_blocked(client, db_session, world, c) -> None:
    done = now() - dt.timedelta(hours=2)
    body = batch(
        progress(c.module.id, 100, done),
        attempt(c.test.id, RIGHT(c), done + dt.timedelta(hours=1)),
        sent_at=now() - dt.timedelta(hours=3),  # годинник пристрою відстає на 3 год
    )
    assert statuses(await send(client, world.student_a, body)) == [("accepted", None)] * 2
    row = await db_session.scalar(select(Attempt).where(Attempt.student_id == world.student_a.id))
    assert row.credit_status == "credited" and row.is_suspicious is True
    await stats_service.recompute_for_student(db_session, world.student_a.id, get_settings())
    r = await client.get(f"/classes/{world.class_a.id}/tests", headers=auth_header(world.teacher_a))
    (student,) = r.json()["tests"][0]["students"]
    assert student["status"] == "passed" and student["is_suspicious"] is True


async def test_practice_test_has_no_window(client, db_session, world, c) -> None:
    c.test.window_enabled, c.test.window_hours = False, None
    await db_session.flush()
    done = now() - dt.timedelta(days=10)
    await send(
        client,
        world.student_a,
        batch(
            progress(c.module.id, 100, done),
            attempt(c.test.id, RIGHT(c), done + dt.timedelta(days=9)),
        ),
    )
    assert await attempts(db_session, world.student_a, c) == [("credited", 100.0)]
