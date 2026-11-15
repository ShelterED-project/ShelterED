"""«Як ти зараз?» (docs/wellbeing-checkin.md): відповіді окремо від журналу подій і журнал
переглядів. Не тест і не діагноз: лише вибір картинки погоди 1..5 раз на день.

Значення в `sync_event.payload` не зберігається (там порожній payload). Сирі відповіді й
записи `sync_event` типу `survey_answer` живуть 30 днів (Celery `wellbeing.purge`), видалення
учня прибирає їх каскадом.
"""

import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class WellbeingAnswer(Base):
    """Одна відповідь учня на день; пізніша (за `occurred_at`) того ж дня замінює ранішу."""

    __tablename__ = "wellbeing_answer"
    __table_args__ = (
        CheckConstraint("value BETWEEN 1 AND 5", name="value_range"),
        UniqueConstraint("student_id", "answered_on"),
        Index("ix_wellbeing_answer_answered_on", "answered_on"),
    )

    # `client_event_id` події, що дала поточне значення.
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    # Дата відповіді в поясі школи (Europe/Kyiv) за виправленим часом.
    answered_on: Mapped[dt.date] = mapped_column(Date)
    value: Mapped[int] = mapped_column(SmallInteger)
    # Час пристрою, виправлений на зсув годинника пакета (`occurred_at` + `clock_skew_ms`):
    # від нього дата відповіді й правило «пізніша відповідь дня перемагає».
    occurred_at: Mapped[dt.datetime]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class WellbeingViewLog(Base):
    """Хто й коли дивився дані «Як ти зараз?» дитини (батьки). Сама дитина в журнал не
    пишеться; вчитель і адміністрація доступу не мають."""

    __tablename__ = "wellbeing_view_log"
    __table_args__ = (Index("ix_wellbeing_view_log_student_id", "student_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    viewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    viewed_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
