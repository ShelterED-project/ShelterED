"""Агрегати для кабінетів і дашбордів (B14). Похідні дані: рахує лише Celery-задача
(`app/services/stats.py`) з `module_progress`, `attempt` і розкладу; перерахунок ідемпотентний
(повний перерахунок рядків учня чи класу), тож таблиці можна будь-коли очистити й зібрати знову.
Нових персональних полів про дітей немає: лише id і числа.
"""

import datetime as dt
import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StudentLessonStat(Base):
    """Прогрес учня по уроку: уроки, призначені класам учня (дата ≤ сьогодні), і уроки,
    з яких є прогрес чи спроби."""

    __tablename__ = "student_lesson_stat"
    __table_args__ = (
        CheckConstraint("progress_pct BETWEEN 0 AND 100", name="progress_range"),
        Index("ix_student_lesson_stat_lesson_id", "lesson_id"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lesson.id", ondelete="CASCADE"), primary_key=True
    )
    modules_total: Mapped[int] = mapped_column(SmallInteger)
    modules_done: Mapped[int] = mapped_column(SmallInteger)
    # Середнє `progress_pct` модулів уроку (модуль без прогресу = 0).
    progress_pct: Mapped[int] = mapped_column(SmallInteger)
    # Урок завершено (усі модулі 100%): найпізніший `module_progress.full_at` (годинник пристрою).
    completed_at: Mapped[dt.datetime | None]
    # Час навчання: сума `module.duration_min` завершених модулів (див. docs/db-schema.md, B14).
    study_minutes: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[dt.datetime]


class StudentTestStat(Base):
    """Результат учня з тесту (тести уроків з `student_lesson_stat`)."""

    __tablename__ = "student_test_stat"
    __table_args__ = (Index("ix_student_test_stat_test_id", "test_id"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("test.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id", ondelete="CASCADE"))
    attempts: Mapped[int] = mapped_column(Integer)
    # Зарахована спроба: оцінка 0..100 і час завершення за годинником пристрою.
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    credited_at: Mapped[dt.datetime | None]
    # Хоч одна спроба з підозрілим часом пристрою — позначка для вчителя.
    is_suspicious: Mapped[bool]
    computed_at: Mapped[dt.datetime]


class StudentStudyDay(Base):
    """Хвилини навчання учня по днях (дата за поясом школи, за `module_progress.full_at`)."""

    __tablename__ = "student_study_day"
    __table_args__ = (CheckConstraint("minutes >= 0", name="minutes_non_negative"),)

    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    minutes: Mapped[int] = mapped_column(Integer)


class ClassLessonStat(Base):
    """Прогрес класу по уроку (уроки розкладу класу з датою ≤ сьогодні)."""

    __tablename__ = "class_lesson_stat"

    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("school_class.id", ondelete="CASCADE"), primary_key=True
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lesson.id", ondelete="CASCADE"), primary_key=True
    )
    first_date: Mapped[dt.date] = mapped_column(Date)
    students_total: Mapped[int] = mapped_column(Integer)
    students_completed: Mapped[int] = mapped_column(Integer)
    avg_progress_pct: Mapped[int] = mapped_column(SmallInteger)
    # Пари (учень, тест уроку) із зарахованою спробою; середня оцінка й скільки склали.
    tests_scored: Mapped[int] = mapped_column(Integer)
    tests_passed: Mapped[int] = mapped_column(Integer)
    avg_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    computed_at: Mapped[dt.datetime]


class ClassQuestionStat(Base):
    """Скільки зарахованих спроб класу відповіли на питання правильно (прогалини по темах)."""

    __tablename__ = "class_question_stat"
    __table_args__ = (Index("ix_class_question_stat_class_id_lesson_id", "class_id", "lesson_id"),)

    class_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("school_class.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("question.id", ondelete="CASCADE"), primary_key=True
    )
    test_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test.id", ondelete="CASCADE"))
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lesson.id", ondelete="CASCADE"))
    answered: Mapped[int] = mapped_column(Integer)
    correct: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[dt.datetime]


class AlertStudyStat(Base):
    """Скільки навчалися учні школи під час тривоги (дашборд адміністрації, P2): завершені
    модулі з `full_at` у межах [початок, відбій) тривоги; для ручної тривоги — лише її клас."""

    __tablename__ = "alert_study_stat"
    __table_args__ = (Index("ix_alert_study_stat_school_id", "school_id"),)

    alert_event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("alert_event.id", ondelete="CASCADE"), primary_key=True
    )
    school_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("school.id", ondelete="CASCADE"))
    students: Mapped[int] = mapped_column(Integer)
    study_minutes: Mapped[int] = mapped_column(Integer)
    computed_at: Mapped[dt.datetime]
