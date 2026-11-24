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

Кеш пояснень (`tutor_explanation`) адресований вмістом: ключ — sha256 {клас, предмет, назва
модуля, тексти текстових карток, версія промпту} (`explanation_key`), без прив'язки до уроку.
Повторна публікація, копія уроку чи такий самий модуль колеги беруть готове пояснення без
LLM. Типове «Поясни» модуля чи картки (без тексту учня) спершу бере спільне пояснення
(`cached: true`); та сама розмова вдруге — нове пояснення від LLM, кеш не перезаписується.
Кешу ще немає — перший запит іде в LLM під коротким замком Redis на ключ (решта чекають його
відповідь) і зберігає її для всіх. Вільний текст, практика, перевірка, фото й safety не
кешуються ніколи.

Мінімум даних: в AI — клас (номер), предмет, назва модуля, текст картки й репліки учня; без
імені, email, школи. Для `intent: safety` повідомлення учня не зберігається ніде (ні в
історії, ні у відповіді), завдання й підказки не змінюються.
"""

import asyncio
import datetime as dt
import hashlib
import json
import logging
import math
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from redis.asyncio import Redis as AsyncRedis
from redis.exceptions import RedisError
from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.models.lessons import Card, Lesson, Module, Subject
from app.models.school import SchoolClass, User
from app.models.tutor import TutorConversation, TutorExplanation, TutorExplanationAttempt
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
# Скільки невдалих спроб (порожня/safety-відповідь, відхилений запит, урок без класу) на ключ
# пояснення, після чого beat його більше не чіпає.
MAX_EXPLANATION_ATTEMPTS = 3
# Скільки ключів отриманих пояснень пам'ятає розмова.
MAX_EXPLAINED_KEYS = 20
# `last_used_at` пояснення оновлюється не частіше (не пишемо на кожну видачу).
TOUCH_INTERVAL = dt.timedelta(days=1)
# Замок Redis на ключ пояснення: поки перший запит чекає LLM, інші опитують БД і беруть його
# відповідь, а не йдуть у LLM усі разом. Живе таймаут AI + запас; чекають не довше таймауту AI.
EXPLAIN_KEY_LOCK_SLACK_S = 5
EXPLAIN_WAIT_POLL_S = 0.3

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


# ---------- текст матеріалу і ключ кешу ----------


def card_text(card: Card) -> str:
    """Текст картки: `body.text` текстової, підпис (`caption`) картки з медіа."""
    body = card.body if isinstance(card.body, dict) else {}
    value = body.get("text") if card.kind == "text" else body.get("caption")
    return value.strip() if isinstance(value, str) else ""


async def module_texts(session: AsyncSession, module_id: uuid.UUID) -> list[str]:
    """Непорожні тексти текстових карток модуля по порядку."""
    cards = await session.scalars(
        select(Card).where(Card.module_id == module_id, Card.kind == "text").order_by(Card.position)
    )
    return [t for t in (card_text(c) for c in cards) if t]


def _norm(value: str | None) -> str:
    return " ".join((value or "").split())


def explanation_key(
    *,
    grade: int | None,
    subject: str | None,
    title: str,
    texts: Iterable[str],
    prompt_version: str,
) -> str | None:
    """Ключ кешу пояснення: sha256 канонічного JSON усього, що визначає відповідь LLM —
    клас, предмет (назва: коду в довіднику немає), назва модуля, тексти по порядку (пробіли
    нормалізовані), версія промпту. Опис уроку, тести, зображення й id сюди не входять.
    None — тексту немає, пояснювати нічого."""
    normalized = [t for t in (_norm(x) for x in texts) if t]
    if not normalized:
        return None
    data = {
        "grade": grade,
        "subject": _norm(subject),
        "title": _norm(title),
        "texts": normalized,
        "prompt_version": prompt_version,
    }
    raw = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class ModuleMaterial:
    """Модуль уроку для пояснення: тексти й ключ кешу (клас уроку, предмет, версія промпту)."""

    lesson_id: uuid.UUID
    module_id: uuid.UUID
    title: str
    texts: list[str]
    grade: int | None
    subject: str | None
    key: str | None


async def _lesson_grades(
    session: AsyncSession, lessons: list[Lesson]
) -> dict[uuid.UUID, int | None]:
    """Клас уроку; якщо вчитель його не вказав — найменший клас, де урок стоїть у розкладі."""
    grades: dict[uuid.UUID, int | None] = {lesson.id: lesson.grade for lesson in lessons}
    missing = [lesson.id for lesson in lessons if lesson.grade is None]
    if missing:
        scheduled = school_service.scheduled_lessons()
        rows = await session.execute(
            select(scheduled.c.lesson_id, func.min(SchoolClass.grade))
            .join(SchoolClass, SchoolClass.id == scheduled.c.class_id)
            .where(scheduled.c.lesson_id.in_(missing))
            .group_by(scheduled.c.lesson_id)
        )
        grades.update({lesson_id: grade for lesson_id, grade in rows})
    return grades


async def lesson_materials(
    session: AsyncSession, lessons: Iterable[Lesson]
) -> dict[uuid.UUID, list[ModuleMaterial]]:
    """Модулі уроків (спершу укриттєва частина) з текстами й ключами кешу, кілька запитів на
    всі уроки разом."""
    lessons = list(lessons)
    if not lessons:
        return {}
    grades = await _lesson_grades(session, lessons)
    subjects = dict(
        (
            await session.execute(
                select(Subject.id, Subject.name).where(
                    Subject.id.in_({lesson.subject_id for lesson in lessons})
                )
            )
        ).all()
    )
    modules = list(
        await session.scalars(
            select(Module).where(Module.lesson_id.in_([lesson.id for lesson in lessons]))
        )
    )
    modules.sort(key=lambda m: (0 if m.part == "shelter" else 1, m.position))
    texts: dict[uuid.UUID, list[str]] = {}
    if modules:
        cards = await session.scalars(
            select(Card)
            .where(Card.module_id.in_([m.id for m in modules]), Card.kind == "text")
            .order_by(Card.module_id, Card.position)
        )
        for card in cards:
            text = card_text(card)
            if text:
                texts.setdefault(card.module_id, []).append(text)
    prompt_version = get_settings().tutor_prompt_version
    by_id = {lesson.id: lesson for lesson in lessons}
    result: dict[uuid.UUID, list[ModuleMaterial]] = {lesson.id: [] for lesson in lessons}
    for m in modules:
        lesson = by_id[m.lesson_id]
        grade, subject = grades.get(lesson.id), subjects.get(lesson.subject_id)
        module_texts_ = texts.get(m.id, [])
        result[lesson.id].append(
            ModuleMaterial(
                lesson_id=lesson.id,
                module_id=m.id,
                title=m.title,
                texts=module_texts_,
                grade=grade,
                subject=subject,
                key=explanation_key(
                    grade=grade,
                    subject=subject,
                    title=m.title,
                    texts=module_texts_,
                    prompt_version=prompt_version,
                ),
            )
        )
    return result


async def shared_explanation(session: AsyncSession, key: str) -> TutorExplanation | None:
    return await session.scalar(select(TutorExplanation).where(TutorExplanation.cache_key == key))


async def _touch(session: AsyncSession, rows: Iterable[TutorExplanation]) -> None:
    """Позначає пояснення використаними (`last_used_at`), не частіше `TOUCH_INTERVAL`.
    Commit робить викликач."""
    now = dt.datetime.now(dt.UTC)
    ids = [r.id for r in rows if r.last_used_at < now - TOUCH_INTERVAL]
    if ids:
        await session.execute(
            update(TutorExplanation)
            .where(TutorExplanation.id.in_(ids))
            .values(last_used_at=now)
            .execution_options(synchronize_session=False)
        )


async def lessons_with_keys(session: AsyncSession, keys: dict[str, str]) -> list[uuid.UUID]:
    """Опубліковані уроки, у яких є модуль із ключем з `keys` ({ключ: назва модуля}): їхні
    пакети треба перезібрати, коли з'явилося спільне пояснення. Спершу звужуємо за назвою
    модуля (вона входить у ключ)."""
    if not keys:
        return []
    lessons = list(
        await session.scalars(
            select(Lesson)
            .where(
                Lesson.status == "published",
                Lesson.id.in_(select(Module.lesson_id).where(Module.title.in_(set(keys.values())))),
            )
            .order_by(Lesson.id)
        )
    )
    materials = await lesson_materials(session, lessons)
    return [
        lesson_id
        for lesson_id, items in materials.items()
        if any(m.key in keys for m in items if m.key)
    ]


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

    # Спершу визначаємо урок і перевіряємо доступ учня, лише потім звіряємо картку/модуль:
    # будь-яка розбіжність чи чужий об'єкт дає однакову 404, без підказок про зв'язки.
    if body.card_id is not None:
        card = await session.get(Card, body.card_id)
        if card is None:
            raise _not_found("Resource")
        if module_id is not None and module_id != card.module_id:
            raise _not_found("Resource")
        module_id = card.module_id
    if module_id is not None:
        module = await session.get(Module, module_id)
        if module is None:
            raise _not_found("Resource")
        if lesson_id is not None and lesson_id != module.lesson_id:
            raise _not_found("Resource")
        lesson_id = module.lesson_id
    subject = None
    if lesson_id is not None:
        lesson = await session.get(Lesson, lesson_id)
        if lesson is None or not await student_has_lesson(session, student.id, lesson.id):
            raise _not_found("Resource")
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


# ---------- замок на ключ пояснення (онлайн) ----------


@lru_cache
def _redis(url: str) -> AsyncRedis:
    return AsyncRedis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)


def explain_lock_redis(settings: Settings) -> AsyncRedis:
    """Спільний async-клієнт Redis для замків пояснень (тести підміняють)."""
    return _redis(settings.redis_url)


def explain_lock_name(key: str) -> str:
    """Той самий замок бере й Celery-задача пояснень (workers/tutor.py)."""
    return f"tutor:explain:key:{key}"


async def _lock_key(settings: Settings, key: str) -> str | None:
    """Токен — замок взято; None — його тримає інший запит; "" — Redis недоступний
    (fail-open: краще зайвий виклик LLM, ніж помилка учню)."""
    token = uuid.uuid4().hex
    ttl = math.ceil(settings.ai_timeout_s) + EXPLAIN_KEY_LOCK_SLACK_S
    try:
        ok = await explain_lock_redis(settings).set(explain_lock_name(key), token, nx=True, ex=ttl)
    except (RedisError, OSError) as exc:
        logger.warning("Explain key lock unavailable, continuing without it: %s", exc)
        return ""
    return token if ok else None


async def _lock_held(settings: Settings, key: str) -> bool:
    try:
        return bool(await explain_lock_redis(settings).exists(explain_lock_name(key)))
    except (RedisError, OSError):
        return False


async def _unlock_key(settings: Settings, key: str, token: str) -> None:
    try:
        redis = explain_lock_redis(settings)
        value = await redis.get(explain_lock_name(key))
        if isinstance(value, bytes):
            value = value.decode()
        if value == token:
            await redis.delete(explain_lock_name(key))
    except (RedisError, OSError) as exc:
        logger.warning("Explain key unlock failed (expires by TTL): %s", exc)


async def _wait_for_shared(
    session: AsyncSession, settings: Settings, key: str
) -> TutorExplanation | None:
    """Чекає пояснення, яке зараз отримує інший запит. None — той запит завершився без
    пояснення (замок знято) або минув таймаут AI: тоді йдемо в LLM самі."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + settings.ai_timeout_s
    while True:
        await session.commit()  # без відкритої транзакції на час очікування
        await asyncio.sleep(EXPLAIN_WAIT_POLL_S)
        held = await _lock_held(settings, key)
        hit = await shared_explanation(session, key)
        if hit is not None:
            return hit
        if not held or loop.time() >= deadline:
            return None


# ---------- запит до AI ----------


async def _explain_material(
    session: AsyncSession, body: TutorAskRequest, ctx: Context
) -> list[str]:
    """Тексти матеріалу для `explain`: картка (текст чи підпис) або, без картки й без тексту
    учня, текстові картки модуля по порядку."""
    if ctx.card is not None:
        text = card_text(ctx.card)
        return [text] if text else []
    if ctx.module is not None and not body.message:
        return await module_texts(session, ctx.module.id)
    return []


def _explain_message(texts: list[str], question: str | None) -> str | None:
    """`explain`: текст матеріалу (≤ `MAX_CONTEXT_CHARS`) + питання учня, якщо є."""
    material = "\n\n".join(texts)[:MAX_CONTEXT_CHARS]
    if not material:
        return question
    prompt = EXPLAIN_PROMPT + material
    return f"{prompt}\n\nПитання учня: {question}" if question else prompt


async def _fallback_explanation(
    session: AsyncSession,
    body: TutorAskRequest,
    ctx: Context,
    conv: TutorConversation | None,
    key: str | None,
) -> TutorAnswerOut | None:
    """AI недоступний, а учень просив пояснити: пояснення з кешу за ключем запиту, інакше —
    пояснення модуля (те саме, що в пакеті)."""
    if ctx.module is None or ctx.lesson is None:
        return None
    keys = [key] if key else []
    materials = (await lesson_materials(session, [ctx.lesson])).get(ctx.lesson.id, [])
    keys += [m.key for m in materials if m.module_id == ctx.module.id and m.key]
    hit = None
    for k in keys:
        hit = await shared_explanation(session, k)
        if hit is not None:
            break
    if hit is None:
        return None
    return TutorAnswerOut(
        request_id=body.request_id,
        conversation_id=body.conversation_id,
        reply=hit.text,
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
    message = body.message
    key: str | None = None
    if action == "explain":
        texts = await _explain_material(session, body, ctx)
        message = _explain_message(texts, body.message)
        # Кешується лише типове «Поясни» матеріалу модуля: без тексту учня (і без фото —
        # з фото `action` уже `check`).
        if not body.message and ctx.module is not None:
            key = explanation_key(
                grade=ctx.grade,
                subject=ctx.subject,
                title=ctx.module.title,
                texts=texts,
                prompt_version=settings.tutor_prompt_version,
            )
    if message is None and image is None and action is None:
        raise _validation("VALIDATION_ERROR", "message, image_base64 or action is required")
    user_text = message or PLACEHOLDERS[action]

    # Розмова вже отримала це пояснення — «Поясни» ще раз: нове від LLM, кеш не чіпаємо.
    received = list(conv.explained_keys or []) if conv is not None else []
    fresh_key = key if key is not None and key not in received else None
    lock_token: str | None = None
    if fresh_key is not None:
        hit = await shared_explanation(session, fresh_key)
        if hit is None:
            lock_token = await _lock_key(settings, fresh_key)
            if lock_token is None:
                # Інший учень уже питає LLM про цей матеріал: чекаємо його відповідь.
                hit = await _wait_for_shared(session, settings, fresh_key)
        if hit is not None:
            await _touch(session, [hit])
            from_cache = AIChatResponse(reply=hit.text, intent="explain")
            out, _ = await _save(
                session, student, body, ctx, from_cache, user_text, same_topic, fresh_key, True
            )
            return out

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

    try:
        # Транзакцію не тримаємо відкритою на час виклику AI.
        await session.commit()
        try:
            ai = await client.chat(payload)
        except AppError as exc:
            if exc.code == "AI_UNAVAILABLE" and action == "explain":
                fallback = await _fallback_explanation(session, body, ctx, conv, key)
                if fallback is not None:
                    return fallback
            raise
        # Спільне пояснення записується до зняття замка: ті, хто чекає, його побачать.
        out, new_key = await _save(
            session, student, body, ctx, ai, user_text, same_topic, fresh_key, False
        )
    finally:
        if lock_token and fresh_key is not None:
            await _unlock_key(settings, fresh_key, lock_token)
    if new_key is not None and ctx.module is not None:
        await enqueue_pack_rebuilds(session, {new_key: ctx.module.title})
    return out


async def enqueue_pack_rebuilds(session: AsyncSession, keys: dict[str, str]) -> None:
    """Нові спільні пояснення: перезбірка пакетів уроків, модулі яких мають ці ключі (пакет
    збирається детерміновано, тож зайва перезбірка нової версії не дає)."""
    from app.workers.packs import enqueue_rebuild_for_lesson  # цикл імпортів через packs

    lesson_ids = await lessons_with_keys(session, keys)
    await session.commit()
    for lesson_id in lesson_ids:
        await enqueue_rebuild_for_lesson(lesson_id)


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
    fresh_key: str | None,
    cached: bool,
) -> tuple[TutorAnswerOut, str | None]:
    """Записує відповідь у розмову. `fresh_key` — ключ пояснення, якого розмова ще не
    отримувала: розмова його запам'ятовує, а відповідь LLM (`explain`, не порожня) стає
    спільним поясненням. (відповідь, ключ нового спільного пояснення або None)."""
    conv = await _locked_conversation(session, student, body, ctx)
    stored = _stored_reply(conv, body.request_id)
    if stored is not None:
        # Паралельний повтор уже зберіг відповідь — віддаємо її, друга не записується.
        await session.rollback()
        return stored, None

    intent = ai.normalized_intent()
    if ctx.lesson is not None:
        conv.lesson_id = ctx.lesson.id
        conv.module_id = ctx.module.id if ctx.module else None
    if intent != "safety":
        if not same_topic:
            conv.task, conv.hints_used = None, 0
        task = ai.task
        # AI мав би повертати `task` завжди, але на випадок `null` лишаємо збережене завдання.
        if task is None and intent in ("explain", "practice") and conv.task is not None:
            task = conv.task
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
        cached=cached,
    )
    replies = list(conv.replies or []) + [
        {"request_id": str(body.request_id), "response": out.model_dump(mode="json")}
    ]
    conv.replies = replies[-MAX_REPLIES:]
    new_key = None
    if fresh_key is not None and intent == "explain" and ai.reply.strip():
        keys = [k for k in conv.explained_keys or [] if k != fresh_key] + [fresh_key]
        conv.explained_keys = keys[-MAX_EXPLAINED_KEYS:]
        if not cached:
            inserted = await session.scalar(
                pg_insert(TutorExplanation)
                .values(
                    cache_key=fresh_key,
                    prompt_version=get_settings().tutor_prompt_version,
                    text=ai.reply,
                )
                .on_conflict_do_nothing(index_elements=["cache_key"])
                .returning(TutorExplanation.id)
            )
            new_key = fresh_key if inserted is not None else None
    conv.updated_at = dt.datetime.now(dt.UTC)
    await session.commit()
    return out, new_key


# ---------- закешовані пояснення для пакета (B13.3) ----------


async def _existing_keys(session: AsyncSession, keys: Iterable[str]) -> set[str]:
    keys = list(set(keys))
    if not keys:
        return set()
    return set(
        await session.scalars(
            select(TutorExplanation.cache_key).where(TutorExplanation.cache_key.in_(keys))
        )
    )


async def _attempts(
    session: AsyncSession, keys: Iterable[str]
) -> dict[str, tuple[int, dt.datetime]]:
    keys = list(set(keys))
    if not keys:
        return {}
    rows = await session.execute(
        select(
            TutorExplanationAttempt.cache_key,
            TutorExplanationAttempt.attempts,
            TutorExplanationAttempt.last_attempt_at,
        ).where(TutorExplanationAttempt.cache_key.in_(keys))
    )
    return {key: (attempts, at) for key, attempts, at in rows}


async def _record_failed_attempt(session: AsyncSession, key: str) -> None:
    stmt = pg_insert(TutorExplanationAttempt).values(cache_key=key, attempts=1)
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["cache_key"],
            set_={
                "attempts": TutorExplanationAttempt.attempts + 1,
                "last_attempt_at": func.now(),
            },
        )
    )
    await session.commit()


async def _missing(
    session: AsyncSession, materials: list[ModuleMaterial]
) -> tuple[dict[str, ModuleMaterial], dict[str, tuple[int, dt.datetime]]]:
    """Ключі модулів без пояснення, що ще не вичерпали спроб ({ключ: модуль}, без дублів),
    і лічильники спроб."""
    wanted: dict[str, ModuleMaterial] = {}
    for m in materials:
        if m.key is not None:
            wanted.setdefault(m.key, m)
    have = await _existing_keys(session, wanted)
    attempts = await _attempts(session, wanted)
    missing = {
        k: m
        for k, m in wanted.items()
        if k not in have and attempts.get(k, (0,))[0] < MAX_EXPLANATION_ATTEMPTS
    }
    return missing, attempts


async def lessons_missing_explanations(
    session: AsyncSession, limit: int = MISSING_EXPLANATIONS_BATCH
) -> list[uuid.UUID]:
    """Опубліковані уроки, у яких є модуль з текстом без пояснення за його поточним ключем.
    Ключі, що вичерпали `MAX_EXPLANATION_ATTEMPTS` невдалих спроб, не враховуються. Спершу
    уроки без спроб чи з найдавнішою спробою, далі новіші: старі проблемні уроки не
    заважають новим."""
    lessons = list(await session.scalars(select(Lesson).where(Lesson.status == "published")))
    materials = await lesson_materials(session, lessons)
    missing, attempts = await _missing(session, [m for ms in materials.values() for m in ms])
    if not missing:
        return []
    by_id = {lesson.id: lesson for lesson in lessons}
    found: dict[uuid.UUID, dt.datetime | None] = {}
    for lesson_id, items in materials.items():
        keys = {m.key for m in items if m.key in missing}
        if not keys:
            continue
        tried = [attempts[k][1] for k in keys if k in attempts]
        found[lesson_id] = max(tried) if tried else None

    epoch = dt.datetime.min.replace(tzinfo=dt.UTC)

    def order(lesson_id: uuid.UUID) -> tuple[Any, ...]:
        last = found[lesson_id]
        published = by_id[lesson_id].published_at
        return (
            last is not None,
            last or epoch,
            published is None,
            -(published or epoch).timestamp(),
            str(lesson_id),
        )

    return sorted(found, key=order)[:limit]


KeyLock = tuple[Callable[[str], str | None], Callable[[str, str], None]]


async def generate_explanations(
    session: AsyncSession,
    lesson_id: uuid.UUID,
    client: AIClient,
    key_lock: KeyLock | None = None,
) -> tuple[dict[str, str], bool]:
    """Пояснення модулів опублікованого уроку, яких ще немає в кеші за їхнім ключем
    ({новий ключ: назва модуля}, AI недоступний — повторити пізніше). Модулі з уже відомим
    ключем (повторна публікація, копія, такий самий модуль колеги) LLM не викликають. Кожне
    пояснення — окремий commit, тож збій AI посеред уроку не губить уже отримані.
    `key_lock` — (взяти, зняти) замок на ключ, спільний з онлайн-запитами: зайнятий ключ
    пропускаємо (його вже генерують)."""
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None or lesson.status != "published":
        return {}, False
    materials = (await lesson_materials(session, [lesson]))[lesson.id]
    todo, _ = await _missing(session, materials)
    await session.commit()
    created: dict[str, str] = {}
    for key, module in todo.items():
        if module.grade is None:
            logger.warning("Lesson has no grade for explanations: lesson=%s", lesson.id)
            await _record_failed_attempt(session, key)
            continue
        token = key_lock[0](key) if key_lock else ""
        if token is None:
            logger.info("Explanation in progress elsewhere: module=%s", module.module_id)
            continue
        try:
            payload: dict[str, Any] = {
                "action": "explain",
                "grade": module.grade,
                "topic": module.title,
                "topic_id": str(module.module_id),
                "message": _explain_message(module.texts, None),
            }
            if module.subject:
                payload["subject"] = module.subject
            await session.commit()  # без відкритої транзакції на час виклику AI
            try:
                ai = await client.chat(payload)
            except AppError as exc:
                if exc.code == "AI_UNAVAILABLE":
                    return created, True
                logger.warning(
                    "Explanation skipped: lesson=%s module=%s code=%s",
                    lesson.id,
                    module.module_id,
                    exc.code,
                )
                await _record_failed_attempt(session, key)
                continue
            if ai.normalized_intent() == "safety" or not ai.reply.strip():
                await _record_failed_attempt(session, key)
                continue
            inserted = await session.scalar(
                pg_insert(TutorExplanation)
                .values(
                    cache_key=key,
                    prompt_version=get_settings().tutor_prompt_version,
                    text=ai.reply,
                )
                .on_conflict_do_nothing(index_elements=["cache_key"])
                .returning(TutorExplanation.id)
            )
            await session.commit()
            if inserted is not None:
                created[key] = module.title
        finally:
            if token and key_lock:
                key_lock[1](key, token)
    logger.info(
        "Explanations generated: lesson=%s version=%d new=%d",
        lesson.id,
        lesson.version,
        len(created),
    )
    return created, False


async def pack_explanations(
    session: AsyncSession, modules: list[ModuleMaterial]
) -> list[dict[str, Any]]:
    """Пояснення для пакета: за поточним ключем кожного модуля (`lesson_materials` уроків
    пакета, у їхньому порядку). Модулі без пояснення пропускаються (решта йдуть); коли
    пояснення з'явиться, перезбірка дасть нову версію пакета. Видача позначає пояснення
    використаними."""
    keys = {m.key for m in modules if m.key}
    if not keys:
        return []
    rows = {
        e.cache_key: e
        for e in await session.scalars(
            select(TutorExplanation).where(TutorExplanation.cache_key.in_(keys))
        )
    }
    await _touch(session, rows.values())
    result = []
    for m in modules:
        e = rows.get(m.key) if m.key else None
        if e is not None:
            result.append(
                PackExplanation(
                    id=e.id, lesson_id=m.lesson_id, module_id=m.module_id, text=e.text
                ).model_dump(mode="json")
            )
    return result


async def current_keys(session: AsyncSession) -> set[str]:
    """Ключі модулів усіх опублікованих уроків (поточні клас, вміст, версія промпту)."""
    lessons = list(await session.scalars(select(Lesson).where(Lesson.status == "published")))
    materials = await lesson_materials(session, lessons)
    return {m.key for items in materials.values() for m in items if m.key}


async def purge_explanations(
    session: AsyncSession, settings: Settings, now: dt.datetime
) -> tuple[int, int]:
    """Строк зберігання кешу: пояснення, не використані `RETENTION_TUTOR_EXPLANATION_DAYS`,
    і спроби, старші за цей строк, — якщо їхній ключ не потрібен жодному модулю
    опублікованого уроку. Зміна версії промпту робить старі ключі непотрібними, тож вони
    йдуть самі. (пояснень, спроб); commit робить викликач."""
    before = now - dt.timedelta(days=settings.retention_tutor_explanation_days)
    stale = (
        await session.execute(
            select(TutorExplanation.id, TutorExplanation.cache_key).where(
                TutorExplanation.last_used_at < before
            )
        )
    ).all()
    stale_attempts = list(
        await session.scalars(
            select(TutorExplanationAttempt.cache_key).where(
                TutorExplanationAttempt.last_attempt_at < before
            )
        )
    )
    if not stale and not stale_attempts:
        return 0, 0
    keep = await current_keys(session)
    ids = [i for i, key in stale if key not in keep]
    attempt_keys = [key for key in stale_attempts if key not in keep]
    if ids:
        await session.execute(delete(TutorExplanation).where(TutorExplanation.id.in_(ids)))
    if attempt_keys:
        await session.execute(
            delete(TutorExplanationAttempt).where(
                TutorExplanationAttempt.cache_key.in_(attempt_keys)
            )
        )
    return len(ids), len(attempt_keys)
