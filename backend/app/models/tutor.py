"""ШІ-репетитор (B13): стан розмов учня і закешовані пояснення для пакета «Рюкзак».

AI-сервіс нічого не пам'ятає між запитами: завдання (`task` з еталонною відповіддю),
кількість підказок і останні репліки зберігає backend. Учню `task` віддається лише без
відповіді (див. services/tutor.py).
"""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, SmallInteger, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class TutorConversation(TimestampMixin, Base):
    """Розмова учня з репетитором. `id` створює клієнт (один на чат модуля); чужий id —
    404. Видаляється разом з учнем і через `RETENTION_TUTOR_CONVERSATION_DAYS` без
    активності (`updated_at`)."""

    __tablename__ = "tutor_conversation"
    __table_args__ = (
        Index("ix_tutor_conversation_student_id", "student_id"),
        # Прибирання за строком зберігання.
        Index("ix_tutor_conversation_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lesson.id", ondelete="SET NULL")
    )
    module_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("module.id", ondelete="SET NULL")
    )
    # Поточне завдання від AI (`task` з відповіді `practice`) — разом з `answer`; учню не
    # віддається.
    task: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    hints_used: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    # До 8 останніх реплік [{"role": "user" | "assistant", "text": "..."}], від старих до нових.
    history: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    # Відповіді на останні запити [{"request_id": "...", "response": {...}}] — повтор того
    # самого `request_id` повертає збережену відповідь без виклику AI (ідемпотентність).
    replies: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class TutorExplanation(Base):
    """Закешоване пояснення модуля опублікованого уроку (B13.3): генерує Celery-задача після
    публікації, входить у пакет «Рюкзак» для показу офлайн. Одне на (урок, версія, модуль)."""

    __tablename__ = "tutor_explanation"
    __table_args__ = (
        UniqueConstraint(
            "lesson_id", "lesson_version", "module_id", name="uq_tutor_explanation_module"
        ),
        Index("ix_tutor_explanation_module_id", "module_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id", ondelete="CASCADE"))
    lesson_version: Mapped[int] = mapped_column(Integer)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module.id", ondelete="CASCADE"))
    text: Mapped[str]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class TutorExplanationAttempt(Base):
    """Невдалі спроби отримати пояснення модуля (порожня/safety-відповідь, відхилений запит,
    урок без класу). Після `MAX_EXPLANATION_ATTEMPTS` модуль цієї версії уроку beat не
    чіпає, тож він не палить виклики LLM щогодини. Нова версія уроку — нові спроби."""

    __tablename__ = "tutor_explanation_attempt"
    __table_args__ = (
        UniqueConstraint("module_id", "lesson_version", name="uq_tutor_explanation_attempt"),
        Index("ix_tutor_explanation_attempt_lesson_id", "lesson_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id", ondelete="CASCADE"))
    lesson_version: Mapped[int] = mapped_column(Integer)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module.id", ondelete="CASCADE"))
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    last_attempt_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
