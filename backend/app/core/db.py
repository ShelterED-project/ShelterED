from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    if settings.database_url is None:
        raise RuntimeError("DATABASE_URL is not set")
    return create_async_engine(
        settings.database_url.get_secret_value(),
        # asyncpg не розуміє sslmode в URL, тому TLS передаємо напряму драйверу.
        connect_args={"ssl": "require"} if settings.database_ssl else {},
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        # Neon засинає й рве простої з'єднання: перевіряємо з'єднання перед видачею
        # і не тримаємо його довше 5 хв.
        pool_pre_ping=True,
        pool_recycle=300,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: після commit об'єкти лишаються читабельними
    # (інакше доступ до поля в async-коді спробує неявно сходити в БД).
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-залежність: одна сесія на запит, закривається після відповіді."""
    async with get_sessionmaker()() as session:
        yield session
