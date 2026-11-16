import uuid
from datetime import UTC

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.types import TypeDecorator

from database import Base

STATUSES = ("in_shelter", "safe")


class UTCDateTime(TypeDecorator):
    """SQLite не зберігає часовий пояс: пишемо UTC, читаємо як aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Очікується datetime з часовим поясом")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        return None if value is None else value.replace(tzinfo=UTC)


class State(Base):
    """Один рядок (id=1): пристрій, токени вчителя, обраний клас, стан синхронізації."""

    __tablename__ = "local_state"
    id = Column(Integer, primary_key=True)
    device_id = Column(String, nullable=False)  # стабільний UUID цього сервера
    access_token = Column(Text)
    refresh_token = Column(Text)
    access_expires_at = Column(UTCDateTime)
    teacher_name = Column(String)
    classes_json = Column(Text)  # [{"id", "name"}] для вибору класу
    class_id = Column(String)
    class_name = Column(String)
    cloud_session_id = Column(String)  # відкрита перекличка в хмарі (за останньою синхронізацією)
    roster_updated_at = Column(UTCDateTime)
    last_sync_at = Column(UTCDateTime)
    last_sync_error = Column(String)

    @property
    def connected(self) -> bool:
        return bool(self.refresh_token)


class RosterStudent(Base):
    """Список учнів обраного класу (кеш із хмари)."""

    __tablename__ = "roster"
    student_id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    last_name = Column(String)

    @property
    def full_name(self) -> str:
        return f"{self.display_name} {self.last_name or ''}".strip()


class LocalSession(Base):
    """Перекличка, яку вчитель почав на ноутбуці."""

    __tablename__ = "rollcall_session"
    id = Column(String, primary_key=True)  # UUID v7, створений локально
    class_id = Column(String, nullable=False)
    started_at = Column(UTCDateTime, nullable=False)
    ended_at = Column(UTCDateTime)  # завершено лише локально
    registered = Column(Boolean, nullable=False, default=False)  # хмара знає цю сесію
    cloud_id = Column(String)  # якщо в хмарі вже була відкрита інша сесія (409)

    @property
    def effective_id(self) -> str:
        return self.cloud_id or self.id


class Mark(Base):
    """Подія rollcall_status: кожна зміна статусу учня — новий запис."""

    __tablename__ = "rollcall_mark"
    client_event_id = Column(String, primary_key=True)  # UUID v7
    session_id = Column(String, ForeignKey("rollcall_session.id"), nullable=False, index=True)
    student_id = Column(String, nullable=False)
    status = Column(String, nullable=False)  # in_shelter | safe
    occurred_at = Column(UTCDateTime, nullable=False)
    sync_state = Column(String, nullable=False, default="pending", index=True)
    reject_reason = Column(String)


def get_state(db: Session) -> State:
    state = db.get(State, 1)
    if state is None:
        db.add(State(id=1, device_id=str(uuid.uuid4())))
        try:
            db.commit()
        except IntegrityError:  # інший потік щойно створив рядок
            db.rollback()
        state = db.get(State, 1)
    return state


def active_session(db: Session) -> LocalSession | None:
    return (
        db.query(LocalSession)
        .filter(LocalSession.ended_at.is_(None))
        .order_by(LocalSession.started_at.desc())
        .first()
    )
