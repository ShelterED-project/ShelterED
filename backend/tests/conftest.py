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
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789"
# Настройки, від яких залежать результати тестів, не беремо з backend/.env розробника.
os.environ["ACCESS_TOKEN_TTL_MIN"] = "15"
os.environ["REFRESH_TOKEN_TTL_DAYS"] = "30"
os.environ["REFRESH_REUSE_GRACE_SECONDS"] = "300"
os.environ["AUTH_CODE_TTL_S"] = "60"
os.environ["PARENT_LINK_CODE_TTL_DAYS"] = "7"
os.environ["OAUTH_CLIENT_IDS"] = '["sheltered-pwa"]'
os.environ["CORS_ORIGINS"] = '["http://localhost:5173"]'
# Опитування API тривог у тестах вимкнене; провайдер підміняють фейком.
os.environ["ALERTS_API_TOKEN"] = ""
os.environ["ALERTS_SOURCE_STALE_S"] = "300"
os.environ["SYNC_SUSPICIOUS_SKEW_S"] = "300"
os.environ["SYNC_ROLLCALL_CLOSE_GRACE_S"] = "120"
os.environ["STATS_PASS_SCORE"] = "60"
os.environ["STATS_CLOSING_SOON_H"] = "6"
os.environ["STATS_CLASS_DEBOUNCE_S"] = "30"
os.environ["RATE_LIMIT_JOIN_ACCOUNT"] = "10"
os.environ["RATE_LIMIT_JOIN_IP"] = "300"
os.environ["RATE_LIMIT_LOGIN_ACCOUNT"] = "10"
os.environ["RATE_LIMIT_LOGIN_IP"] = "300"
os.environ["RATE_LIMIT_JOIN_ACCOUNT_ALL_IPS"] = "100"
os.environ["RATE_LIMIT_LOGIN_ACCOUNT_ALL_IPS"] = "100"
os.environ["RATE_LIMIT_WINDOW_S"] = "900"

import uuid  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from functools import lru_cache  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.api.deps import get_rate_limiter, get_storage  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.db import get_session  # noqa: E402
from app.core.rate_limit import MemoryRateLimiter  # noqa: E402
from app.core.security import create_access_token, hash_secret, new_link_code  # noqa: E402
from app.core.storage import LocalMediaStorage  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.lessons import Subject  # noqa: E402
from app.models.school import (  # noqa: E402
    ClassMembership,
    ParentChild,
    School,
    SchoolClass,
    User,
)
from app.services.auth import name_key  # noqa: E402
from app.workers.celery_app import celery_app  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def enqueued(monkeypatch: pytest.MonkeyPatch) -> list[SimpleNamespace]:
    """Задачі, поставлені в чергу Celery (брокер у тестах не потрібен).

    Кожен елемент: name, args, queue. Push — name == "push.send", args[0] — payload.
    """
    calls: list[SimpleNamespace] = []

    def send_task(name, args=None, kwargs=None, queue=None, **options):
        calls.append(SimpleNamespace(name=name, args=list(args or []), queue=queue))

    monkeypatch.setattr(celery_app, "send_task", send_task)
    return calls


def pushes(calls: list[SimpleNamespace], push_type: str | None = None) -> list[dict]:
    """Payload поставлених push (опційно лише одного типу)."""
    return [
        c.args[0]
        for c in calls
        if c.name == "push.send" and (push_type is None or c.args[0]["type"] == push_type)
    ]


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


# ---------- користувачі й HTTP-клієнт для тестів авторизації ----------

PASSWORD = "correct-horse-battery"
PIN = "1234"


@lru_cache
def _password_hash() -> str:
    return hash_secret(PASSWORD)


@lru_cache
def _pin_hash() -> str:
    return hash_secret(PIN)


class Factory:
    """Створює школи, класи й користувачів у поточній тестовій транзакції."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def school(self, name: str = "Школа 1") -> School:
        school = School(name=name, region_code="kyiv")
        self.session.add(school)
        await self.session.flush()
        return school

    async def klass(self, school: School, name: str = "7-А", *, expires=None) -> SchoolClass:
        klass = SchoolClass(
            school_id=school.id,
            name=name,
            grade=7,
            academic_year="2026/2027",
            join_code=new_link_code(),
            join_code_expires_at=expires,
        )
        self.session.add(klass)
        await self.session.flush()
        return klass

    async def adult(self, role: str, school: School | None, name: str = "Олена") -> User:
        user = User(
            role=role,
            display_name=name,
            school_id=None if role == "parent" else school.id,
            email=f"{uuid.uuid4().hex[:10]}@example.com",
            password_hash=_password_hash(),
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def teacher(self, school: School, klass: SchoolClass | None = None) -> User:
        teacher = await self.adult("teacher", school)
        if klass:
            self.session.add(
                ClassMembership(class_id=klass.id, user_id=teacher.id, member_role="teacher")
            )
            await self.session.flush()
        return teacher

    async def student(self, klass: SchoolClass, name: str = "Іван", last: str = "Петренко") -> User:
        student = User(
            role="student",
            display_name=name,
            last_name=last,
            name_key=name_key(name, last),
            school_id=klass.school_id,
            pin_hash=_pin_hash(),
        )
        self.session.add(student)
        await self.session.flush()
        self.session.add(
            ClassMembership(class_id=klass.id, user_id=student.id, member_role="student")
        )
        await self.session.flush()
        return student

    async def subject(self, school: School | None = None, name: str = "Математика") -> Subject:
        subject = Subject(name=name, school_id=school.id if school else None)
        self.session.add(subject)
        await self.session.flush()
        return subject

    async def parent_of(self, student: User) -> User:
        parent = await self.adult("parent", None, "Марія")
        self.session.add(ParentChild(parent_id=parent.id, child_id=student.id))
        await self.session.flush()
        return parent


@pytest.fixture
def factory(db_session: AsyncSession) -> Factory:
    return Factory(db_session)


@pytest.fixture
async def world(factory: Factory) -> SimpleNamespace:
    """Школа з двома класами, друга школа з одним; по користувачу кожної ролі."""
    w = SimpleNamespace()
    w.school = await factory.school()
    w.other_school = await factory.school("Школа 2")
    w.class_a = await factory.klass(w.school, "7-А")
    w.class_b = await factory.klass(w.school, "7-Б")
    w.class_c = await factory.klass(w.other_school, "7-В")
    w.admin = await factory.adult("admin", w.school)
    w.other_admin = await factory.adult("admin", w.other_school)
    w.teacher_a = await factory.teacher(w.school, w.class_a)
    w.teacher_b = await factory.teacher(w.school, w.class_b)
    w.student_a = await factory.student(w.class_a, "Іван", "Петренко")
    w.student_b = await factory.student(w.class_b, "Марко", "Коваль")
    w.student_c = await factory.student(w.class_c, "Оксана", "Бойко")
    w.parent_a = await factory.parent_of(w.student_a)
    w.parent_free = await factory.adult("parent", None, "Без дитини")
    return w


def auth_header(user: User) -> dict[str, str]:
    """Access-токен, випущений напряму (без HTTP-входу)."""
    token = create_access_token(user.id, user.role, get_settings(), user.token_version)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_session] = override_session
    # Rate limiter у пам'яті (свіжий на тест): тести не залежать від Redis і один від одного.
    limiter = MemoryRateLimiter()
    application.dependency_overrides[get_rate_limiter] = lambda: limiter
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
def media_storage(app: FastAPI, tmp_path: Path) -> LocalMediaStorage:
    """Медіа пишуться в тимчасовий каталог тесту, а не в MEDIA_ROOT."""
    storage = LocalMediaStorage(tmp_path / "media", "/media")
    app.dependency_overrides[get_storage] = lambda: storage
    return storage


# ---------- справжні commit-и (паралельні запити, збій посеред пакета, стрічка змін) ----------


class Committed(SimpleNamespace):
    """Дані закомічені, кожен HTTP-запит отримує власну сесію (окреме з'єднання)."""


@pytest.fixture
async def committed(migrated_db: str) -> AsyncIterator[Committed]:
    """Режим без обгортки-транзакції: потрібен там, де важливі справжні commit-и й
    паралельні з'єднання. Після тесту всі таблиці очищуються (TRUNCATE ... CASCADE)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.models import Base

    engine = create_async_engine(migrated_db, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    application = create_app()

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    application.dependency_overrides[get_session] = override_session
    limiter = MemoryRateLimiter()
    application.dependency_overrides[get_rate_limiter] = lambda: limiter
    setup = maker()
    try:
        async with AsyncClient(
            transport=ASGITransport(app=application, raise_app_exceptions=False),
            base_url="http://test",
        ) as http:
            yield Committed(
                app=application, client=http, maker=maker, session=setup, factory=Factory(setup)
            )
    finally:
        await setup.close()
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        async with engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        await engine.dispose()
