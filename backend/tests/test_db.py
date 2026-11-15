from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

pytestmark = pytest.mark.anyio


async def test_migrations_applied(db_session):
    version = await db_session.scalar(text("SELECT version_num FROM alembic_version"))
    alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    head = ScriptDirectory.from_config(Config(str(alembic_ini))).get_current_head()
    assert version == head


async def test_changes_are_rolled_back_part_1(db_session):
    await db_session.execute(text("CREATE TABLE isolation_probe (id int)"))
    await db_session.execute(text("INSERT INTO isolation_probe VALUES (1)"))
    await db_session.commit()
    assert await db_session.scalar(text("SELECT count(*) FROM isolation_probe")) == 1


async def test_changes_are_rolled_back_part_2(db_session):
    # Таблиця з попереднього тесту не має існувати, хоч там і був commit().
    exists = await db_session.scalar(text("SELECT to_regclass('isolation_probe')"))
    assert exists is None


async def test_uses_test_database(db_session):
    # Захист від випадкового запуску тестів на Neon.
    assert await db_session.scalar(text("SELECT current_database()")) == "sheltered_test"


def test_openapi_file_is_up_to_date():
    from app.cli import OPENAPI_PATH, render_openapi

    # read_text нормалізує CRLF, який Git на Windows може підставити.
    committed = OPENAPI_PATH.read_text(encoding="utf-8")
    assert committed == render_openapi(), (
        "docs/openapi.json is stale: run `python -m app.cli export-openapi` and commit it"
    )


async def test_progress_aggregates_backfill_accepts_decimal_progress(committed):
    """Міграція 69af2adf1d7f заповнює `module_progress.full_at` зі старих подій, де сирий
    payload міг мати `progress_pct: 100.0` (::int на ньому падав); вниз і знову вгору."""
    import datetime as dt
    import uuid

    import anyio
    from alembic import command
    from conftest import BACKEND_DIR

    from app.models.lessons import Lesson, Module

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    f = committed.factory
    school = await f.school()
    klass = await f.klass(school)
    teacher = await f.teacher(school, klass)
    student = await f.student(klass)
    subject = await f.subject()
    lesson = Lesson(
        subject_id=subject.id, author_id=teacher.id, title="Т", shelter_part="У", main_part="О"
    )
    committed.session.add(lesson)
    await committed.session.flush()
    module = Module(lesson_id=lesson.id, part="shelter", position=1, title="М", duration_min=4)
    committed.session.add(module)
    await committed.session.commit()

    at = dt.datetime(2026, 11, 5, 9, 0, tzinfo=dt.UTC)
    await anyio.to_thread.run_sync(command.downgrade, config, "827ed8465b1b")
    try:
        async with committed.maker() as db:
            for pct in ("100.0", "100"):
                event_id = uuid.uuid4()
                await db.execute(
                    text(
                        "INSERT INTO sync_event (client_event_id, type, user_id, device_id,"
                        " occurred_at, received_at, payload, status, source)"
                        " VALUES (:id, 'module_progress', :user, :device, :at, :at,"
                        " CAST(:payload AS jsonb), 'accepted', 'online')"
                    ),
                    {
                        "id": event_id,
                        "user": student.id,
                        "device": uuid.uuid4(),
                        "at": at if pct == "100.0" else at + dt.timedelta(hours=1),
                        "payload": f'{{"module_id": "{module.id}", "progress_pct": {pct}}}',
                    },
                )
            await db.execute(
                text(
                    "INSERT INTO module_progress (student_id, module_id, progress_pct,"
                    " last_event_id) VALUES (:student, :module, 100, :event)"
                ),
                {"student": student.id, "module": module.id, "event": event_id},
            )
            await db.commit()
    finally:
        await anyio.to_thread.run_sync(command.upgrade, config, "head")
    async with committed.maker() as db:
        full_at = await db.scalar(
            text("SELECT full_at FROM module_progress WHERE student_id = :s"), {"s": student.id}
        )
    assert full_at == at


async def test_app_connections_limit_idle_in_transaction(migrated_db, monkeypatch):
    """З'єднання застосунку (API-пул і Celery) мають idle_in_transaction_session_timeout:
    сесія, що простоює у відкритій транзакції, розривається сервером."""
    import asyncio

    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core import db
    from app.core.config import get_settings

    show = text("SHOW idle_in_transaction_session_timeout")
    async with db.standalone_session() as session:
        assert await session.scalar(show) == "1min"
    db.get_engine.cache_clear()
    try:
        async with db.get_engine().connect() as conn:
            assert await conn.scalar(show) == "1min"
    finally:
        await db.get_engine().dispose()
        db.get_engine.cache_clear()

    monkeypatch.setenv("DB_IDLE_IN_TRANSACTION_TIMEOUT_S", "1")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        engine = create_async_engine(
            migrated_db, connect_args=db.connect_args(settings), poolclass=NullPool
        )
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))  # транзакція відкрита
            await asyncio.sleep(1.5)
            with pytest.raises(DBAPIError):
                await conn.execute(text("SELECT 1"))
        await engine.dispose()
    finally:
        get_settings.cache_clear()


def test_pooler_endpoint_gets_no_server_settings(monkeypatch, caplog):
    """PgBouncer (pooled endpoint Neon) не приймає server_settings: не надсилаємо їх,
    попереджаємо в лозі один раз."""
    from pydantic import SecretStr

    from app.core import db
    from app.core.config import get_settings

    settings = get_settings().model_copy()
    direct = "postgresql+asyncpg://u:p@ep-x-123.eu-central-1.aws.neon.tech/db"
    settings.database_url = SecretStr(direct)
    assert "server_settings" in db.connect_args(settings)

    db._warn_pooler.cache_clear()
    settings.database_url = SecretStr(direct.replace("ep-x-123", "ep-x-123-pooler"))
    with caplog.at_level("WARNING", logger="app.core.db"):
        assert "server_settings" not in db.connect_args(settings)
        assert "server_settings" not in db.connect_args(settings)
    assert [r.message for r in caplog.records].count(caplog.records[0].message) == 1
    assert "-pooler" in caplog.records[0].message
    db._warn_pooler.cache_clear()
