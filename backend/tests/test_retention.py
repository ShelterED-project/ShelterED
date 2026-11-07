"""Строки зберігання (B15.1): payload журналу подій, відхилені події, прострочені токени й коди,
журнал переглядів «Як ти зараз?». Ідемпотентність прийому подій не ламається."""

import datetime as dt
import uuid

import pytest
from sqlalchemy import func, select, update
from test_sync import attempt, batch, content, progress, send

from app.core.config import get_settings
from app.models.auth import AuthCode, ParentLinkCode, RefreshToken
from app.models.outbox import TaskOutbox
from app.models.sync import Attempt, ModuleProgress, SyncEvent
from app.models.wellbeing import WellbeingViewLog
from app.services import retention
from app.workers.celery_app import celery_app

pytestmark = pytest.mark.anyio


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def age_events(db, days: int) -> None:
    await db.execute(update(SyncEvent).values(received_at=now() - dt.timedelta(days=days)))


async def test_old_event_payload_is_cleared_but_duplicate_detection_survives(
    client, db_session, factory, world
) -> None:
    c = await content(db_session, factory, world.class_a, world.teacher_a)
    t = now()
    good = attempt(c.test.id, {c.q1.id: ["a"]}, t - dt.timedelta(minutes=1))
    prog = progress(c.module.id, 40, t - dt.timedelta(minutes=2))
    bad = progress(uuid.uuid4(), 10, t)  # невідомий модуль — rejected
    results = await send(client, world.student_a, batch(good, prog, bad))
    assert [r["status"] for r in results] == ["accepted", "accepted", "rejected"]

    await age_events(db_session, 179)
    assert (await retention.purge(db_session, get_settings()))["sync_event_payloads"] == 0
    await age_events(db_session, 181)
    await db_session.execute(
        update(SyncEvent)
        .where(SyncEvent.client_event_id == good["client_event_id"])
        .values(is_suspicious=True)
    )
    counts = await retention.purge(db_session, get_settings())
    assert counts["sync_event_payloads"] == 2 and counts["sync_event_rejected"] == 1

    rows = list(
        await db_session.scalars(select(SyncEvent).execution_options(populate_existing=True))
    )
    assert len(rows) == 2 and all(r.payload == {} for r in rows)
    # Разом із payload — id пристрою й зсув годинника; позначка підозрілого часу лишається.
    assert all(r.device_id is None and r.clock_skew_ms is None for r in rows)
    assert sorted(r.is_suspicious for r in rows) == [False, True]
    # Результати подій на місці.
    assert (await db_session.scalar(select(Attempt))).answers
    assert (await db_session.scalar(select(ModuleProgress))).progress_pct == 40

    # Повтор старих прийнятих подій — `duplicate`, друга спроба не з'являється.
    again = await send(client, world.student_a, batch(good, prog))
    assert [r["status"] for r in again] == ["duplicate", "duplicate"]
    assert len(list(await db_session.scalars(select(Attempt)))) == 1

    # Повторний запуск нічого не змінює.
    counts = await retention.purge(db_session, get_settings())
    assert counts["sync_event_payloads"] == 0 and counts["sync_event_rejected"] == 0


async def test_expired_auth_rows_and_old_view_logs_are_deleted(db_session, world) -> None:
    student = world.student_a
    t = now()
    family = uuid.uuid4()
    newest = RefreshToken(
        user_id=student.id, family_id=family, token_hash="n", expires_at=t - dt.timedelta(days=8)
    )
    db_session.add(newest)
    await db_session.flush()
    older = RefreshToken(
        user_id=student.id,
        family_id=family,
        token_hash="o",
        expires_at=t - dt.timedelta(days=9),
        replaced_by_id=newest.id,
    )
    fresh = RefreshToken(
        user_id=student.id,
        family_id=uuid.uuid4(),
        token_hash="f",
        expires_at=t - dt.timedelta(days=6),
    )
    db_session.add_all(
        [
            older,
            fresh,
            AuthCode(
                code_hash="c1",
                user_id=student.id,
                code_challenge="x",
                client_id="sheltered-pwa",
                expires_at=t - dt.timedelta(days=8),
            ),
            ParentLinkCode(
                code_hash="l1", child_id=student.id, expires_at=t - dt.timedelta(days=31)
            ),
            ParentLinkCode(
                code_hash="l2", child_id=student.id, expires_at=t - dt.timedelta(days=29)
            ),
            WellbeingViewLog(
                viewer_id=world.parent_a.id,
                student_id=student.id,
                viewed_at=t - dt.timedelta(days=366),
            ),
            WellbeingViewLog(
                viewer_id=world.parent_a.id,
                student_id=student.id,
                viewed_at=t - dt.timedelta(days=364),
            ),
        ]
    )
    await db_session.flush()

    counts = await retention.purge(db_session, get_settings())
    assert counts["refresh_tokens"] == 2 and counts["auth_codes"] == 1
    assert counts["parent_link_codes"] == 1 and counts["wellbeing_view_log"] == 1
    assert list(await db_session.scalars(select(RefreshToken.token_hash))) == ["f"]
    assert list(await db_session.scalars(select(ParentLinkCode.code_hash))) == ["l2"]
    assert len(list(await db_session.scalars(select(WellbeingViewLog)))) == 1

    again = await retention.purge(db_session, get_settings())
    assert set(again.values()) == {0}


async def test_purge_is_scheduled_daily() -> None:
    entry = celery_app.conf.beat_schedule["retention-purge"]
    assert entry["task"] == "retention.purge"
    assert (
        "retention.purge" in celery_app.tasks or "app.workers.retention" in celery_app.conf.include
    )


async def test_sync_events_are_purged_in_batches(client, db_session, factory, world) -> None:
    """Пакети по `batch_size` рядків (кожен — свій commit) до кінця; ліміт часу зупиняє
    прохід, а наступний запуск добирає решту."""
    c = await content(db_session, factory, world.class_a, world.teacher_a)
    t = now()
    events = [progress(c.module.id, 10 + i, t - dt.timedelta(minutes=i)) for i in range(5)]
    await send(client, world.student_a, batch(*events))
    await age_events(db_session, 181)

    first = await retention.purge(db_session, get_settings(), batch_size=2, max_s=0)
    assert first["sync_event_payloads"] == 2  # ліміт часу: один пакет за запуск
    rest = await retention.purge(db_session, get_settings(), batch_size=2)
    assert rest["sync_event_payloads"] == 3
    left = await db_session.scalar(
        select(func.count()).select_from(SyncEvent).where(SyncEvent.device_id.is_not(None))
    )
    assert left == 0


async def test_retention_index_is_used_for_old_events(db_session) -> None:
    from sqlalchemy import text

    await db_session.execute(text("SET LOCAL enable_seqscan = off"))
    # На майже порожній таблиці (оцінка — 1 рядок) вартості рівні, і залежно від статистики,
    # що лишили інші тести, планувальник бере й ix_sync_event_user_id_received_at із фільтром.
    # Перевіряємо саме те, що частковий індекс підходить під запит: конкурента прибираємо
    # (DDL у транзакції тесту, відкотиться разом із нею).
    await db_session.execute(text("DROP INDEX ix_sync_event_user_id_received_at"))
    plan = "\n".join(
        await db_session.scalars(
            text(
                "EXPLAIN SELECT client_event_id FROM sync_event "
                "WHERE received_at < now() AND device_id IS NOT NULL "
                "ORDER BY received_at LIMIT 5000"
            )
        )
    )
    assert "ix_sync_event_retention" in plan


async def test_published_outbox_tasks_are_deleted(db_session) -> None:
    now = dt.datetime.now(dt.UTC)
    old = TaskOutbox(task_name="a", args=[], queue="default", sent_at=now - dt.timedelta(days=2))
    fresh = TaskOutbox(task_name="b", args=[], queue="default", sent_at=now)
    pending = TaskOutbox(task_name="c", args=[], queue="default")
    db_session.add_all([old, fresh, pending])
    await db_session.flush()
    counts = await retention.purge(db_session, get_settings(), now)
    assert counts["task_outbox"] == 1
    left = set(await db_session.scalars(select(TaskOutbox.task_name)))
    assert left == {"b", "c"}
