"""AI-аналіз тесту класу: висновок для вчителя й фідбек кожному учню та батькам.

Потік: вчитель натискає «Проаналізувати» (`start`) → рядок `processing` → Celery
`test_analysis.run` збирає зараховані спроби учнів класу (`build_payload`), викликає AI
(`POST /ai/v1/test-analysis`) і зберігає відповідь (`draft`) → вчитель за потреби править
тексти учню/батькам (`edit_feedback`) і публікує (`publish`) → учні й батьки бачать свій текст
(`student_feedback`).

Приватність: в AI ідуть лише питання, варіанти й відповіді під псевдонімами `s1`, `s2`…;
імен і id учнів AI не бачить. Псевдоніми замінюються на id лише в збереженому `result`.
Адміністрація аналізів не бачить (як і інших навчальних даних окремих учнів).

Питання `text` і `match` поки не аналізуються (AI-сервіс підтримує `single`/`multiple`) —
вони просто не потрапляють у запит.
"""

import datetime as dt
import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import exists, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.lessons import Lesson, Question, Subject, Test
from app.models.packs import KnowledgePack, KnowledgePackLesson
from app.models.school import ClassMembership, ParentChild, SchoolClass, User
from app.models.sync import Attempt
from app.models.test_analysis import TestAnalysis, TestAnalysisEdit
from app.schemas.test_analysis import (
    AnalysisError,
    AnalysisStudentOut,
    FeedbackEditIn,
    TestAnalysisOut,
    TestFeedbackItem,
    TestFeedbackOut,
)
from app.services import school as school_service
from app.services.ai import AIClient

logger = logging.getLogger(__name__)

SUPPORTED_KINDS = ("single", "multiple")
# Ліміти схеми запиту AI-сервісу (`TestAnalysisRequest`).
MAX_QUESTIONS = 50
MAX_STUDENTS = 60
MAX_OPTIONS = 10
MAX_OPTION_ID = 16
MAX_OPTION_TEXT = 500
MAX_PROMPT = 2000
MAX_TITLE = 200
MAX_SUBJECT = 100
# Ключі в `result`, де AI повертає псевдоніми учнів.
_ID_KEY = "student_id"
_ID_LIST_KEYS = ("student_ids", "needs_support_ids")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _not_found(what: str = "Analysis") -> AppError:
    return AppError("NOT_FOUND", f"{what} not found", status_code=404)


# ---------- вибірки ----------


def _class_students(class_id: uuid.UUID):
    return select(ClassMembership.user_id).where(
        ClassMembership.class_id == class_id, ClassMembership.member_role == "student"
    )


def _credited_attempts(class_id: uuid.UUID, test_id: uuid.UUID):
    return select(Attempt).where(
        Attempt.test_id == test_id,
        Attempt.credit_status == "credited",
        Attempt.student_id.in_(_class_students(class_id)),
    )


async def _class_has_lesson(
    session: AsyncSession, class_id: uuid.UUID, lesson_id: uuid.UUID
) -> bool:
    """Урок у розкладі класу або в його пакеті (те саме правило, що й для учня)."""
    scheduled = school_service.scheduled_lessons()
    assigned = select(scheduled.c.lesson_id).where(
        scheduled.c.class_id == class_id, scheduled.c.lesson_id == lesson_id
    )
    in_pack = (
        select(KnowledgePackLesson.lesson_id)
        .join(KnowledgePack, KnowledgePack.id == KnowledgePackLesson.pack_id)
        .where(KnowledgePack.class_id == class_id, KnowledgePackLesson.lesson_id == lesson_id)
    )
    return bool(await session.scalar(select(or_(exists(assigned), exists(in_pack)))))


async def _class_test(session: AsyncSession, klass: SchoolClass, test_id: uuid.UUID) -> Test:
    test = await session.get(Test, test_id)
    if test is None or not await _class_has_lesson(session, klass.id, test.lesson_id):
        raise _not_found("Test")
    return test


async def _latest(
    session: AsyncSession, class_id: uuid.UUID, test_id: uuid.UUID
) -> TestAnalysis | None:
    return await session.scalar(
        select(TestAnalysis)
        .where(TestAnalysis.class_id == class_id, TestAnalysis.test_id == test_id)
        .order_by(TestAnalysis.created_at.desc(), TestAnalysis.id.desc())
        .limit(1)
    )


async def _expire_if_stale(
    session: AsyncSession, analysis: TestAnalysis | None, settings: Settings
) -> None:
    """Аналіз, що висить у `processing` довше за `AI_ANALYSIS_STALE_S` (задача впала чи
    воркер не запущений), переводимо у `failed`: вчитель зможе запустити ще раз."""
    if analysis is None or analysis.status != "processing":
        return
    if analysis.created_at > _now() - dt.timedelta(seconds=settings.ai_analysis_stale_s):
        return
    analysis.status = "failed"
    analysis.error_code = "AI_TIMEOUT"
    analysis.completed_at = _now()
    await session.commit()
    logger.warning("Test analysis expired in processing: analysis=%s", analysis.id)


# ---------- B1: запуск ----------


async def start(
    session: AsyncSession,
    klass: SchoolClass,
    test_id: uuid.UUID,
    teacher: User,
    settings: Settings,
) -> tuple[TestAnalysisOut, bool]:
    """Новий аналіз (`processing`). Повертає (аналіз, створено?). Якщо аналіз цього тесту
    вже йде — повертає його, нового не створює. Задачу ставить виклик після commit."""
    test = await _class_test(session, klass, test_id)
    latest = await _latest(session, klass.id, test.id)
    await _expire_if_stale(session, latest, settings)
    if latest is not None and latest.status == "processing":
        return await analysis_out(session, latest), False

    attempts = len((await session.scalars(_credited_attempts(klass.id, test.id))).all())
    required = settings.ai_analysis_min_attempts
    if attempts < required:
        raise AppError(
            "NOT_ENOUGH_ATTEMPTS",
            "Not enough credited attempts to analyze the test",
            status_code=409,
            details={"attempts": attempts, "required": required},
        )
    supported = await session.scalar(
        select(exists().where(Question.test_id == test.id, Question.kind.in_(SUPPORTED_KINDS)))
    )
    if not supported:
        raise AppError(
            "TEST_NOT_ANALYZABLE",
            "The test has no single/multiple choice questions to analyze",
            status_code=409,
        )

    analysis = TestAnalysis(
        class_id=klass.id,
        test_id=test.id,
        created_by=teacher.id,
        status="processing",
        attempts_count=attempts,
    )
    session.add(analysis)
    try:
        await session.commit()
    except IntegrityError:
        # Паралельний клік: інший запит щойно створив `processing` (унікальний індекс).
        await session.rollback()
        running = await _latest(session, klass.id, test.id)
        if running is None:
            raise
        return await analysis_out(session, running), False
    await session.refresh(analysis)
    return await analysis_out(session, analysis), True


# ---------- B2: останній аналіз ----------


async def get_latest(
    session: AsyncSession, klass: SchoolClass, test_id: uuid.UUID, settings: Settings
) -> TestAnalysisOut:
    test = await _class_test(session, klass, test_id)
    latest = await _latest(session, klass.id, test.id)
    if latest is None:
        raise AppError("ANALYSIS_NOT_FOUND", "The test has not been analyzed yet", 404)
    await _expire_if_stale(session, latest, settings)
    return await analysis_out(session, latest)


# ---------- Celery: виклик AI ----------


async def build_payload(
    session: AsyncSession, analysis: TestAnalysis, settings: Settings
) -> tuple[dict[str, Any], dict[str, str]]:
    """Запит до AI і відповідність псевдонім → id учня. Без імен і id учнів."""
    klass = await session.get(SchoolClass, analysis.class_id)
    test = await session.get(Test, analysis.test_id)
    if klass is None or test is None:
        raise _not_found()
    lesson = await session.get(Lesson, test.lesson_id)
    subject = (
        await session.scalar(select(Subject.name).where(Subject.id == lesson.subject_id))
        if lesson
        else None
    )

    questions: list[dict[str, Any]] = []
    option_ids: dict[str, set[str]] = {}
    for q in await session.scalars(
        select(Question)
        .where(Question.test_id == test.id, Question.kind.in_(SUPPORTED_KINDS))
        .order_by(Question.position)
    ):
        options = [
            {"id": o["id"], "text": str(o.get("text") or "")[:MAX_OPTION_TEXT]}
            for o in (q.options or [])
            if isinstance(o, dict)
            and isinstance(o.get("id"), str)
            and 0 < len(o["id"]) <= MAX_OPTION_ID
        ][:MAX_OPTIONS]
        ids = {o["id"] for o in options}
        key = [k for k in (q.answer_key or []) if isinstance(k, str) and k in ids]
        if len(options) < 2 or not key:
            continue  # непридатне питання (AI-схема відхилила б увесь запит)
        questions.append(
            {
                "id": str(q.id),
                "prompt": q.prompt[:MAX_PROMPT],
                "kind": q.kind,
                "options": options,
                "answer_key": key,
                "points": max(1, min(int(q.points or 1), 100)),
            }
        )
        option_ids[str(q.id)] = ids
        if len(questions) == MAX_QUESTIONS:
            break

    attempts = (
        await session.scalars(
            _credited_attempts(klass.id, test.id).order_by(Attempt.completed_at_client, Attempt.id)
        )
    ).all()
    if len(attempts) > MAX_STUDENTS:
        logger.warning("Test analysis truncated to %d students", MAX_STUDENTS)
    students: list[dict[str, Any]] = []
    pseudonyms: dict[str, str] = {}
    for n, attempt in enumerate(attempts[:MAX_STUDENTS], start=1):
        alias = f"s{n}"
        pseudonyms[alias] = str(attempt.student_id)
        raw = attempt.answers if isinstance(attempt.answers, dict) else {}
        answers = {}
        for qid, valid in option_ids.items():
            given = raw.get(qid)
            if isinstance(given, list):
                answers[qid] = [a for a in given if isinstance(a, str) and a in valid]
        students.append({"student_id": alias, "answers": answers})

    payload = {
        "grade": max(1, min(klass.grade or (lesson.grade if lesson else None) or 1, 11)),
        "subject": subject[:MAX_SUBJECT] if subject else None,
        "lesson_title": lesson.title[:MAX_TITLE] if lesson else None,
        "test_title": test.title[:MAX_TITLE],
        "pass_score_pct": float(settings.stats_pass_score),
        "questions": questions,
        "students": students,
    }
    return payload, pseudonyms


def restore_ids(value: Any, pseudonyms: dict[str, str]) -> Any:
    """Підміняє псевдоніми на id учнів у всій відповіді AI. Невідомий псевдонім (помилка
    AI) прибирається: у списках — елемент, у `students[]` — увесь запис."""
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict) and _ID_KEY in item and item[_ID_KEY] not in pseudonyms:
                continue
            out.append(restore_ids(item, pseudonyms))
        return out
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key == _ID_KEY and isinstance(item, str):
            result[key] = pseudonyms.get(item, item)
        elif key in _ID_LIST_KEYS and isinstance(item, list):
            result[key] = [pseudonyms[i] for i in item if isinstance(i, str) and i in pseudonyms]
        else:
            result[key] = restore_ids(item, pseudonyms)
    return result


async def run(
    session: AsyncSession, analysis_id: uuid.UUID, ai: AIClient, settings: Settings
) -> str | None:
    """Тіло Celery-задачі. Повертає кінцевий статус (None — нічого не робили)."""
    analysis = await session.get(TestAnalysis, analysis_id)
    if analysis is None or analysis.status != "processing":
        return None
    payload, pseudonyms = await build_payload(session, analysis, settings)
    # Не тримаємо транзакцію відкритою, поки працює LLM (до хвилини і довше).
    await session.commit()

    error_code: str | None = None
    result: dict[str, Any] | None = None
    if not payload["questions"] or not payload["students"]:
        error_code = "AI_BAD_REQUEST"
    else:
        try:
            result = restore_ids(await ai.test_analysis(payload), pseudonyms)
        except AppError as exc:
            error_code = exc.code

    await session.refresh(analysis)
    if analysis.status != "processing":
        # Поки чекали AI, аналіз визнали завислим — результат не перезаписує `failed`.
        return analysis.status
    analysis.completed_at = _now()
    if error_code is None:
        analysis.status = "draft"
        analysis.result = result
    else:
        analysis.status = "failed"
        analysis.error_code = error_code
    await session.commit()
    logger.info("Test analysis finished: analysis=%s status=%s", analysis.id, analysis.status)
    return analysis.status


# ---------- відповідь API (з правками вчителя) ----------


async def _edits(session: AsyncSession, analysis_id: uuid.UUID) -> dict[str, TestAnalysisEdit]:
    rows = await session.scalars(
        select(TestAnalysisEdit).where(TestAnalysisEdit.analysis_id == analysis_id)
    )
    return {str(e.student_id): e for e in rows}


def _apply_edit(student: dict[str, Any], edit: TestAnalysisEdit | None) -> dict[str, Any]:
    student = dict(student)
    feedback = dict(student.get("feedback") or {})
    edited = False
    if edit is not None:
        if edit.student_text is not None:
            feedback["student"], edited = edit.student_text, True
        if edit.parent_text is not None:
            feedback["parent"], edited = edit.parent_text, True
    student["feedback"] = feedback
    student["feedback_edited"] = edited
    return student


async def analysis_out(session: AsyncSession, analysis: TestAnalysis) -> TestAnalysisOut:
    result = analysis.result
    if isinstance(result, dict) and analysis.status in ("draft", "published"):
        edits = await _edits(session, analysis.id)
        result = dict(result)
        result["students"] = [
            _apply_edit(s, edits.get(str(s.get("student_id"))))
            for s in result.get("students") or []
            if isinstance(s, dict)
        ]
    else:
        result = None
    return TestAnalysisOut(
        id=analysis.id,
        class_id=analysis.class_id,
        test_id=analysis.test_id,
        status=analysis.status,
        attempts_count=analysis.attempts_count,
        created_at=analysis.created_at,
        created_by=analysis.created_by,
        completed_at=analysis.completed_at,
        published_at=analysis.published_at,
        error=AnalysisError(code=analysis.error_code)
        if analysis.status == "failed" and analysis.error_code
        else None,
        result=result,
    )


# ---------- B3, B4: правки й публікація (вчитель класу) ----------


async def get_for_teacher(
    session: AsyncSession, teacher: User, analysis_id: uuid.UUID
) -> TestAnalysis:
    analysis = await session.get(TestAnalysis, analysis_id)
    if analysis is None:
        raise _not_found()
    member = await session.scalar(
        select(ClassMembership.user_id).where(
            ClassMembership.class_id == analysis.class_id,
            ClassMembership.user_id == teacher.id,
            ClassMembership.member_role == "teacher",
        )
    )
    if member is None:
        raise AppError("FORBIDDEN", "No access to this analysis", status_code=403)
    return analysis


def _student_entry(analysis: TestAnalysis, student_id: uuid.UUID) -> dict[str, Any] | None:
    students = (analysis.result or {}).get("students") or []
    return next((s for s in students if s.get("student_id") == str(student_id)), None)


async def edit_feedback(
    session: AsyncSession,
    teacher: User,
    analysis: TestAnalysis,
    student_id: uuid.UUID,
    body: FeedbackEditIn,
) -> AnalysisStudentOut:
    if analysis.status != "draft":
        raise AppError(
            "ANALYSIS_NOT_DRAFT",
            "Only a draft analysis can be edited",
            status_code=409,
            details={"status": analysis.status},
        )
    entry = _student_entry(analysis, student_id)
    if entry is None:
        raise _not_found("Student")
    edit = await session.get(TestAnalysisEdit, (analysis.id, student_id))
    if edit is None:
        edit = TestAnalysisEdit(analysis_id=analysis.id, student_id=student_id)
        session.add(edit)
    # Відсутнє поле — без змін; `null` — повернути текст AI.
    if "student" in body.model_fields_set:
        edit.student_text = body.student
    if "parent" in body.model_fields_set:
        edit.parent_text = body.parent
    edit.edited_by = teacher.id
    edit.edited_at = _now()
    await session.commit()
    return AnalysisStudentOut.model_validate(_apply_edit(entry, edit))


async def publish(session: AsyncSession, analysis: TestAnalysis) -> TestAnalysisOut:
    if analysis.status not in ("draft", "published"):
        raise AppError(
            "ANALYSIS_NOT_READY",
            "The analysis is not ready to be published",
            status_code=409,
            details={"status": analysis.status},
        )
    if analysis.status == "draft":
        analysis.status = "published"
        analysis.published_at = _now()
        await session.commit()
    return await analysis_out(session, analysis)


# ---------- B5: фідбек учню / батькам ----------


async def student_feedback(session: AsyncSession, viewer: User, student: User) -> TestFeedbackOut:
    """Опубліковані відгуки учня: по одному (останньому) на тест, від нових до старих.
    `text` — за роллю того, хто питає (учень чи батьки), з правками вчителя."""
    if viewer.role == "student" and viewer.id == student.id:
        field = "student"
    elif viewer.role == "parent" and await session.get(ParentChild, (viewer.id, student.id)):
        field = "parent"
    else:
        raise AppError("FORBIDDEN", "No access to this student", status_code=403)

    rows = await session.execute(
        select(TestAnalysis, Test.title, Lesson.title, Subject.name)
        .join(Test, Test.id == TestAnalysis.test_id)
        .join(Lesson, Lesson.id == Test.lesson_id)
        .outerjoin(Subject, Subject.id == Lesson.subject_id)
        .where(
            TestAnalysis.status == "published",
            TestAnalysis.class_id.in_(
                select(ClassMembership.class_id).where(
                    ClassMembership.user_id == student.id,
                    ClassMembership.member_role == "student",
                )
            ),
            TestAnalysis.result.contains({"students": [{"student_id": str(student.id)}]}),
        )
        .order_by(TestAnalysis.published_at.desc(), TestAnalysis.id.desc())
    )
    items: list[TestFeedbackItem] = []
    seen: set[uuid.UUID] = set()
    for analysis, test_title, lesson_title, subject in rows:
        if analysis.test_id in seen:
            continue
        seen.add(analysis.test_id)
        entry = _student_entry(analysis, student.id)
        if entry is None:
            continue
        edit = await session.get(TestAnalysisEdit, (analysis.id, student.id))
        entry = _apply_edit(entry, edit)
        score = entry.get("score_pct")
        items.append(
            TestFeedbackItem(
                analysis_id=analysis.id,
                test_id=analysis.test_id,
                test_title=test_title,
                lesson_title=lesson_title,
                subject=subject,
                score_pct=float(score) if isinstance(score, int | float | Decimal) else None,
                correct_count=len(entry.get("correct_question_ids") or []),
                questions_total=len((analysis.result or {}).get("questions") or []),
                text=str(entry["feedback"].get(field) or ""),
                published_at=analysis.published_at,
            )
        )
    return TestFeedbackOut(items=items)


# ---------- видалення даних учня (B15) ----------


def _without_student(value: Any, sid: str) -> Any:
    if isinstance(value, list):
        return [
            _without_student(i, sid)
            for i in value
            if not (isinstance(i, dict) and i.get(_ID_KEY) == sid)
        ]
    if not isinstance(value, dict):
        return value
    return {
        k: [i for i in v if i != sid]
        if k in _ID_LIST_KEYS and isinstance(v, list)
        else _without_student(v, sid)
        for k, v in value.items()
    }


async def forget_student(session: AsyncSession, student_id: uuid.UUID) -> int:
    """Прибирає учня з `result` усіх аналізів (jsonb каскад не зачіпає). Правки вчителя
    видаляє ON DELETE CASCADE. Знеособлена статистика класу лишається. Без commit."""
    sid = str(student_id)
    analyses = await session.scalars(
        select(TestAnalysis).where(
            TestAnalysis.result.contains({"students": [{"student_id": sid}]})
        )
    )
    count = 0
    for analysis in analyses:
        analysis.result = _without_student(analysis.result, sid)
        count += 1
    return count
