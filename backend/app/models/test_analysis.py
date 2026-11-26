"""AI-аналіз тесту класу: висновок для вчителя й фідбек кожному учню (учню й батькам).

Вчитель натискає «Проаналізувати» → Celery-задача збирає зараховані спроби класу й викликає
AI-сервіс (`POST /ai/v1/test-analysis`) → `draft` → вчитель за потреби править тексти й
публікує → учні й батьки бачать свій фідбек. Повторний аналіз — новий рядок, старі лишаються.
"""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class TestAnalysis(Base):
    """Один запуск аналізу тесту в класі.

    `result` — відповідь AI, де псевдоніми учнів (`s1`, `s2`…) уже замінено на справжні id;
    `null`, поки `processing` чи `failed`. Імен учнів тут немає. Правки вчителя — окремо
    (`test_analysis_edit`), щоб завжди можна було повернути текст AI.
    """

    __tablename__ = "test_analysis"
    __test__ = False  # не тестовий клас для pytest (назва починається з Test)
    __table_args__ = (
        CheckConstraint("status IN ('processing', 'draft', 'published', 'failed')", name="status"),
        # Останній аналіз тесту в класі (B2) і «чи вже йде аналіз» (B1).
        Index("ix_test_analysis_class_id_test_id", "class_id", "test_id", "created_at"),
        # Не більше одного аналізу в роботі на тест класу (подвійний клік, два вчителі).
        Index(
            "uq_test_analysis_processing",
            "class_id",
            "test_id",
            unique=True,
            postgresql_where=text("status = 'processing'"),
        ),
        # Пошук фідбеку учня (B5) і видалення учня (B15): `result @> {"students": [...]}`.
        Index("ix_test_analysis_result", "result", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school_class.id", ondelete="CASCADE"))
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    status: Mapped[str]
    # Скільки зарахованих спроб було на момент запуску (для діагностики й UI).
    attempts_count: Mapped[int]
    result: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    # Машинний код помилки при `failed`: AI_UNAVAILABLE / AI_BAD_REQUEST / AI_TIMEOUT.
    error_code: Mapped[str | None]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[dt.datetime | None]
    published_at: Mapped[dt.datetime | None]


class TestAnalysisEdit(Base):
    """Правка вчителя у фідбеку одного учня. `null` у полі — текст AI без змін."""

    __tablename__ = "test_analysis_edit"
    __test__ = False

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test_analysis.id", ondelete="CASCADE"), primary_key=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    student_text: Mapped[str | None]
    parent_text: Mapped[str | None]
    edited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    edited_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
