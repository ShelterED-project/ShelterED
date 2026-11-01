import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class SyncEvent(Base):
    """Журнал подій з пристроїв; PK = client_event_id дає ідемпотентність."""

    __tablename__ = "sync_event"
    __table_args__ = (
        CheckConstraint(
            "type IN ('module_progress', 'test_attempt', 'rollcall_status', 'survey_answer')",
            name="type",
        ),
        CheckConstraint("source IN ('online', 'qr')", name="source"),
        CheckConstraint("status IN ('accepted', 'rejected')", name="status"),
        Index("ix_sync_event_user_id_received_at", "user_id", "received_at"),
    )

    # Створює клієнт; вставка INSERT ... ON CONFLICT DO NOTHING.
    client_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    type: Mapped[str]
    # Повне видалення даних учня каскадом (на запит батьків / школи).
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    # Id пристрою створює клієнт; окремої таблиці device поки немає.
    device_id: Mapped[uuid.UUID]
    occurred_at: Mapped[dt.datetime]  # годинник пристрою
    received_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())  # годинник сервера
    clock_skew_ms: Mapped[int | None] = mapped_column(Integer)
    # Час у майбутньому / великий зсув: позначка, не блокування.
    is_suspicious: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    source: Mapped[str] = mapped_column(server_default="online")
    # Вчитель, який передав QR-події.
    relayed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    payload: Mapped[Any] = mapped_column(JSONB)
    status: Mapped[str]
    reject_reason: Mapped[str | None]


class Attempt(Base):
    """Спроба тесту."""

    __tablename__ = "attempt"
    __table_args__ = (
        CheckConstraint(
            "credit_status IN ('credited', 'not_credited_late', 'not_credited_repeat')",
            name="credit_status",
        ),
        # Дві зараховані спроби на тест у БД неможливі: зараховується перша завершена.
        Index(
            "uq_attempt_student_id_test_id_credited",
            "student_id",
            "test_id",
            unique=True,
            postgresql_where=text("credit_status = 'credited'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Одна подія — одна спроба.
    client_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sync_event.client_event_id", ondelete="CASCADE"), unique=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id"))
    # {"<question_id>": ["a"]}
    answers: Mapped[Any] = mapped_column(JSONB)
    # Для вікна тесту рахується саме він.
    completed_at_client: Mapped[dt.datetime]
    received_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    credit_status: Mapped[str]
    is_suspicious: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class ModuleProgress(Base):
    __tablename__ = "module_progress"
    __table_args__ = (CheckConstraint("progress_pct BETWEEN 0 AND 100", name="progress_range"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module.id", ondelete="CASCADE"), primary_key=True
    )
    # Оновлюється через GREATEST: беремо максимум.
    progress_pct: Mapped[int] = mapped_column(SmallInteger)
    completed_at_client: Mapped[dt.datetime | None]
    # Остання подія, яка змінила рядок.
    last_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_event.client_event_id"))
