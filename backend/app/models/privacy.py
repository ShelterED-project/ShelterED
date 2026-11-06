"""Видалення даних учня на запит батьків або школи (B15.5).

Запит створюють батьки дитини або адміністрація її школи, підтверджує адміністрація школи.
Підтвердження видаляє акаунт учня (`app_user`) і все пов'язане каскадом. Після видалення
запит і журнал не містять персональних даних: `student_id` стає NULL (SET NULL), лишається
лише `student_hash` — sha256 від id учня (псевдонім: за відомим id можна перевірити, що
дані видалено, але з хешу id не відновити й нічого про дитину не дізнатися).
"""

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk

REASONS = ("left_school", "consent_withdrawn", "duplicate_account", "other")


class DataDeletionRequest(Base):
    """Запит на видалення даних учня. Відкритий (`pending`) — не більше одного на учня."""

    __tablename__ = "data_deletion_request"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'confirmed', 'rejected')", name="status"),
        CheckConstraint("requested_by_role IN ('parent', 'admin')", name="requested_by_role"),
        CheckConstraint(
            "reason IS NULL OR reason IN (" + ", ".join(f"'{r}'" for r in REASONS) + ")",
            name="reason",
        ),
        Index(
            "uq_data_deletion_request_student_id_pending",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_data_deletion_request_school_id_status", "school_id", "status"),
        Index("ix_data_deletion_request_requested_by", "requested_by"),
    )

    # Створює клієнт (ідемпотентний повтор).
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # NULL після видалення учня.
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    student_hash: Mapped[str]
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school.id", ondelete="CASCADE"))
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    requested_by_role: Mapped[str]
    # Причина — лише з переліку, без вільного тексту (у ньому могли б опинитися дані дитини).
    reason: Mapped[str | None]
    status: Mapped[str] = mapped_column(server_default="pending")
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    decided_at: Mapped[dt.datetime | None]
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )


class DataDeletionLog(Base):
    """Журнал виконаних видалень: що, коли й хто підтвердив, без персональних даних."""

    __tablename__ = "data_deletion_log"
    __table_args__ = (
        CheckConstraint("requested_by_role IN ('parent', 'admin')", name="requested_by_role"),
        Index("ix_data_deletion_log_school_id", "school_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Без FK: запис журналу не залежить від долі запиту. Унікальний — одне видалення на запит.
    request_id: Mapped[uuid.UUID] = mapped_column(unique=True)
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school.id", ondelete="CASCADE"))
    student_hash: Mapped[str]
    requested_by_role: Mapped[str]
    requested_at: Mapped[dt.datetime]
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    deleted_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
