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
