import datetime as dt
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk
from app.models.sync import SyncChangeMixin


class RollCallSession(Base):
    __tablename__ = "rollcall_session"
    __table_args__ = (
        # Не більше однієї відкритої переклички на клас.
        Index(
            "uq_rollcall_session_class_id_open",
            "class_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school_class.id", ondelete="CASCADE"))
    # NULL, якщо відкрив вчитель вручну.
    alert_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("alert_event.id"))
    # NULL при автовідкритті.
    opened_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    is_drill: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    opened_at: Mapped[dt.datetime]
    closed_at: Mapped[dt.datetime | None]


class RollCallStatus(SyncChangeMixin, Base):
    """Статус учня в сесії. «Немає відповіді» = рядка немає."""

    __tablename__ = "rollcall_status"
    __table_args__ = (
        CheckConstraint("status IN ('safe', 'in_shelter')", name="status"),
        Index("ix_rollcall_status_sync_changes", "student_id", "change_xid", "change_seq"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rollcall_session.id", ondelete="CASCADE"), primary_key=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str]
    # Годинник пристрою; перемагає найпізніший.
    occurred_at: Mapped[dt.datetime]
    received_at: Mapped[dt.datetime]
    last_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_event.client_event_id"))
