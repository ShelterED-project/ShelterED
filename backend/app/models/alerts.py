import datetime as dt
import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class AlertEvent(Base):
    __tablename__ = "alert_event"
    __table_args__ = (
        CheckConstraint("source IN ('api', 'manual')", name="source"),
        # Повтор події від AI-сервісу ігнорується.
        UniqueConstraint(
            "source", "external_id", "school_id", name="uq_alert_event_source_external_school"
        ),
        # Журнал тривог школи.
        Index("ix_alert_event_school_id_started_at", "school_id", "started_at"),
        # GET /alerts/active.
        Index(
            "ix_alert_event_active",
            "school_id",
            postgresql_where=text("ended_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    region_code: Mapped[str]
    # Запис для кожної школи регіону.
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("school.id"))
    # Ручна тривога для класу.
    class_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("school_class.id"))
    source: Mapped[str]
    external_id: Mapped[str | None]
    is_drill: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    started_at: Mapped[dt.datetime]
    ended_at: Mapped[dt.datetime | None]  # відбій
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
