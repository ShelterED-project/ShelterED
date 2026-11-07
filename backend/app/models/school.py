import datetime as dt
import uuid

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    SmallInteger,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, uuid_pk


class School(TimestampMixin, Base):
    __tablename__ = "school"
    __table_args__ = (Index("ix_school_region_code", "region_code"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str]
    # Регіон для API тривог; формат залежить від обраного API.
    region_code: Mapped[str]
    timezone: Mapped[str] = mapped_column(server_default="Europe/Kyiv")


class SchoolClass(TimestampMixin, Base):
    __tablename__ = "school_class"
    __table_args__ = (
        CheckConstraint("grade BETWEEN 1 AND 11", name="grade_range"),
        UniqueConstraint(
            "school_id", "academic_year", "name", name="uq_school_class_school_year_name"
        ),
        CheckConstraint("join_code ~ '^[A-Z0-9]+$'", name="join_code_format"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school.id", ondelete="CASCADE"))
    name: Mapped[str]
    grade: Mapped[int] = mapped_column(SmallInteger)
    academic_year: Mapped[str]
    # Код класу для входу учнів (нормалізований: лише A-Z0-9). Після join_code_expires_at
    # він лише перестає створювати нових учнів; наявні учні входять і далі.
    join_code: Mapped[str] = mapped_column(unique=True)
    join_code_expires_at: Mapped[dt.datetime | None]


class User(TimestampMixin, Base):
    __tablename__ = "app_user"  # "user" — зарезервоване слово
    __table_args__ = (
        CheckConstraint("role IN ('student', 'teacher', 'parent', 'admin')", name="role"),
        CheckConstraint("char_length(display_name) BETWEEN 1 AND 50", name="display_name_length"),
        CheckConstraint(
            "last_name IS NULL OR char_length(last_name) BETWEEN 1 AND 50",
            name="last_name_length",
        ),
        # Учень входить за кодом класу: жодних email і пароля.
        CheckConstraint(
            "role <> 'student' OR (email IS NULL AND password_hash IS NULL)",
            name="student_no_credentials",
        ),
        # PIN є лише в учнів.
        CheckConstraint("role = 'student' OR pin_hash IS NULL", name="pin_only_student"),
        # Пошук учня в класі за ім'ям (join -> class_membership).
        Index("ix_app_user_name_key", "name_key"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    role: Mapped[str]
    display_name: Mapped[str]  # ім'я
    # Прізвище: обов'язковість для учня перевіряє API, у БД допускаємо NULL.
    last_name: Mapped[str | None]
    school_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("school.id"))
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str | None]
    # PIN учня (argon2); NULL після скидання вчителем: наступний вхід задає новий.
    pin_hash: Mapped[str | None]
    # Нормалізоване імʼя+прізвище для пошуку учня (лише в учнів; у дорослих NULL).
    name_key: Mapped[str | None]
    # Епоха облікових даних: скидання PIN збільшує її, і всі видані токени (access `ver`,
    # refresh) із меншою версією перестають діяти.
    token_version: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(server_default=text("true"))


class ClassMembership(Base):
    __tablename__ = "class_membership"
    __table_args__ = (
        CheckConstraint("member_role IN ('student', 'teacher')", name="member_role"),
        # «Мої класи» вчителя / «мій клас» учня; на цьому тримаються перевірки доступу.
        Index("ix_class_membership_user_id", "user_id"),
    )

    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("school_class.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    member_role: Mapped[str]
    joined_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class ParentChild(Base):
    __tablename__ = "parent_child"
    __table_args__ = (Index("ix_parent_child_child_id", "child_id"),)

    parent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    child_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    linked_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())


class ScheduleSlot(TimestampMixin, Base):
    """Постійний тижневий слот. Час — місцевий час школи."""

    __tablename__ = "schedule_slot"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 1 AND 7", name="weekday_range"),
        CheckConstraint("ends_at > starts_at", name="time_order"),
        # «Який урок зараз».
        Index("ix_schedule_slot_class_id_weekday", "class_id", "weekday"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school_class.id", ondelete="CASCADE"))
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subject.id"))
    weekday: Mapped[int] = mapped_column(SmallInteger)  # ISO: 1 = понеділок
    starts_at: Mapped[dt.time] = mapped_column(Time)
    ends_at: Mapped[dt.time] = mapped_column(Time)
    valid_from: Mapped[dt.date] = mapped_column(Date)
    valid_to: Mapped[dt.date | None] = mapped_column(Date)


class ScheduleOverride(TimestampMixin, Base):
    """Перевизначення розкладу на конкретну дату."""

    __tablename__ = "schedule_override"
    __table_args__ = (
        CheckConstraint("kind IN ('cancel', 'replace', 'extra')", name="kind"),
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at", name="time_order"
        ),
        # Урок ставиться лише в додатковий урок без слота (у слот — через lesson_assignment).
        CheckConstraint(
            "lesson_id IS NULL OR (kind = 'extra' AND slot_id IS NULL)", name="extra_lesson"
        ),
        # Не більше одного перевизначення слота на дату (extra без слота — не обмежені).
        UniqueConstraint("slot_id", "date", name="uq_schedule_override_slot_date"),
        # Розклад класу на період.
        Index("ix_schedule_override_class_id_date", "class_id", "date"),
        # У які дні стоїть урок (як ix_lesson_assignment_lesson_id).
        Index("ix_schedule_override_lesson_id", "lesson_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school_class.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column(Date)
    # NULL для додаткового уроку.
    slot_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("schedule_slot.id"))
    kind: Mapped[str]
    subject_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subject.id"))
    starts_at: Mapped[dt.time | None] = mapped_column(Time)
    ends_at: Mapped[dt.time | None] = mapped_column(Time)
    # Додатковий урок поза розкладом, який ставить вчитель класу (kind = extra, без слота);
    # час тоді необов'язковий.
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lesson.id"))
    # Видалений додатковий урок вчителя (надгробок): не показується ніде, а повтор створення
    # з тим самим id отримує 410 замість воскресіння уроку.
    deleted_at: Mapped[dt.datetime | None]


class LessonAssignment(Base):
    """Який урок іде в слоті в конкретну дату."""

    __tablename__ = "lesson_assignment"
    # Перевірки при публікації: у які дні вже стоїть урок.
    __table_args__ = (Index("ix_lesson_assignment_lesson_id", "lesson_id"),)

    slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_slot.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id"))
