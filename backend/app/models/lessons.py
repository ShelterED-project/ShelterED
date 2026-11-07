import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class Subject(TimestampMixin, Base):
    __tablename__ = "subject"

    id: Mapped[uuid.UUID] = uuid_pk()
    # NULL = загальний довідник для всіх шкіл.
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("school.id"))
    name: Mapped[str]


class Lesson(TimestampMixin, Base):
    """Урок не прив'язаний до класу: призначається на слот у дату (lesson_assignment)."""

    __tablename__ = "lesson"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="status"),
        # «Мої уроки» вчителя.
        Index("ix_lesson_author_id", "author_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subject.id"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))
    title: Mapped[str]
    shelter_part: Mapped[str]
    main_part: Mapped[str]
    status: Mapped[str] = mapped_column(server_default="draft")
    # +1 при кожній зміні опублікованого уроку; пакет пам'ятає версію.
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    published_at: Mapped[dt.datetime | None]
    grade: Mapped[int | None] = mapped_column(SmallInteger)


class Module(TimestampMixin, Base):
    """Мікро-модуль 3–5 хв."""

    __tablename__ = "module"
    __table_args__ = (
        CheckConstraint("part IN ('shelter', 'main')", name="part"),
        CheckConstraint("duration_min BETWEEN 1 AND 10", name="duration_range"),
        UniqueConstraint("lesson_id", "part", "position", name="uq_module_lesson_part_position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id", ondelete="CASCADE"))
    part: Mapped[str]
    position: Mapped[int] = mapped_column(SmallInteger)
    title: Mapped[str]
    duration_min: Mapped[int] = mapped_column(SmallInteger)


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_asset"
    __table_args__ = (
        CheckConstraint("kind IN ('video', 'image', 'subtitles')", name="kind"),
        # Пошук уже збереженого файла з тим самим вмістом (дедуплікація при завантаженні).
        Index("ix_media_asset_sha256", "sha256"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    kind: Mapped[str]
    # Не унікальний: однаковий вміст — один файл на кілька записів (див. services/media).
    storage_key: Mapped[str]
    mime_type: Mapped[str]
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    # sha256 збереженого файла (що роздається за URL); source_sha256 — файла, який надіслав
    # клієнт, для ідемпотентності повтору (зображення перекодовуються у WebP, див. services/media).
    sha256: Mapped[str]
    source_sha256: Mapped[str]
    duration_s: Mapped[int | None]
    # VTT до відео; публікація відео без субтитрів заборонена (перевіряє сервіс).
    subtitles_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_asset.id"))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("app_user.id"))


class Card(TimestampMixin, Base):
    __tablename__ = "card"
    __table_args__ = (
        CheckConstraint("kind IN ('text', 'image', 'video')", name="kind"),
        UniqueConstraint("module_id", "position", name="uq_card_module_position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("module.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str]
    body: Mapped[Any] = mapped_column(JSONB)
    media_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("media_asset.id"))


class Test(TimestampMixin, Base):
    __tablename__ = "test"
    __test__ = False  # не збирати pytest-ом як тестовий клас
    __table_args__ = (
        CheckConstraint("window_hours IN (24, 48, 72)", name="window_hours_values"),
        CheckConstraint("window_enabled = false OR window_hours IS NOT NULL", name="window_hours"),
        # Тести уроку: збірка пакета, агрегати, каскад від уроку.
        Index("ix_test_lesson_id", "lesson_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id", ondelete="CASCADE"))
    title: Mapped[str]
    # Тест із вікном: проходити можна протягом window_hours після уроку.
    window_enabled: Mapped[bool] = mapped_column(server_default=text("false"))
    window_hours: Mapped[int | None] = mapped_column(SmallInteger)


class Question(TimestampMixin, Base):
    __tablename__ = "question"
    __table_args__ = (
        CheckConstraint("kind IN ('single', 'multiple')", name="kind"),
        UniqueConstraint("test_id", "position", name="uq_question_test_position"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger)
    kind: Mapped[str]
    prompt: Mapped[str]
    # [{"id": "a", "text": "..."}]
    options: Mapped[Any] = mapped_column(JSONB)
    # Правильні id варіантів; перевірку робить сервер.
    answer_key: Mapped[Any] = mapped_column(JSONB)
    points: Mapped[int] = mapped_column(SmallInteger, server_default=text("1"))
