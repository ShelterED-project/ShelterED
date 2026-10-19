import os

# Тести ніколи не ходять у Neon: змінні оточення мають пріоритет над backend/.env,
# тож підміняємо БД до першого імпорту app.*.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://sheltered:sheltered@localhost:5433/sheltered_test",
)
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DATABASE_URL_DIRECT"] = TEST_DATABASE_URL
os.environ["DATABASE_SSL"] = "false"

from collections.abc import AsyncIterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session")
def migrated_db() -> str:
    """Один раз за запуск накочує всі міграції на тестову БД."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(config, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def db_session(migrated_db: str) -> AsyncIterator[AsyncSession]:
    """Сесія в транзакції, яка відкочується після тесту: тести не бачать даних один одного.

    Навіть commit() у коді, що тестується, стає лише savepoint усередині цієї транзакції.
    """
    engine = create_async_engine(migrated_db, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
    await engine.dispose()
