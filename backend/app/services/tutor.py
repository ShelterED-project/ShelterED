"""ШІ-репетитор (B13): `POST /tutor/ask` і закешовані пояснення для пакета «Рюкзак».

AI-сервіс stateless, тож стан розмови зберігає backend (`tutor_conversation`): поточне
завдання з еталонною відповіддю (учню — лише умова), кількість підказок, до 8 останніх
реплік і відповіді на останні запити.

Ідемпотентність: відповідь зберігається в розмові під `request_id` (останні
`MAX_REPLIES`). Повтор того самого `request_id` (обрив до відповіді) повертає збережену
відповідь без виклику AI і без витрати ліміту запитів. Два одночасні повтори, що обидва не
застали збереженої відповіді, можуть викликати AI двічі, але в розмову потрапить одна
відповідь (рядок розмови блокується на час запису, друга бере вже збережену).

Транзакція БД не тримається під час виклику AI (до 45 с): контекст читається, транзакція
закривається, після відповіді розмова перечитується з блокуванням і оновлюється.

Мінімум даних: в AI — клас (номер), предмет, назва модуля, текст картки й репліки учня; без
імені, email, школи. Для `intent: safety` повідомлення учня не зберігається ніде (ні в
історії, ні у відповіді), завдання й підказки не змінюються.
"""

import datetime as dt
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, exists, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.lessons import Card, Lesson, Module, Subject
from app.models.school import SchoolClass, User
from app.models.tutor import TutorConversation, TutorExplanation
from app.schemas.packs import PackExplanation
from app.schemas.tutor import (
    TutorAnswerOut,
    TutorAskRequest,
    TutorCheckResult,
    TutorTaskOut,
    decode_image,
)
from app.services import school as school_service
from app.services.ai import AIChatResponse, AIClient
from app.services.sync import student_has_lesson

logger = logging.getLogger(__name__)

# Обмеження контракту AI: історія — до 8 реплік, репліка — до 4000 символів.
MAX_HISTORY = 8
MAX_HISTORY_TEXT = 4000
# Текст матеріалу (картка чи модуль), що йде в AI для пояснення.
MAX_CONTEXT_CHARS = 3000
# Скільки останніх відповідей розмови зберігається для повторів `request_id`.
MAX_REPLIES = 10
# Скільки уроків без пояснень бере один прохід beat.
MISSING_EXPLANATIONS_BATCH = 50

EXPLAIN_PROMPT = "Поясни цей матеріал іншими словами, з одним прикладом:\n"
# Репліка учня в історії, коли тексту немає (кнопка без повідомлення, лише фото).
PLACEHOLDERS = {
    "explain": "Поясни, будь ласка.",
    "practice": "Дай завдання або підказку.",
    "check": "[фото відповіді]",
    None: "…",
}


def _not_found(what: str) -> AppError:
    return AppError("NOT_FOUND", f"{what} not found", status_code=404)


def _validation(code: str, message: str) -> AppError:
    return AppError(code, message, status_code=422)


# ---------- текст матеріалу ----------


def card_text(card: Card) -> str:
    """Текст картки: `body.text` текстової, підпис (`caption`) картки з медіа."""
    body = card.body if isinstance(card.body, dict) else {}
    value = body.get("text") if card.kind == "text" else body.get("caption")
    return value.strip() if isinstance(value, str) else ""


async def module_text(session: AsyncSession, module_id: uuid.UUID) -> str:
    """Текст модуля для пояснення: текстові картки по порядку, до `MAX_CONTEXT_CHARS`."""
    cards = await session.scalars(
        select(Card).where(Card.module_id == module_id, Card.kind == "text").order_by(Card.position)
    )
    text = "\n\n".join(t for t in (card_text(c) for c in cards) if t)
    return text[:MAX_CONTEXT_CHARS]


# ---------- контекст запиту ----------


@dataclass
class Context:
    grade: int
    lesson: Lesson | None = None
    module: Module | None = None
    card: Card | None = None
    subject: str | None = None


async def _student_grade(session: AsyncSession, student: User) -> int | None:
    class_id = await school_service.student_class_id(session, student.id)
    if class_id is None:
        return None
    return await session.scalar(select(SchoolClass.grade).where(SchoolClass.id == class_id))


async def _resolve_context(
    session: AsyncSession,
    student: User,
    body: TutorAskRequest,
    conv: TutorConversation | None,
) -> Context:
    """Урок/модуль/картка з запиту (або збережені в розмові, якщо в запиті їх немає).
    Урок має бути в розкладі чи пакеті класу учня — інакше 403."""
    card = module = lesson = None
    if body.lesson_id or body.module_id or body.card_id:
        lesson_id, module_id = body.lesson_id, body.module_id
    elif conv is not None:
        lesson_id, module_id = conv.lesson_id, conv.module_id
    else:
        lesson_id = module_id = None

    if body.card_id is not None:
        card = await session.get(Card, body.card_id)
        if card is None:
            raise _not_found("Card")
        if module_id is not None and module_id != card.module_id:
            raise _validation("VALIDATION_ERROR", "card_id does not belong to module_id")
        module_id = card.module_id
    if module_id is not None:
        module = await session.get(Module, module_id)
        if module is None:
            raise _not_found("Module")
        if lesson_id is not None and lesson_id != module.lesson_id:
            raise _validation("VALIDATION_ERROR", "module_id does not belong to lesson_id")
        lesson_id = module.lesson_id
    subject = None
    if lesson_id is not None:
        lesson = await session.get(Lesson, lesson_id)
        if lesson is None:
            raise _not_found("Lesson")
        if not await student_has_lesson(session, student.id, lesson.id):
            raise AppError("FORBIDDEN", "Lesson is not available to this student", 403)
        subject = await session.scalar(select(Subject.name).where(Subject.id == lesson.subject_id))

    grade = await _student_grade(session, student)
    if grade is None and lesson is not None:
        grade = lesson.grade
    if grade is None:
        raise AppError("FORBIDDEN", "Student has no class", status_code=403)
    return Context(grade=grade, lesson=lesson, module=module, card=card, subject=subject)


# ---------- відповідь учню ----------


def _options(raw: Any) -> list[str] | None:
    if not isinstance(raw, list):
        return None
    result = []
    for item in raw:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            result.append(item["text"])
    return result or None


def public_task(task: Any) -> TutorTaskOut | None:
    """Умова завдання для учня. Білий список полів: `answer`, `expected_answer`, `hints`,
    `common_mistakes` і будь-які інші поля від AI учню не віддаються."""
    if not isinstance(task, dict) or not isinstance(task.get("question"), str):
        return None
    answer_type = task.get("answer_type")
    return TutorTaskOut(
        question=task["question"],
        answer_type=answer_type if isinstance(answer_type, str) else None,
        options=_options(task.get("options")),
    )


def _check_result(raw: dict[str, Any] | None) -> TutorCheckResult | None:
    if not raw:
        return None
    try:
        return TutorCheckResult(correct=bool(raw["correct"]), score=float(raw["score"]))
    except (KeyError, TypeError, ValueError):
        return None


def _stored_reply(conv: TutorConversation, request_id: uuid.UUID) -> TutorAnswerOut | None:
    for item in conv.replies or []:
        if item.get("request_id") == str(request_id):
            return TutorAnswerOut.model_validate(item["response"])
    return None


async def find_replay(
    session: AsyncSession, student: User, body: TutorAskRequest
) -> TutorAnswerOut | None:
    """Збережена відповідь на цей `request_id` (повтор після обриву). Чужа розмова — 404."""
    conv = await session.get(TutorConversation, body.conversation_id)
    if conv is None:
        return None
    if conv.student_id != student.id:
        raise _not_found("Conversation")
    return _stored_reply(conv, body.request_id)


# ---------- запит до AI ----------


async def _build_message(
    session: AsyncSession, body: TutorAskRequest, ctx: Context, action: str | None
) -> str | None:
    """`explain`: текст картки (або текстових карток модуля, якщо картку не вказано) + питання
    учня, якщо є. Інакше — повідомлення учня як є."""
    if action == "explain":
        if ctx.card is not None:
            material = card_text(ctx.card)[:MAX_CONTEXT_CHARS]
        elif ctx.module is not None and not body.message:
            material = await module_text(session, ctx.module.id)
        else:
            material = ""
        if material:
            prompt = EXPLAIN_PROMPT + material
            return f"{prompt}\n\nПитання учня: {body.message}" if body.message else prompt
    return body.message


async def _cached_explanation(
    session: AsyncSession, body: TutorAskRequest, ctx: Context, conv: TutorConversation | None
) -> TutorAnswerOut | None:
    """AI недоступний, а учень просив пояснити модуль: пояснення з кешу (те саме, що в пакеті)."""
    if ctx.module is None or ctx.lesson is None:
        return None
    text = await session.scalar(
        select(TutorExplanation.text)
        .where(TutorExplanation.module_id == ctx.module.id)
        .order_by(TutorExplanation.lesson_version.desc())
        .limit(1)
    )
    if text is None:
        return None
    return TutorAnswerOut(
        request_id=body.request_id,
        conversation_id=body.conversation_id,
        reply=text,
        intent="explain",
        task=public_task(conv.task) if conv is not None else None,
        hints_used=conv.hints_used if conv is not None else 0,
        suggestions=[],
        check_result=None,
        cached=True,
    )


async def ask(
    session: AsyncSession,
    student: User,
    body: TutorAskRequest,
    client: AIClient,
    settings: Settings,
) -> TutorAnswerOut:
    conv = await session.get(TutorConversation, body.conversation_id)
    if conv is not None and conv.student_id != student.id:
        raise _not_found("Conversation")
    ctx = await _resolve_context(session, student, body, conv)
    action = body.action

    image = None
    if body.image_base64 is not None:
        if action not in (None, "check"):
            raise _validation("VALIDATION_ERROR", "image_base64 is accepted only for action=check")
        try:
            mime, _ = decode_image(body.image_base64, settings.tutor_max_image_bytes)
        except ValueError as exc:
            raise _validation("INVALID_IMAGE", str(exc)) from None
        action = "check"
        image = f"data:{mime};base64,{body.image_base64.split(',', 1)[-1].strip()}"

    # Інший модуль — інша тема: старе завдання не переноситься.
    same_topic = conv is not None and (ctx.module is None or conv.module_id == ctx.module.id)
    task = conv.task if conv is not None and same_topic else None
    hints_used = conv.hints_used if conv is not None and same_topic else 0
    history = list(conv.history or []) if conv is not None else []

    if action == "check" and task is None:
        raise _validation("TUTOR_TASK_REQUIRED", "No current task to check: ask for a task first")
    if action == "practice" and task is None and ctx.module is None and ctx.lesson is None:
        raise _validation("TUTOR_TOPIC_REQUIRED", "A new task needs lesson_id or module_id")
    message = await _build_message(session, body, ctx, action)
    if message is None and image is None and action is None:
        raise _validation("VALIDATION_ERROR", "message, image_base64 or action is required")

    payload: dict[str, Any] = {"grade": ctx.grade, "hints_used": hints_used, "history": history}
    if action is not None:
        payload["action"] = action
    if ctx.subject:
        payload["subject"] = ctx.subject
    if ctx.module is not None:
        payload["topic"], payload["topic_id"] = ctx.module.title, str(ctx.module.id)
    elif ctx.lesson is not None:
        payload["topic"], payload["topic_id"] = ctx.lesson.title, str(ctx.lesson.id)
    if message is not None:
        payload["message"] = message
    if image is not None:
        payload["image_base64"] = image
    if task is not None:
        payload["task"] = task

    # Транзакцію не тримаємо відкритою на час виклику AI.
    await session.commit()
    try:
        ai = await client.chat(payload)
    except AppError as exc:
        if exc.code == "AI_UNAVAILABLE" and action == "explain":
            cached = await _cached_explanation(session, body, ctx, conv)
            if cached is not None:
                return cached
        raise
    return await _save(session, student, body, ctx, ai, message or PLACEHOLDERS[action], same_topic)


async def _locked_conversation(
    session: AsyncSession, student: User, body: TutorAskRequest, ctx: Context
) -> TutorConversation:
    await session.execute(
        pg_insert(TutorConversation)
        .values(
            id=body.conversation_id,
            student_id=student.id,
            lesson_id=ctx.lesson.id if ctx.lesson else None,
            module_id=ctx.module.id if ctx.module else None,
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    conv = await session.get(
        TutorConversation, body.conversation_id, with_for_update=True, populate_existing=True
    )
    assert conv is not None
    if conv.student_id != student.id:
        raise _not_found("Conversation")
    return conv


async def _save(
    session: AsyncSession,
    student: User,
    body: TutorAskRequest,
    ctx: Context,
    ai: AIChatResponse,
    user_text: str,
    same_topic: bool,
) -> TutorAnswerOut:
    conv = await _locked_conversation(session, student, body, ctx)
    stored = _stored_reply(conv, body.request_id)
    if stored is not None:
        # Паралельний повтор уже зберіг відповідь — віддаємо її, друга не записується.
        await session.rollback()
        return stored

    intent = ai.normalized_intent()
    if ctx.lesson is not None:
        conv.lesson_id = ctx.lesson.id
        conv.module_id = ctx.module.id if ctx.module else None
    if not same_topic:
        conv.task, conv.hints_used = None, 0
    if intent != "safety":
        task = ai.task
        check = _check_result(ai.check_result)
        # Правильно розв'язане завдання закрите: наступне `practice` дасть нове, а не підказку.
        if intent == "check" and check is not None and check.correct:
            task = None
        conv.task = task
        if ai.hints_used is not None:
            conv.hints_used = max(0, min(3, ai.hints_used)) if task is not None else 0
        elif task is None:
            conv.hints_used = 0
        history = list(conv.history or []) + [
            {"role": "user", "text": user_text[:MAX_HISTORY_TEXT]},
            {"role": "assistant", "text": ai.reply[:MAX_HISTORY_TEXT]},
        ]
        conv.history = history[-MAX_HISTORY:]
    out = TutorAnswerOut(
        request_id=body.request_id,
        conversation_id=body.conversation_id,
        reply=ai.reply,
        intent=intent,  # type: ignore[arg-type]
        task=None if intent == "safety" else public_task(conv.task),
        hints_used=conv.hints_used,
        suggestions=[] if intent == "safety" else ai.suggestions,
        check_result=_check_result(ai.check_result) if intent == "check" else None,
        cached=False,
    )
    replies = list(conv.replies or []) + [
        {"request_id": str(body.request_id), "response": out.model_dump(mode="json")}
    ]
    conv.replies = replies[-MAX_REPLIES:]
    conv.updated_at = dt.datetime.now(dt.UTC)
    await session.commit()
    return out


# ---------- закешовані пояснення (B13.3) ----------


async def _lesson_grade(session: AsyncSession, lesson: Lesson) -> int | None:
    """Клас уроку; якщо вчитель його не вказав — найменший клас, де урок стоїть у розкладі."""
    if lesson.grade is not None:
        return lesson.grade
    scheduled = school_service.scheduled_lessons()
    return await session.scalar(
        select(func.min(SchoolClass.grade))
        .join(scheduled, scheduled.c.class_id == SchoolClass.id)
        .where(scheduled.c.lesson_id == lesson.id)
    )


def _has_text_cards():
    return exists().where(
        Card.module_id == Module.id,
        Card.kind == "text",
        func.length(func.coalesce(Card.body["text"].astext, "")) > 0,
    )


def _has_explanation():
    return exists().where(
        TutorExplanation.lesson_id == Lesson.id,
        TutorExplanation.lesson_version == Lesson.version,
        TutorExplanation.module_id == Module.id,
    )


async def lessons_missing_explanations(
    session: AsyncSession, limit: int = MISSING_EXPLANATIONS_BATCH
) -> list[uuid.UUID]:
    """Опубліковані уроки, у яких є модуль з текстом без пояснення поточної версії."""
    rows = await session.scalars(
        select(Lesson.id)
        .join(Module, Module.lesson_id == Lesson.id)
        .where(Lesson.status == "published", _has_text_cards(), ~_has_explanation())
        .group_by(Lesson.id)
        .order_by(Lesson.id)
        .limit(limit)
    )
    return list(rows)


async def generate_explanations(
    session: AsyncSession, lesson_id: uuid.UUID, client: AIClient
) -> tuple[int, bool]:
    """Пояснення модулів опублікованого уроку, яких ще немає для його версії.
    (нових пояснень, AI недоступний — повторити пізніше). Кожне пояснення — окремий commit,
    тож збій AI посеред уроку не губить уже отримані. Ідемпотентно (унікальний ключ)."""
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None or lesson.status != "published":
        return 0, False
    version = lesson.version
    modules = list(
        await session.scalars(
            select(Module)
            .where(Module.lesson_id == lesson.id, _has_text_cards(), ~_has_explanation())
            .join(Lesson, Lesson.id == Module.lesson_id)
            .order_by(Module.part.desc(), Module.position)
        )
    )
    # Пояснення старих версій уроку більше не потрапляють у пакети.
    await session.execute(
        delete(TutorExplanation).where(
            TutorExplanation.lesson_id == lesson.id, TutorExplanation.lesson_version < version
        )
    )
    await session.commit()
    if not modules:
        return 0, False
    grade = await _lesson_grade(session, lesson)
    if grade is None:
        logger.warning("Lesson has no grade for explanations: lesson=%s", lesson.id)
        return 0, False
    subject = await session.scalar(select(Subject.name).where(Subject.id == lesson.subject_id))
    created = 0
    for module in modules:
        text = await module_text(session, module.id)
        if not text:
            continue
        payload: dict[str, Any] = {
            "action": "explain",
            "grade": grade,
            "topic": module.title,
            "topic_id": str(module.id),
            "message": EXPLAIN_PROMPT + text,
        }
        if subject:
            payload["subject"] = subject
        await session.commit()  # без відкритої транзакції на час виклику AI
        try:
            ai = await client.chat(payload)
        except AppError as exc:
            if exc.code == "AI_UNAVAILABLE":
                return created, True
            logger.warning(
                "Explanation skipped: lesson=%s module=%s code=%s", lesson.id, module.id, exc.code
            )
            continue
        if ai.normalized_intent() == "safety" or not ai.reply.strip():
            continue
        inserted = await session.scalar(
            pg_insert(TutorExplanation)
            .values(lesson_id=lesson.id, lesson_version=version, module_id=module.id, text=ai.reply)
            .on_conflict_do_nothing(constraint="uq_tutor_explanation_module")
            .returning(TutorExplanation.id)
        )
        await session.commit()
        created += inserted is not None
    logger.info("Explanations generated: lesson=%s version=%d new=%d", lesson.id, version, created)
    return created, False


async def pack_explanations(
    session: AsyncSession, versions: dict[uuid.UUID, int]
) -> list[dict[str, Any]]:
    """Пояснення для пакета: уроки в їхніх версіях, у порядку уроків пакета й модулів."""
    if not versions:
        return []
    rows = await session.execute(
        select(TutorExplanation, Module.part, Module.position)
        .join(Module, Module.id == TutorExplanation.module_id)
        .where(
            tuple_(TutorExplanation.lesson_id, TutorExplanation.lesson_version).in_(
                list(versions.items())
            )
        )
    )
    order = {lid: i for i, lid in enumerate(versions)}
    items = sorted(
        rows,
        key=lambda r: (order[r[0].lesson_id], 0 if r[1] == "shelter" else 1, r[2]),
    )
    return [
        PackExplanation(
            id=e.id, lesson_id=e.lesson_id, module_id=e.module_id, text=e.text
        ).model_dump(mode="json")
        for e, _, _ in items
    ]
