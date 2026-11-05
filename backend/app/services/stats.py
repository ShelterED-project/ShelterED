"""Агрегати кабінетів (B14): перерахунок (Celery, черга `default`) і читання для API.

Перерахунок — повна заміна рядків учня чи класу в одній транзакції під advisory lock, тож
повторний чи паралельний запуск дає той самий результат (ідемпотентно). Джерела: розклад
класу (`lesson_assignment`), `module_progress`, `attempt`. Ендпоінти лише читають готові рядки
(і групують кілька десятків рядків учня/класу), сирі події на запит не перебираються.

Визначення (docs/db-schema.md, «Рішення B14»):
- урок учня — опублікований урок, призначений його класу на дату ≤ сьогодні (пояс школи), або
  урок, з якого є прогрес чи спроби;
- урок завершено — усі його модулі 100%; час завершення — найпізніший `full_at` модулів;
- час навчання — сума `duration_min` завершених модулів (плановий час, а не різниця позначок
  часу пристрою: її не можна перевірити й вона завищується відкритим екраном); день — дата
  `full_at` у поясі школи;
- тест складено — оцінка зарахованої спроби ≥ `STATS_PASS_SCORE`.
"""

import datetime as dt
import uuid
from collections import defaultdict
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.alerts import AlertEvent
from app.models.lessons import Lesson, Module, Question, Subject, Test
from app.models.school import (
    ClassMembership,
    LessonAssignment,
    ScheduleSlot,
    School,
    SchoolClass,
    User,
)
from app.models.stats import (
    AlertStudyStat,
    ClassLessonStat,
    ClassQuestionStat,
    StudentLessonStat,
    StudentStudyDay,
    StudentTestStat,
)
from app.models.sync import Attempt, ModuleProgress
from app.schemas.stats import (
    AlertStudyItem,
    AlertStudyOut,
    ClassGapsOut,
    ClassLessonProgress,
    ClassProgressOut,
    ClassTestOut,
    ClassTestsOut,
    GapQuestion,
    GapTopic,
    KnowledgeMapOut,
    KnowledgeMapSubject,
    StudentLessonProgress,
    StudentProgressOut,
    StudentTestOut,
    StudentTestResult,
    StudentTestStatus,
    StudyDay,
    StudyTime,
    TestStatusCounts,
)

DEFAULT_TZ = "Europe/Kyiv"
STUDY_DAYS = 7


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def _lock(session: AsyncSession, key: str) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(key, 0))))


async def _school_tz(session: AsyncSession, school_id: uuid.UUID | None) -> ZoneInfo:
    name = None
    if school_id is not None:
        name = await session.scalar(select(School.timezone).where(School.id == school_id))
    return ZoneInfo(name or DEFAULT_TZ)


def _assigned_lessons(class_ids, today: dt.date):
    """Опубліковані уроки розкладу класів із датою ≤ today."""
    return (
        select(LessonAssignment.lesson_id)
        .join(ScheduleSlot, ScheduleSlot.id == LessonAssignment.slot_id)
        .join(Lesson, Lesson.id == LessonAssignment.lesson_id)
        .where(
            ScheduleSlot.class_id.in_(class_ids),
            LessonAssignment.date <= today,
            Lesson.status == "published",
        )
    )


def _class_students(class_id: uuid.UUID):
    return select(ClassMembership.user_id).where(
        ClassMembership.class_id == class_id, ClassMembership.member_role == "student"
    )


def _avg(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return (sum(values, Decimal(0)) / len(values)).quantize(Decimal("0.01"))


# ---------- перерахунок ----------


async def recompute_student(
    session: AsyncSession, student_id: uuid.UUID, now: dt.datetime | None = None
) -> bool:
    """Перерахувати рядки учня (уроки, тести, дні навчання). Не комітить. False — не учень."""
    now = now or _now()
    student = await session.get(User, student_id)
    if student is None or student.role != "student":
        return False
    await _lock(session, f"stats:student:{student_id}")
    tz = await _school_tz(session, student.school_id)
    today = now.astimezone(tz).date()

    class_ids = select(ClassMembership.class_id).where(
        ClassMembership.user_id == student_id, ClassMembership.member_role == "student"
    )
    progressed = (
        select(Module.lesson_id)
        .join(ModuleProgress, ModuleProgress.module_id == Module.id)
        .where(ModuleProgress.student_id == student_id)
    )
    attempted = (
        select(Test.lesson_id)
        .join(Attempt, Attempt.test_id == Test.id)
        .where(Attempt.student_id == student_id)
    )
    lesson_ids = set(
        await session.scalars(union(_assigned_lessons(class_ids, today), progressed, attempted))
    )

    modules = (
        await session.execute(
            select(Module.id, Module.lesson_id, Module.duration_min).where(
                Module.lesson_id.in_(lesson_ids)
            )
        )
    ).all()
    progress = {
        row.module_id: row
        for row in await session.execute(
            select(
                ModuleProgress.module_id, ModuleProgress.progress_pct, ModuleProgress.full_at
            ).where(ModuleProgress.student_id == student_id)
        )
    }
    by_lesson: dict[uuid.UUID, list] = defaultdict(list)
    for m in modules:
        by_lesson[m.lesson_id].append(m)

    lesson_rows = []
    study: dict[dt.date, int] = defaultdict(int)
    for lesson_id in lesson_ids:
        mods = by_lesson.get(lesson_id, [])
        pcts, done_at, minutes = [], [], 0
        for m in mods:
            p = progress.get(m.id)
            pcts.append(p.progress_pct if p else 0)
            if p is not None and p.progress_pct == 100 and p.full_at is not None:
                done_at.append(p.full_at)
                minutes += m.duration_min
                study[p.full_at.astimezone(tz).date()] += m.duration_min
        lesson_rows.append(
            {
                "student_id": student_id,
                "lesson_id": lesson_id,
                "modules_total": len(mods),
                "modules_done": len(done_at),
                "progress_pct": round(sum(pcts) / len(pcts)) if pcts else 0,
                "completed_at": max(done_at) if mods and len(done_at) == len(mods) else None,
                "study_minutes": minutes,
                "computed_at": now,
            }
        )

    tests = (
        await session.execute(select(Test.id, Test.lesson_id).where(Test.lesson_id.in_(lesson_ids)))
    ).all()
    attempts: dict[uuid.UUID, list] = defaultdict(list)
    for a in await session.execute(
        select(
            Attempt.test_id,
            Attempt.credit_status,
            Attempt.score,
            Attempt.completed_at_client,
            Attempt.is_suspicious,
        ).where(Attempt.student_id == student_id)
    ):
        attempts[a.test_id].append(a)
    test_rows = []
    for t in tests:
        mine = attempts.get(t.id, [])
        credited = next((a for a in mine if a.credit_status == "credited"), None)
        test_rows.append(
            {
                "student_id": student_id,
                "test_id": t.id,
                "lesson_id": t.lesson_id,
                "attempts": len(mine),
                "score": credited.score if credited else None,
                "credited_at": credited.completed_at_client if credited else None,
                "is_suspicious": any(a.is_suspicious for a in mine),
                "computed_at": now,
            }
        )

    for model in (StudentLessonStat, StudentTestStat, StudentStudyDay):
        await session.execute(delete(model).where(model.student_id == student_id))
    if lesson_rows:
        await session.execute(StudentLessonStat.__table__.insert(), lesson_rows)
    if test_rows:
        await session.execute(StudentTestStat.__table__.insert(), test_rows)
    if study:
        await session.execute(
            StudentStudyDay.__table__.insert(),
            [{"student_id": student_id, "day": d, "minutes": m} for d, m in study.items()],
        )
    return True


async def recompute_class(
    session: AsyncSession, class_id: uuid.UUID, settings: Settings, now: dt.datetime | None = None
) -> bool:
    """Перерахувати рядки класу з рядків учнів (їх рахує recompute_student). Не комітить."""
    now = now or _now()
    klass = await session.get(SchoolClass, class_id)
    if klass is None:
        return False
    await _lock(session, f"stats:class:{class_id}")
    tz = await _school_tz(session, klass.school_id)
    today = now.astimezone(tz).date()

    students = list(await session.scalars(_class_students(class_id)))
    first_dates = dict(
        (
            await session.execute(
                select(LessonAssignment.lesson_id, func.min(LessonAssignment.date))
                .join(ScheduleSlot, ScheduleSlot.id == LessonAssignment.slot_id)
                .join(Lesson, Lesson.id == LessonAssignment.lesson_id)
                .where(
                    ScheduleSlot.class_id == class_id,
                    LessonAssignment.date <= today,
                    Lesson.status == "published",
                )
                .group_by(LessonAssignment.lesson_id)
            )
        ).all()
    )
    lesson_ids = list(first_dates)
    lesson_stats = (
        await session.scalars(
            select(StudentLessonStat).where(
                StudentLessonStat.student_id.in_(students),
                StudentLessonStat.lesson_id.in_(lesson_ids),
            )
        )
    ).all()
    test_stats = (
        await session.scalars(
            select(StudentTestStat).where(
                StudentTestStat.student_id.in_(students),
                StudentTestStat.lesson_id.in_(lesson_ids),
            )
        )
    ).all()
    per_lesson: dict[uuid.UUID, list[StudentLessonStat]] = defaultdict(list)
    for s in lesson_stats:
        per_lesson[s.lesson_id].append(s)
    scores: dict[uuid.UUID, list[Decimal]] = defaultdict(list)
    for t in test_stats:
        if t.score is not None:
            scores[t.lesson_id].append(t.score)

    pass_score = Decimal(settings.stats_pass_score)
    lesson_rows = []
    for lesson_id, first_date in first_dates.items():
        rows = per_lesson.get(lesson_id, [])
        total = len(students)
        lesson_rows.append(
            {
                "class_id": class_id,
                "lesson_id": lesson_id,
                "first_date": first_date,
                "students_total": total,
                "students_completed": sum(r.completed_at is not None for r in rows),
                "avg_progress_pct": round(sum(r.progress_pct for r in rows) / total)
                if total
                else 0,
                "tests_scored": len(scores[lesson_id]),
                "tests_passed": sum(s >= pass_score for s in scores[lesson_id]),
                "avg_score": _avg(scores[lesson_id]),
                "computed_at": now,
            }
        )

    questions = (
        await session.execute(
            select(Question.id, Question.test_id, Question.answer_key, Test.lesson_id)
            .join(Test, Test.id == Question.test_id)
            .where(Test.lesson_id.in_(lesson_ids))
        )
    ).all()
    credited: dict[uuid.UUID, list[dict]] = defaultdict(list)
    for a in await session.execute(
        select(Attempt.test_id, Attempt.answers).where(
            Attempt.student_id.in_(students),
            Attempt.credit_status == "credited",
            Attempt.test_id.in_({q.test_id for q in questions}),
        )
    ):
        credited[a.test_id].append(a.answers or {})
    question_rows = []
    for q in questions:
        answers = credited.get(q.test_id, [])
        key = set(q.answer_key or [])
        question_rows.append(
            {
                "class_id": class_id,
                "question_id": q.id,
                "test_id": q.test_id,
                "lesson_id": q.lesson_id,
                "answered": len(answers),
                "correct": sum(bool(key) and set(a.get(str(q.id), [])) == key for a in answers),
                "computed_at": now,
            }
        )

    for model in (ClassLessonStat, ClassQuestionStat):
        await session.execute(delete(model).where(model.class_id == class_id))
    if lesson_rows:
        await session.execute(ClassLessonStat.__table__.insert(), lesson_rows)
    if question_rows:
        await session.execute(ClassQuestionStat.__table__.insert(), question_rows)
    return True


async def recompute_for_student(
    session: AsyncSession, student_id: uuid.UUID, settings: Settings
) -> int:
    """Після синхронізації: рядки учня, потім кожного його класу (окремі транзакції: клас
    читає вже закомічені рядки учнів, тож паралельні задачі різних учнів не гублять даних)."""
    if not await recompute_student(session, student_id):
        await session.rollback()
        return 0
    await session.commit()
    class_ids = list(
        await session.scalars(
            select(ClassMembership.class_id).where(
                ClassMembership.user_id == student_id, ClassMembership.member_role == "student"
            )
        )
    )
    for class_id in class_ids:
        await recompute_class(session, class_id, settings)
        await session.commit()
    return len(class_ids)


async def recompute_alert_study(
    session: AsyncSession, school_id: uuid.UUID, settings: Settings, now: dt.datetime | None = None
) -> int:
    """Навчання під час тривог школи за `STATS_ALERT_LOOKBACK_DAYS` (старіші рядки лишаються).
    Хвилини — `duration_min` модулів, завершених (`full_at`) між початком і відбоєм тривоги
    (триває — до now) учнями школи; ручна тривога класу — лише учнями цього класу. Не комітить."""
    now = now or _now()
    await _lock(session, f"stats:alerts:{school_id}")
    alerts = (
        await session.scalars(
            select(AlertEvent).where(
                AlertEvent.school_id == school_id,
                AlertEvent.started_at
                >= now - dt.timedelta(days=settings.stats_alert_lookback_days),
            )
        )
    ).all()
    rows = []
    for alert in alerts:
        query = (
            select(
                func.count(func.distinct(ModuleProgress.student_id)),
                func.coalesce(func.sum(Module.duration_min), 0),
            )
            .join(Module, Module.id == ModuleProgress.module_id)
            .join(User, User.id == ModuleProgress.student_id)
            .where(
                User.school_id == school_id,
                ModuleProgress.progress_pct == 100,
                ModuleProgress.full_at >= alert.started_at,
                ModuleProgress.full_at < (alert.ended_at or now),
            )
        )
        if alert.class_id is not None:
            query = query.where(ModuleProgress.student_id.in_(_class_students(alert.class_id)))
        students, minutes = (await session.execute(query)).one()
        rows.append(
            {
                "alert_event_id": alert.id,
                "school_id": school_id,
                "students": students,
                "study_minutes": minutes,
                "computed_at": now,
            }
        )
    await session.execute(
        delete(AlertStudyStat).where(AlertStudyStat.alert_event_id.in_([a.id for a in alerts]))
    )
    if rows:
        await session.execute(AlertStudyStat.__table__.insert(), rows)
    return len(rows)


async def refresh_all(session: AsyncSession, settings: Settings) -> dict[str, int]:
    """Періодично (beat): усі учні, потім усі класи й навчання під час тривог шкіл — новий день
    у розкладі, пропущені задачі, події, що прийшли після відбою."""
    student_ids = list(
        await session.scalars(select(User.id).where(User.role == "student", User.is_active))
    )
    for student_id in student_ids:
        await recompute_student(session, student_id)
        await session.commit()
    class_ids = list(await session.scalars(select(SchoolClass.id)))
    for class_id in class_ids:
        await recompute_class(session, class_id, settings)
        await session.commit()
    school_ids = list(await session.scalars(select(School.id)))
    for school_id in school_ids:
        await recompute_alert_study(session, school_id, settings)
        await session.commit()
    return {"students": len(student_ids), "classes": len(class_ids), "schools": len(school_ids)}


# ---------- читання (кабінети) ----------


def test_status(
    score: Decimal | None,
    deadline: dt.datetime | None,
    now: dt.datetime,
    settings: Settings,
) -> StudentTestStatus:
    """Статус тесту учня для кабінетів: складено / не складено / вікно закривається / чекає."""
    if score is not None:
        return "passed" if score >= settings.stats_pass_score else "not_passed"
    if deadline is not None:
        if now > deadline:
            return "not_passed"
        if deadline - now < dt.timedelta(hours=settings.stats_closing_soon_h):
            return "closing_soon"
    return "pending"


def _deadline(
    window_enabled: bool, window_hours: int | None, completed_at: dt.datetime | None
) -> dt.datetime | None:
    """Дедлайн тесту з вікном: завершення уроку (годинник пристрою) + тривалість вікна."""
    if not window_enabled or window_hours is None or completed_at is None:
        return None
    return completed_at + dt.timedelta(hours=window_hours)


def _score(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


async def class_progress(session: AsyncSession, klass: SchoolClass) -> ClassProgressOut:
    rows = (
        await session.execute(
            select(ClassLessonStat, Lesson.title, Subject.name)
            .join(Lesson, Lesson.id == ClassLessonStat.lesson_id)
            .join(Subject, Subject.id == Lesson.subject_id)
            .where(ClassLessonStat.class_id == klass.id)
            .order_by(ClassLessonStat.first_date, Lesson.title)
        )
    ).all()
    return ClassProgressOut(
        class_id=klass.id,
        computed_at=max((s.computed_at for s, _, _ in rows), default=None),
        lessons=[
            ClassLessonProgress(
                lesson_id=s.lesson_id,
                title=title,
                subject_name=subject,
                first_date=s.first_date,
                students_total=s.students_total,
                students_completed=s.students_completed,
                avg_progress_pct=s.avg_progress_pct,
                tests_scored=s.tests_scored,
                tests_passed=s.tests_passed,
                avg_score=_score(s.avg_score),
            )
            for s, title, subject in rows
        ],
    )


async def class_tests(
    session: AsyncSession, klass: SchoolClass, settings: Settings, now: dt.datetime | None = None
) -> ClassTestsOut:
    """Тести уроків класу зі статусом кожного учня (хто не склав, у кого закривається вікно)."""
    now = now or _now()
    students = (
        await session.execute(
            select(User.id, User.display_name, User.last_name)
            .where(User.id.in_(_class_students(klass.id)))
            .order_by(User.last_name, User.display_name, User.id)
        )
    ).all()
    student_ids = [s.id for s in students]
    lessons = select(ClassLessonStat.lesson_id).where(ClassLessonStat.class_id == klass.id)
    tests = (
        await session.execute(
            select(Test, Lesson.title.label("lesson_title"), ClassLessonStat.first_date)
            .join(Lesson, Lesson.id == Test.lesson_id)
            .join(
                ClassLessonStat,
                (ClassLessonStat.lesson_id == Test.lesson_id)
                & (ClassLessonStat.class_id == klass.id),
            )
            .where(Test.lesson_id.in_(lessons))
            .order_by(ClassLessonStat.first_date, Lesson.title, Test.title)
        )
    ).all()
    stats = {
        (s.student_id, s.test_id): s
        for s in await session.scalars(
            select(StudentTestStat).where(StudentTestStat.student_id.in_(student_ids))
        )
    }
    completed = {
        (s.student_id, s.lesson_id): s.completed_at
        for s in await session.scalars(
            select(StudentLessonStat).where(StudentLessonStat.student_id.in_(student_ids))
        )
    }
    out = []
    for test, lesson_title, _ in tests:
        results = []
        for st in students:
            stat = stats.get((st.id, test.id))
            deadline = _deadline(
                test.window_enabled, test.window_hours, completed.get((st.id, test.lesson_id))
            )
            score = stat.score if stat else None
            results.append(
                StudentTestResult(
                    student_id=st.id,
                    display_name=st.display_name,
                    last_name=st.last_name,
                    status=test_status(score, deadline, now, settings),
                    score=_score(score),
                    attempts=stat.attempts if stat else 0,
                    deadline=deadline,
                    is_suspicious=stat.is_suspicious if stat else False,
                )
            )
        counts = TestStatusCounts(
            **{k: sum(r.status == k for r in results) for k in TestStatusCounts.model_fields}
        )
        out.append(
            ClassTestOut(
                test_id=test.id,
                lesson_id=test.lesson_id,
                lesson_title=lesson_title,
                title=test.title,
                window_hours=test.window_hours if test.window_enabled else None,
                counts=counts,
                students=results,
            )
        )
    return ClassTestsOut(class_id=klass.id, pass_score=settings.stats_pass_score, tests=out)


async def class_gaps(session: AsyncSession, klass: SchoolClass, settings: Settings) -> ClassGapsOut:
    """Прогалини по темах: тема = урок; найслабші уроки й питання за зарахованими спробами."""
    lessons = (
        await session.execute(
            select(ClassLessonStat, Lesson.title, Subject.name)
            .join(Lesson, Lesson.id == ClassLessonStat.lesson_id)
            .join(Subject, Subject.id == Lesson.subject_id)
            .where(ClassLessonStat.class_id == klass.id, ClassLessonStat.tests_scored > 0)
        )
    ).all()
    questions: dict[uuid.UUID, list[GapQuestion]] = defaultdict(list)
    for q, prompt in await session.execute(
        select(ClassQuestionStat, Question.prompt)
        .join(Question, Question.id == ClassQuestionStat.question_id)
        .where(ClassQuestionStat.class_id == klass.id, ClassQuestionStat.answered > 0)
    ):
        questions[q.lesson_id].append(
            GapQuestion(
                question_id=q.question_id,
                test_id=q.test_id,
                prompt=prompt,
                answered=q.answered,
                correct=q.correct,
                correct_pct=round(q.correct * 100 / q.answered),
            )
        )
    topics = [
        GapTopic(
            lesson_id=s.lesson_id,
            title=title,
            subject_name=subject,
            avg_score=_score(s.avg_score),
            tests_scored=s.tests_scored,
            tests_passed=s.tests_passed,
            is_gap=s.avg_score is not None and s.avg_score < settings.stats_pass_score,
            questions=sorted(questions[s.lesson_id], key=lambda q: (q.correct_pct, q.prompt)),
        )
        for s, title, subject in lessons
    ]
    topics.sort(key=lambda t: (t.avg_score if t.avg_score is not None else 101, t.title))
    return ClassGapsOut(class_id=klass.id, pass_score=settings.stats_pass_score, topics=topics)


async def student_progress(
    session: AsyncSession, student: User, settings: Settings, now: dt.datetime | None = None
) -> StudentProgressOut:
    """Кабінет учня й батьків: прогрес по уроках, тести (з вікном), час навчання."""
    now = now or _now()
    lessons = (
        await session.execute(
            select(StudentLessonStat, Lesson.title, Subject.name)
            .join(Lesson, Lesson.id == StudentLessonStat.lesson_id)
            .join(Subject, Subject.id == Lesson.subject_id)
            .where(StudentLessonStat.student_id == student.id)
            .order_by(Subject.name, Lesson.title)
        )
    ).all()
    completed = {s.lesson_id: s.completed_at for s, _, _ in lessons}
    tests = (
        await session.execute(
            select(StudentTestStat, Test)
            .join(Test, Test.id == StudentTestStat.test_id)
            .where(StudentTestStat.student_id == student.id)
            .order_by(Test.title)
        )
    ).all()

    tz = await _school_tz(session, student.school_id)
    today = now.astimezone(tz).date()
    first = today - dt.timedelta(days=STUDY_DAYS - 1)
    days = dict(
        (
            await session.execute(
                select(StudentStudyDay.day, StudentStudyDay.minutes).where(
                    StudentStudyDay.student_id == student.id
                )
            )
        ).all()
    )
    week = [
        StudyDay(
            day=first + dt.timedelta(days=i), minutes=days.get(first + dt.timedelta(days=i), 0)
        )
        for i in range(STUDY_DAYS)
    ]
    computed = [s.computed_at for s, _, _ in lessons] + [s.computed_at for s, _ in tests]
    return StudentProgressOut(
        student_id=student.id,
        computed_at=max(computed, default=None),
        lessons=[
            StudentLessonProgress(
                lesson_id=s.lesson_id,
                title=title,
                subject_name=subject,
                progress_pct=s.progress_pct,
                modules_done=s.modules_done,
                modules_total=s.modules_total,
                completed_at=s.completed_at,
                study_minutes=s.study_minutes,
            )
            for s, title, subject in lessons
        ],
        tests=[_student_test(s, t, completed.get(t.lesson_id), now, settings) for s, t in tests],
        study=StudyTime(
            total_minutes=sum(days.values()),
            last_7_days_minutes=sum(d.minutes for d in week),
            days=week,
        ),
    )


def _student_test(
    stat: StudentTestStat,
    test: Test,
    lesson_completed_at: dt.datetime | None,
    now: dt.datetime,
    settings: Settings,
) -> StudentTestOut:
    deadline = _deadline(test.window_enabled, test.window_hours, lesson_completed_at)
    return StudentTestOut(
        test_id=test.id,
        lesson_id=test.lesson_id,
        title=test.title,
        window_hours=test.window_hours if test.window_enabled else None,
        status=test_status(stat.score, deadline, now, settings),
        score=_score(stat.score),
        attempts=stat.attempts,
        deadline=deadline,
    )


async def knowledge_map(
    session: AsyncSession, student: User, settings: Settings
) -> KnowledgeMapOut:
    """Мапа знань учня: по предметах — уроки завершено / усього, середня оцінка тестів."""
    lessons = (
        await session.execute(
            select(
                StudentLessonStat.lesson_id,
                StudentLessonStat.completed_at,
                Subject.id,
                Subject.name,
            )
            .join(Lesson, Lesson.id == StudentLessonStat.lesson_id)
            .join(Subject, Subject.id == Lesson.subject_id)
            .where(StudentLessonStat.student_id == student.id)
        )
    ).all()
    scores: dict[uuid.UUID, list[Decimal]] = defaultdict(list)
    for lesson_id, score in await session.execute(
        select(StudentTestStat.lesson_id, StudentTestStat.score).where(
            StudentTestStat.student_id == student.id, StudentTestStat.score.is_not(None)
        )
    ):
        scores[lesson_id].append(score)
    subjects: dict[uuid.UUID, dict] = {}
    for lesson_id, completed_at, subject_id, name in lessons:
        item = subjects.setdefault(
            subject_id, {"name": name, "total": 0, "completed": 0, "scores": []}
        )
        item["total"] += 1
        item["completed"] += completed_at is not None
        item["scores"] += scores.get(lesson_id, [])
    out = []
    for subject_id, item in subjects.items():
        avg = _avg(item["scores"])
        out.append(
            KnowledgeMapSubject(
                subject_id=subject_id,
                name=item["name"],
                lessons_total=item["total"],
                lessons_completed=item["completed"],
                avg_score=_score(avg),
                is_gap=avg is not None and avg < settings.stats_pass_score,
            )
        )
    out.sort(key=lambda s: s.name)
    return KnowledgeMapOut(student_id=student.id, subjects=out)


async def alert_study(
    session: AsyncSession,
    admin: User,
    date_from: dt.date | None,
    date_to: dt.date | None,
    limit: int,
    now: dt.datetime | None = None,
) -> AlertStudyOut:
    """Дашборд адміністрації: тривоги школи за період (дати за поясом школи, включно) і скільки
    навчання на них припало. Тривога без перерахунку — `students`/`study_minutes` = null."""
    now = now or _now()
    if admin.school_id is None:
        return AlertStudyOut(alerts=[], alert_minutes=0, study_minutes=0, computed_at=None)
    tz = await _school_tz(session, admin.school_id)
    query = (
        select(AlertEvent, AlertStudyStat)
        .outerjoin(AlertStudyStat, AlertStudyStat.alert_event_id == AlertEvent.id)
        .where(AlertEvent.school_id == admin.school_id)
    )
    if date_from is not None:
        query = query.where(
            AlertEvent.started_at >= dt.datetime.combine(date_from, dt.time(), tzinfo=tz)
        )
    if date_to is not None:
        end = dt.datetime.combine(date_to + dt.timedelta(days=1), dt.time(), tzinfo=tz)
        query = query.where(AlertEvent.started_at < end)
    rows = (
        await session.execute(
            query.order_by(AlertEvent.started_at.desc(), AlertEvent.id).limit(limit)
        )
    ).all()
    items = [
        AlertStudyItem(
            alert_id=a.id,
            source=a.source,
            is_drill=a.is_drill,
            class_id=a.class_id,
            started_at=a.started_at,
            ended_at=a.ended_at,
            duration_minutes=int(((a.ended_at or now) - a.started_at).total_seconds() // 60),
            students=s.students if s else None,
            study_minutes=s.study_minutes if s else None,
        )
        for a, s in rows
    ]
    return AlertStudyOut(
        alerts=items,
        alert_minutes=sum(i.duration_minutes for i in items),
        study_minutes=sum(i.study_minutes or 0 for i in items),
        computed_at=max((s.computed_at for _, s in rows if s), default=None),
    )
