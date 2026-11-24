"""ШІ-репетитор (B13): стан розмов учня і закешовані пояснення для пакета «Рюкзак».

AI-сервіс нічого не пам'ятає між запитами: завдання (`task` з еталонною відповіддю),
кількість підказок і останні репліки зберігає backend. Учню `task` віддається лише без
відповіді (див. services/tutor.py).
"""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, SmallInteger, func, text
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
    # Ключі закешованих пояснень, які розмова вже отримала (до `MAX_EXPLAINED_KEYS`):
    # повторне «Поясни» того самого матеріалу йде в LLM по інше пояснення.
    explained_keys: Mapped[Any] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class TutorExplanation(Base):
    """Закешоване пояснення ШІ (B13.3), адресоване вмістом: `cache_key` — sha256 канонічного
    JSON {клас, предмет, назва модуля, тексти текстових карток, версія промпту}
    (`services/tutor.explanation_key`). Не прив'язане до уроку чи модуля: повторна публікація,
    копія уроку чи такий самий модуль колеги беруть те саме пояснення без виклику LLM.
    Генерує Celery-задача після публікації (для пакета «Рюкзак») або перший `explain` учня
    онлайн; далі його отримують і інші учні (`cached: true`). Прибирає `retention.purge`:
    не використовувалося `RETENTION_TUTOR_EXPLANATION_DAYS` і не потрібне жодному модулю
    опублікованого уроку."""

    __tablename__ = "tutor_explanation"
    __table_args__ = (Index("ix_tutor_explanation_last_used_at", "last_used_at"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    cache_key: Mapped[str] = mapped_column(unique=True)
    # Для діагностики: ключ уже містить версію промпту.
    prompt_version: Mapped[str]
    text: Mapped[str]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    # Остання видача (пакет, онлайн-кеш); оновлюється не частіше ніж раз на добу.
    last_used_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class TutorExplanationAttempt(Base):
    """Невдалі спроби отримати пояснення за ключем (порожня/safety-відповідь, відхилений
    запит, урок без класу). Після `MAX_EXPLANATION_ATTEMPTS` beat цей ключ не чіпає, тож він
    не палить виклики LLM щогодини. Змінений вміст чи версія промпту — новий ключ, нові
    спроби. Недоступний AI спробою не вважається."""

    __tablename__ = "tutor_explanation_attempt"

    cache_key: Mapped[str] = mapped_column(primary_key=True)
    attempts: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    last_attempt_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
