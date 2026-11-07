import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    FetchedValue,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class SyncChangeMixin:
    """Позиція рядка в стрічці змін `GET /sync/changes` (docs/sync-protocol.md, розділ 8).

    Обидва поля ставить тригер `sync_change_stamp` на кожен INSERT і UPDATE: `change_seq` —
    з послідовності `sync_change_seq`, `change_xid` — id транзакції (`pg_current_xact_id()`,
    xid8 у bigint). Код їх не пише.
    """

    change_seq: Mapped[int] = mapped_column(BigInteger, server_default=FetchedValue())
    change_xid: Mapped[int] = mapped_column(BigInteger, server_default=FetchedValue())


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
        # Строки зберігання (retention.purge): лише ще не очищені події, тож індекс не росте
        # з історією, а пакетна вибірка найстаріших не сканує вже очищені рядки.
        Index(
            "ix_sync_event_retention",
            "received_at",
            postgresql_where=text("device_id IS NOT NULL"),
        ),
        # Видалення користувача (ON DELETE SET NULL) без повного сканування журналу; QR-ретрансляція
        # рідкісна, тож індекс лише по заповнених рядках.
        Index(
            "ix_sync_event_relayed_by",
            "relayed_by",
            postgresql_where=text("relayed_by IS NOT NULL"),
        ),
    )

    # Створює клієнт; вставка INSERT ... ON CONFLICT DO NOTHING.
    client_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    type: Mapped[str]
    # Повне видалення даних учня каскадом (на запит батьків / школи).
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    # Id пристрою створює клієнт; окремої таблиці device поки немає. NULL — подію очищено за
    # строком зберігання (разом із payload і clock_skew_ms).
    device_id: Mapped[uuid.UUID | None]
    occurred_at: Mapped[dt.datetime]  # годинник пристрою
    received_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())  # годинник сервера
    clock_skew_ms: Mapped[int | None] = mapped_column(BigInteger)
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


class Attempt(SyncChangeMixin, Base):
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
        Index("ix_attempt_sync_changes", "student_id", "change_xid", "change_seq"),
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


class ModuleProgress(SyncChangeMixin, Base):
    __tablename__ = "module_progress"
    __table_args__ = (
        CheckConstraint("progress_pct BETWEEN 0 AND 100", name="progress_range"),
        Index("ix_module_progress_sync_changes", "student_id", "change_xid", "change_seq"),
        # Перевірка FK під час видалення подій (retention.purge, видалення учня): без індексу —
        # повне сканування таблиці на кожну видалену подію.
        Index("ix_module_progress_last_event_id", "last_event_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("module.id", ondelete="CASCADE"), primary_key=True
    )
    # Оновлюється через GREATEST: беремо максимум.
    progress_pct: Mapped[int] = mapped_column(SmallInteger)
    completed_at_client: Mapped[dt.datetime | None]
    # `occurred_at` (годинник пристрою) найранішої прийнятої події з progress_pct = 100: момент
    # завершення модуля. Від завершення останнього модуля уроку відкривається вікно тесту (B11),
    # за ним же рахується день навчання (B14).
    full_at: Mapped[dt.datetime | None]
    # Остання подія, яка змінила рядок.
    last_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_event.client_event_id"))
