"""Предмети, уроки вчителя (модулі, картки, тести, питання), публікація й розміри для пакета.

Правила:
- писати урок і його вміст може лише автор (вчитель); адмін і інші вчителі школи лише читають;
- опублікований урок незмінний: щоб змінити, вчитель знімає його з публікації (`unpublish`),
  редагує і публікує знову — повторна публікація збільшує `version` (B6.4);
- публікація проходить серверні перевірки (укриттєва частина, субтитри до відео, розмір);
- порядок модулів, карток і питань змінюється пакетно (`reorder_*`): позиції стають 1..n;
- копія уроку (`copy_lesson`) — нова чернетка того, хто копіює, з тими самими id-зв'язками,
  але новими id (uuid5 від id копії), тож повтор копіювання нічого не дублює.
"""

import datetime as dt
import uuid
from collections.abc import Iterable
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, Text, cast, delete, exists, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.storage import MediaStorage
from app.models.lessons import Card, Lesson, MediaAsset, Module, Question, Subject, Test
from app.models.school import ScheduleOverride, SchoolClass, User
from app.models.sync import ModuleProgress
from app.schemas.lessons import (
    CardCreate,
    CardMediaOut,
    CardOut,
    CardUpdate,
    ItemOrder,
    LessonCopy,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    ModuleCreate,
    ModuleOrder,
    ModuleOut,
    ModuleUpdate,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    SubjectCreate,
    TestCreate,
    TestOut,
    TestUpdate,
)
from app.services.idempotency import insert_or_get, integrity_errors
from app.services.media import media_out
from app.services.schedule import DEFAULT_TZ


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _not_found(what: str) -> AppError:
    return AppError("NOT_FOUND", f"{what} not found", status_code=404)


def _forbidden() -> AppError:
    return AppError("FORBIDDEN", "No access to this lesson", status_code=403)


def _position_taken() -> AppError:
    return AppError("POSITION_TAKEN", "Position is already taken", status_code=409)


def _validation(message: str) -> AppError:
    return AppError("VALIDATION_ERROR", message, status_code=422)


_POSITION_ERRORS = {
    "uq_module_lesson_part_position": _position_taken(),
    "uq_card_module_position": _position_taken(),
    "uq_question_test_position": _position_taken(),
}


# ---------- предмети ----------


async def list_subjects(session: AsyncSession, school_id: uuid.UUID | None) -> list[Subject]:
    return list(
        await session.scalars(
            select(Subject)
            .where(or_(Subject.school_id.is_(None), Subject.school_id == school_id))
            .order_by(Subject.name, Subject.id)
        )
    )


async def create_subject(
    session: AsyncSession, admin: User, body: SubjectCreate
) -> tuple[Subject, bool]:
    subject, created = await insert_or_get(
        session, Subject, {"id": body.id, "school_id": admin.school_id, "name": body.name}
    )
    await session.commit()
    return subject, created


async def check_subject(session: AsyncSession, subject_id: uuid.UUID, school_id) -> None:
    """Предмет має бути загальним (school_id NULL) або належати школі."""
    subject = await session.get(Subject, subject_id)
    if subject is None or subject.school_id not in (None, school_id):
        raise _not_found("Subject")


# ---------- доступ до уроку ----------


async def _author_school(session: AsyncSession, lesson: Lesson) -> uuid.UUID | None:
    return await session.scalar(select(User.school_id).where(User.id == lesson.author_id))


async def get_readable_lesson(session: AsyncSession, user: User, lesson_id: uuid.UUID) -> Lesson:
    """Автор, а також вчителі й адміністрація школи автора (лише читання)."""
    lesson = await session.get(Lesson, lesson_id)
    if lesson is None:
        raise _not_found("Lesson")
    if lesson.author_id == user.id:
        return lesson
    if (
        user.role in ("teacher", "admin")
        and user.school_id is not None
        and await _author_school(session, lesson) == user.school_id
    ):
        return lesson
    raise _forbidden()


async def get_editable_lesson(
    session: AsyncSession, user: User, lesson_id: uuid.UUID, *, require_draft: bool = True
) -> Lesson:
    """Урок для зміни: лише автор. Рядок блокується до commit, щоб зміна вмісту
    й публікація не перетиналися."""
    lesson = await session.scalar(
        select(Lesson)
        .where(Lesson.id == lesson_id)
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )
    if lesson is None:
        raise _not_found("Lesson")
    if lesson.author_id != user.id:
        raise _forbidden()
    if require_draft and lesson.status == "published":
        raise AppError(
            "LESSON_PUBLISHED",
            "Published lesson is read-only; unpublish it to edit",
            status_code=409,
        )
    return lesson


async def get_editable_module(session: AsyncSession, user: User, module_id: uuid.UUID) -> Module:
    module = await session.get(Module, module_id)
    if module is None:
        raise _not_found("Module")
    await get_editable_lesson(session, user, module.lesson_id)
    return module


async def get_editable_card(session: AsyncSession, user: User, card_id: uuid.UUID) -> Card:
    card = await session.get(Card, card_id)
    if card is None:
        raise _not_found("Card")
    await get_editable_module(session, user, card.module_id)
    return card


async def get_editable_test(session: AsyncSession, user: User, test_id: uuid.UUID) -> Test:
    test = await session.get(Test, test_id)
    if test is None:
        raise _not_found("Test")
    await get_editable_lesson(session, user, test.lesson_id)
    return test


async def get_editable_question(
    session: AsyncSession, user: User, question_id: uuid.UUID
) -> Question:
    question = await session.get(Question, question_id)
    if question is None:
        raise _not_found("Question")
    await get_editable_test(session, user, question.test_id)
    return question


# ---------- урок ----------


async def list_lessons(session: AsyncSession, user: User, status: str | None) -> list[Lesson]:
    """Вчитель — свої уроки, адмін — уроки вчителів своєї школи."""
    query = select(Lesson).order_by(Lesson.updated_at.desc(), Lesson.id)
    if user.role == "admin":
        query = query.join(User, User.id == Lesson.author_id).where(
            User.school_id == user.school_id
        )
    else:
        query = query.where(Lesson.author_id == user.id)
    if status:
        query = query.where(Lesson.status == status)
    return list(await session.scalars(query))


async def create_lesson(
    session: AsyncSession, teacher: User, body: LessonCreate
) -> tuple[Lesson, bool]:
    await check_subject(session, body.subject_id, teacher.school_id)
    lesson, created = await insert_or_get(
        session, Lesson, {**body.model_dump(), "author_id": teacher.id}
    )
    await session.commit()
    return lesson, created


def _apply(obj: Any, data: dict[str, Any], required: Iterable[str]) -> None:
    for field in required:
        if field in data and data[field] is None:
            raise _validation(f"{field} cannot be null")
    for field, value in data.items():
        setattr(obj, field, value)


async def update_lesson(
    session: AsyncSession, teacher: User, lesson: Lesson, body: LessonUpdate
) -> Lesson:
    data = body.model_dump(exclude_unset=True)
    if data.get("subject_id") is not None:
        await check_subject(session, data["subject_id"], teacher.school_id)
    _apply(lesson, data, ("subject_id", "title", "shelter_part", "main_part"))
    await session.commit()
    return lesson


async def _has_progress(session: AsyncSession, modules_filter: Any) -> bool:
    """Прогрес учнів у модулях — результати: `module_progress` видаляється каскадом від модуля,
    тож без цієї перевірки видалення модуля чи уроку тихо стерло б прогрес (а офлайн-події
    до нього стали б `unknown_entity`). Модулі блокуються FOR UPDATE: вставка прогресу тримає
    на рядку модуля FOR KEY SHARE, тож паралельна синхронізація або закомітиться до перевірки,
    або чекатиме на видалення."""
    await session.execute(select(Module.id).where(modules_filter).with_for_update())
    return bool(
        await session.scalar(
            select(
                exists().where(
                    ModuleProgress.module_id.in_(select(Module.id).where(modules_filter))
                )
            )
        )
    )


async def delete_lesson(session: AsyncSession, lesson: Lesson) -> None:
    """Лише чернетку, на яку ніщо не посилається (розклад, спроби, пакети)."""
    in_use = AppError(
        "LESSON_IN_USE",
        "Lesson is scheduled or has results and cannot be deleted",
        status_code=409,
    )
    if await _has_progress(session, Module.lesson_id == lesson.id):
        raise in_use
    # Надгробки видалених додаткових уроків не тримають урок: після видалення уроку повтор
    # їхнього створення однаково отримає 404 (уроку немає), а не воскресить урок.
    await session.execute(
        delete(ScheduleOverride).where(
            ScheduleOverride.lesson_id == lesson.id, ScheduleOverride.deleted_at.is_not(None)
        )
    )
    async with integrity_errors(session, {"fk_": in_use}):
        await session.delete(lesson)
    await session.commit()


async def card_outs(
    session: AsyncSession, storage: MediaStorage, cards: list[Card]
) -> list[CardOut]:
    """Картки для редактора: з медіа (URL, тип, розмір) і субтитрами відео — одним запитом."""
    media_ids = {c.media_asset_id for c in cards if c.media_asset_id is not None}
    media: dict[uuid.UUID, MediaAsset] = {}
    if media_ids:
        subtitle_ids = select(MediaAsset.subtitles_id).where(MediaAsset.id.in_(media_ids))
        media = {
            m.id: m
            for m in await session.scalars(
                select(MediaAsset).where(
                    or_(MediaAsset.id.in_(media_ids), MediaAsset.id.in_(subtitle_ids))
                )
            )
        }
    out = []
    for c in cards:
        card = CardOut.model_validate(c)
        m = media.get(c.media_asset_id) if c.media_asset_id else None
        if m is not None:
            subtitles = media.get(m.subtitles_id) if m.subtitles_id else None
            card.media = CardMediaOut(
                **media_out(m, storage).model_dump(),
                subtitles=media_out(subtitles, storage) if subtitles is not None else None,
            )
        out.append(card)
    return out


async def lesson_out(
    session: AsyncSession,
    lesson: Lesson,
    storage: MediaStorage,
    settings: Settings | None = None,
) -> LessonOut:
    """Урок повністю для редактора: картки з медіа, розмір уроку й ліміт."""
    # updated_at (onupdate) після зміни прострочений: перечитуємо рядок явно, не ліниво.
    await session.refresh(lesson)
    modules = list(
        await session.scalars(
            select(Module)
            .where(Module.lesson_id == lesson.id)
            .order_by(Module.part.desc(), Module.position)  # shelter перед main
        )
    )
    cards = list(
        await session.scalars(
            select(Card).where(Card.module_id.in_([m.id for m in modules])).order_by(Card.position)
        )
    )
    tests = list(
        await session.scalars(
            select(Test).where(Test.lesson_id == lesson.id).order_by(Test.created_at, Test.id)
        )
    )
    questions = list(
        await session.scalars(
            select(Question)
            .where(Question.test_id.in_([t.id for t in tests]))
            .order_by(Question.position)
        )
    )
    out = LessonOut.model_validate(lesson)
    card_list = await card_outs(session, storage, cards)
    out.modules = [
        ModuleOut.model_validate(m).model_copy(
            update={"cards": [c for c in card_list if c.module_id == m.id]}
        )
        for m in modules
    ]
    out.tests = [
        TestOut.model_validate(t).model_copy(
            update={
                "questions": [QuestionOut.model_validate(q) for q in questions if q.test_id == t.id]
            }
        )
        for t in tests
    ]
    out.size_bytes = await pack_size(session, {lesson.id})
    out.limit_bytes = (settings or get_settings()).pack_max_day_bytes
    out.warnings = await publish_warnings(session, lesson)
    return out


# ---------- модулі, картки, тести, питання ----------


async def create_module(
    session: AsyncSession, lesson: Lesson, body: ModuleCreate
) -> tuple[Module, bool]:
    module, created = await insert_or_get(
        session,
        Module,
        {**body.model_dump(), "lesson_id": lesson.id},
        constraint_errors=_POSITION_ERRORS,
    )
    await session.commit()
    return module, created


async def update_module(session: AsyncSession, module: Module, body: ModuleUpdate) -> Module:
    async with integrity_errors(session, _POSITION_ERRORS):
        _apply(module, body.model_dump(exclude_unset=True), ModuleUpdate.model_fields)
    await session.commit()
    return module


async def _check_card_media(
    session: AsyncSession, user: User, kind: str, media_id: uuid.UUID | None
) -> None:
    if media_id is None:
        return
    media = await session.get(MediaAsset, media_id)
    # Лише власні файли вчителя: чужий id не розкриває, чи існує файл.
    if media is None or media.uploaded_by != user.id:
        raise _not_found("Media")
    if media.kind != kind:
        raise _validation(f"Card kind {kind} does not match media kind {media.kind}")


async def create_card(
    session: AsyncSession, user: User, module: Module, body: CardCreate
) -> tuple[Card, bool]:
    await _check_card_media(session, user, body.kind, body.media_asset_id)
    card, created = await insert_or_get(
        session,
        Card,
        {**body.model_dump(), "module_id": module.id},
        constraint_errors=_POSITION_ERRORS,
    )
    await session.commit()
    return card, created


async def update_card(session: AsyncSession, user: User, card: Card, body: CardUpdate) -> Card:
    data = body.model_dump(exclude_unset=True)
    merged = {f: data.get(f, getattr(card, f)) for f in ("position", "kind", "body")}
    merged["media_asset_id"] = data.get("media_asset_id", card.media_asset_id)
    try:
        CardCreate(id=card.id, **merged)
    except ValueError as exc:
        raise _validation(str(exc).splitlines()[-1].strip()) from exc
    if "media_asset_id" in data or "kind" in data:
        await _check_card_media(session, user, merged["kind"], merged["media_asset_id"])
    async with integrity_errors(session, _POSITION_ERRORS):
        _apply(card, data, ("position", "kind", "body"))
    await session.commit()
    return card


async def create_test(session: AsyncSession, lesson: Lesson, body: TestCreate) -> tuple[Test, bool]:
    test, created = await insert_or_get(
        session, Test, {**body.model_dump(), "lesson_id": lesson.id}
    )
    await session.commit()
    return test, created


async def update_test(session: AsyncSession, test: Test, body: TestUpdate) -> Test:
    data = body.model_dump(exclude_unset=True)
    merged = {f: data.get(f, getattr(test, f)) for f in ("title", "window_enabled", "window_hours")}
    if merged["window_enabled"] is None:
        raise _validation("window_enabled cannot be null")
    try:
        TestCreate(id=test.id, **merged)
    except ValueError as exc:
        raise _validation(str(exc).splitlines()[-1].strip()) from exc
    _apply(test, data, ("title", "window_enabled"))
    await session.commit()
    return test


def _question_values(body: QuestionCreate) -> dict[str, Any]:
    return body.model_dump()


async def create_question(
    session: AsyncSession, test: Test, body: QuestionCreate
) -> tuple[Question, bool]:
    question, created = await insert_or_get(
        session,
        Question,
        {**_question_values(body), "test_id": test.id},
        constraint_errors=_POSITION_ERRORS,
    )
    await session.commit()
    return question, created


async def update_question(
    session: AsyncSession, question: Question, body: QuestionUpdate
) -> Question:
    data = body.model_dump(exclude_unset=True)
    fields = (
        "position",
        "kind",
        "prompt",
        "options",
        "right_options",
        "answer_key",
        "points",
        "explanation",
    )
    merged = {f: data[f] if f in data else getattr(question, f) for f in fields}
    for f in ("position", "kind", "prompt", "options", "answer_key", "points"):
        if merged[f] is None:
            raise _validation(f"{f} cannot be null")
    # Питання перестало бути `match`: праві елементи без явного значення прибираються.
    if merged["kind"] != "match" and "right_options" not in data:
        merged["right_options"] = None
    try:
        checked = QuestionCreate(id=question.id, **merged)
    except ValueError as exc:
        raise _validation(str(exc).splitlines()[-1].strip()) from exc
    values = _question_values(checked)
    async with integrity_errors(session, _POSITION_ERRORS):
        for f in fields:
            setattr(question, f, values[f])
    await session.commit()
    return question


async def delete_child(session: AsyncSession, obj: Module | Card | Test | Question) -> None:
    in_use = AppError("IN_USE", "Item has student results", status_code=409)
    if isinstance(obj, Module) and await _has_progress(session, Module.id == obj.id):
        raise in_use
    async with integrity_errors(session, {"fk_": in_use}):
        await session.delete(obj)
    await session.commit()


# ---------- порядок ----------


def _order_mismatch(current: list[uuid.UUID], wanted: list[uuid.UUID]) -> AppError | None:
    """`ids` мають бути рівно поточним набором, кожен раз (інакше хтось змінив склад
    паралельно, і новий порядок неоднозначний)."""
    duplicates = sorted({str(i) for i in wanted if wanted.count(i) > 1})
    missing = sorted(str(i) for i in set(current) - set(wanted))
    unknown = sorted(str(i) for i in set(wanted) - set(current))
    if not (duplicates or missing or unknown):
        return None
    return AppError(
        "ORDER_MISMATCH",
        "ids must list every current item exactly once",
        status_code=422,
        details={"missing": missing, "unknown": unknown, "duplicates": duplicates},
    )


async def _reorder(session: AsyncSession, model: Any, parent_filter: Any, ids: list[uuid.UUID]):
    """Позиції 1..n у порядку `ids` однією транзакцією. UNIQUE (батько, позиція) не
    відкладений, тож спершу всі позиції зсуваються за межі допустимих (> 1000), потім
    ставляться остаточні. Повтор того самого порядку нічого не змінює (позиції вже такі)."""
    rows = list(
        await session.scalars(
            select(model).where(parent_filter).order_by(model.position).with_for_update()
        )
    )
    error = _order_mismatch([r.id for r in rows], ids)
    if error is not None:
        raise error
    by_id = {r.id: r for r in rows}
    if all(by_id[item_id].position == pos for pos, item_id in enumerate(ids, start=1)):
        return [by_id[i] for i in ids]
    await session.execute(
        update(model).where(parent_filter).values(position=model.position + _POSITION_SHIFT)
    )
    for pos, item_id in enumerate(ids, start=1):
        await session.execute(update(model).where(model.id == item_id).values(position=pos))
    await session.commit()
    return list(
        await session.scalars(
            select(model)
            .where(parent_filter)
            .order_by(model.position)
            .execution_options(populate_existing=True)
        )
    )


# Більше за максимальну позицію (1000) + кількість елементів; вміщається в SMALLINT.
_POSITION_SHIFT = 2000


async def reorder_modules(session: AsyncSession, lesson: Lesson, body: ModuleOrder) -> list[Module]:
    return await _reorder(
        session, Module, (Module.lesson_id == lesson.id) & (Module.part == body.part), body.ids
    )


async def reorder_cards(session: AsyncSession, module: Module, body: ItemOrder) -> list[Card]:
    return await _reorder(session, Card, Card.module_id == module.id, body.ids)


async def reorder_questions(session: AsyncSession, test: Test, body: ItemOrder) -> list[Question]:
    return await _reorder(session, Question, Question.test_id == test.id, body.ids)


# ---------- копія уроку ----------


def _copy_id(lesson_id: uuid.UUID, kind: str, source_id: uuid.UUID) -> uuid.UUID:
    """Id елемента копії: детерміновано від id копії, тож повтор дає ті самі id."""
    return uuid.uuid5(lesson_id, f"{kind}:{source_id}")


def _row(obj: Any, skip: Iterable[str] = ()) -> dict[str, Any]:
    columns = obj.__table__.columns.keys()
    return {c: getattr(obj, c) for c in columns if c not in ("created_at", "updated_at", *skip)}


async def _copy_media(
    session: AsyncSession, user: User, lesson_id: uuid.UUID, media_ids: set[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """Медіа карток для копії: власні файли вчителя — як є; чужі (колеги зі школи) — нові записи
    вчителя на той самий файл (`storage_key`), без копіювання файла. Тож вчитель може міняти
    субтитри й далі перевикористовувати медіа в картках копії (лише власні медіа)."""
    if not media_ids:
        return {}
    media = {
        m.id: m
        for m in await session.scalars(select(MediaAsset).where(MediaAsset.id.in_(media_ids)))
    }
    foreign = {m.id for m in media.values() if m.uploaded_by != user.id}
    subtitle_ids = {media[i].subtitles_id for i in foreign if media[i].subtitles_id is not None}
    if subtitle_ids:
        media.update(
            {
                m.id: m
                for m in await session.scalars(
                    select(MediaAsset).where(MediaAsset.id.in_(subtitle_ids))
                )
            }
        )
    mapping = {i: i for i in media_ids if i not in foreign}
    for i in foreign | {s for s in subtitle_ids if media[s].uploaded_by != user.id}:
        mapping[i] = _copy_id(lesson_id, "media", i)
    # Спершу субтитри: відео посилається на них.
    for group in (subtitle_ids, foreign):
        for i in sorted(group):
            if mapping.get(i, i) == i:
                continue
            values = _row(media[i], skip=("id",))
            values.update(id=mapping[i], uploaded_by=user.id)
            if values["subtitles_id"] is not None:
                values["subtitles_id"] = mapping.get(values["subtitles_id"], values["subtitles_id"])
            await session.execute(
                pg_insert(MediaAsset).values(**values).on_conflict_do_nothing(index_elements=["id"])
            )
    return mapping


async def copy_lesson(
    session: AsyncSession, user: User, source: Lesson, body: LessonCopy
) -> tuple[Lesson, bool]:
    """Глибока копія уроку (модулі, картки, тести, питання) у нову чернетку `user`.
    Ідемпотентно за `body.id`: повтор (той самий автор і джерело) повертає наявну копію, навіть
    якщо її вже редагували; інший урок під цим id — 409 ID_CONFLICT."""
    await check_subject(session, source.subject_id, user.school_id)
    lesson, created = await insert_or_get(
        session,
        Lesson,
        {
            "id": body.id,
            "subject_id": source.subject_id,
            "author_id": user.id,
            "title": body.title or source.title,
            "shelter_part": source.shelter_part,
            "main_part": source.main_part,
            "grade": source.grade,
            "copied_from_id": source.id,
        },
        compare=["author_id", "copied_from_id"],
    )
    if not created:
        await session.commit()
        return lesson, False

    new_id = lesson.id
    modules = list(await session.scalars(select(Module).where(Module.lesson_id == source.id)))
    cards = list(
        await session.scalars(select(Card).where(Card.module_id.in_([m.id for m in modules])))
    )
    tests = list(await session.scalars(select(Test).where(Test.lesson_id == source.id)))
    questions = list(
        await session.scalars(select(Question).where(Question.test_id.in_([t.id for t in tests])))
    )
    media = await _copy_media(
        session, user, new_id, {c.media_asset_id for c in cards if c.media_asset_id}
    )

    if modules:
        await session.execute(
            insert(Module),
            [
                {
                    **_row(m),
                    "id": _copy_id(new_id, "module", m.id),
                    "lesson_id": new_id,
                }
                for m in modules
            ],
        )
    if cards:
        await session.execute(
            insert(Card),
            [
                {
                    **_row(c),
                    "id": _copy_id(new_id, "card", c.id),
                    "module_id": _copy_id(new_id, "module", c.module_id),
                    "media_asset_id": media.get(c.media_asset_id) if c.media_asset_id else None,
                }
                for c in cards
            ],
        )
    if tests:
        await session.execute(
            insert(Test),
            [
                # created_at джерела: тести уроку впорядковані за ним, порядок копії той самий.
                {
                    **_row(t),
                    "id": _copy_id(new_id, "test", t.id),
                    "lesson_id": new_id,
                    "created_at": t.created_at,
                }
                for t in tests
            ],
        )
    if questions:
        await session.execute(
            insert(Question),
            [
                {
                    **_row(q),
                    "id": _copy_id(new_id, "question", q.id),
                    "test_id": _copy_id(new_id, "test", q.test_id),
                }
                for q in questions
            ],
        )
    await session.commit()
    return lesson, True


# ---------- розміри (ліміт уроку й пакета дня) ----------


async def _text_bytes(session: AsyncSession, ids: set[uuid.UUID]) -> int:
    """Приблизний розмір тексту уроків у пакеті: поля уроку, модулів, карток, тестів, питань."""
    ln = func.octet_length
    parts = [
        select(ln(Lesson.title) + ln(Lesson.shelter_part) + ln(Lesson.main_part)).where(
            Lesson.id.in_(ids)
        ),
        select(ln(Module.title)).where(Module.lesson_id.in_(ids)),
        select(ln(cast(Card.body, Text)))
        .join(Module, Module.id == Card.module_id)
        .where(Module.lesson_id.in_(ids)),
        select(ln(Test.title)).where(Test.lesson_id.in_(ids)),
        select(
            ln(Question.prompt)
            + ln(cast(Question.options, Text))
            + ln(cast(Question.answer_key, Text))
            + func.coalesce(ln(cast(Question.right_options, Text)), 0)
            + func.coalesce(ln(Question.explanation), 0)
        )
        .join(Test, Test.id == Question.test_id)
        .where(Test.lesson_id.in_(ids)),
    ]
    total = 0
    for q in parts:
        sub = q.subquery()
        total += await session.scalar(select(func.coalesce(func.sum(sub.c[0]), 0))) or 0
    return int(total)


async def media_size(session: AsyncSession, media_ids: Iterable[uuid.UUID] | Select) -> int:
    """Розмір медіа разом з їхніми субтитрами; кожен файл рахується один раз — і той, що
    спільний для кількох записів з однаковим вмістом (один `storage_key`)."""
    subtitle_ids = select(MediaAsset.subtitles_id).where(
        MediaAsset.id.in_(media_ids), MediaAsset.subtitles_id.is_not(None)
    )
    # Відео, яке ще стискається (оригінал до 300 МБ) чи не стиснулось, не рахується: у пакет
    # воно не потрапить, а урок із ним не опублікується (`video_processing`, `video_failed`).
    files = (
        select(func.max(MediaAsset.size_bytes).label("size_bytes"))
        .where(
            or_(MediaAsset.id.in_(media_ids), MediaAsset.id.in_(subtitle_ids)),
            MediaAsset.processing_status == "ready",
        )
        .group_by(MediaAsset.storage_key)
        .subquery()
    )
    total = await session.scalar(select(func.coalesce(func.sum(files.c.size_bytes), 0)))
    return int(total or 0)


async def _media_bytes(session: AsyncSession, ids: set[uuid.UUID]) -> int:
    """Унікальні медіа карток уроків + їхні субтитри (файл, спільний для уроків, — один раз)."""
    media_ids = (
        select(Card.media_asset_id)
        .join(Module, Module.id == Card.module_id)
        .where(Module.lesson_id.in_(ids), Card.media_asset_id.is_not(None))
    )
    return await media_size(session, media_ids)


async def pack_size(session: AsyncSession, lesson_ids: set[uuid.UUID]) -> int:
    if not lesson_ids:
        return 0
    return await _text_bytes(session, lesson_ids) + await _media_bytes(session, lesson_ids)


# ---------- публікація ----------


async def publish_warnings(session: AsyncSession, lesson: Lesson) -> list[dict[str, Any]]:
    """Зауваження, які не блокують публікацію: відео без VTT-субтитрів (тихий режим краще з
    субтитрами, але вчитель може не встигнути їх зробити)."""
    subtitles = MediaAsset.__table__.alias("subtitles")
    rows = await session.execute(
        select(Card.id, Card.media_asset_id, Module.id)
        .join(Module, Module.id == Card.module_id)
        .join(MediaAsset, MediaAsset.id == Card.media_asset_id)
        .outerjoin(subtitles, subtitles.c.id == MediaAsset.subtitles_id)
        .where(
            Module.lesson_id == lesson.id,
            MediaAsset.kind == "video",
            or_(subtitles.c.id.is_(None), subtitles.c.kind != "subtitles"),
        )
        .order_by(Card.id)
    )
    return [
        {
            "check": "video_subtitles",
            "message": "Video has no VTT subtitles",
            "module_id": str(module_id),
            "card_id": str(card_id),
            "media_asset_id": str(media_id),
        }
        for card_id, media_id, module_id in rows
    ]


async def publish_problems(
    session: AsyncSession, lesson: Lesson, settings: Settings
) -> list[dict[str, Any]]:
    """Усі перевірки перед публікацією; порожній список — можна публікувати."""
    problems: list[dict[str, Any]] = []
    # Лише пунктуація («***») — теж порожній текст: учневі в укритті нічого читати.
    if not any(ch.isalnum() for ch in lesson.shelter_part):
        problems.append(
            {"check": "shelter_part", "message": "Lesson has no shelter part (shelter_part)"}
        )

    has_module = await session.scalar(select(exists().where(Module.lesson_id == lesson.id)))
    if not has_module:
        problems.append({"check": "modules", "message": "Lesson has no modules"})

    # Тест без питань учень не може завершити — урок ніколи не стане «пройдено».
    empty_tests = await session.scalars(
        select(Test.id)
        .where(Test.lesson_id == lesson.id, ~exists().where(Question.test_id == Test.id))
        .order_by(Test.id)
    )
    for test_id in empty_tests:
        problems.append(
            {"check": "test_questions", "message": "Test has no questions", "test_id": str(test_id)}
        )

    # Відео, яке ще стискає сервер або не стиснулось: файла для пакета немає.
    rows = await session.execute(
        select(Card.id, Card.media_asset_id, Module.id, MediaAsset.processing_status)
        .join(Module, Module.id == Card.module_id)
        .join(MediaAsset, MediaAsset.id == Card.media_asset_id)
        .where(Module.lesson_id == lesson.id, MediaAsset.processing_status != "ready")
        .order_by(Card.id)
    )
    for card_id, media_id, module_id, status in rows:
        problems.append(
            {
                "check": "video_processing" if status == "processing" else "video_failed",
                "message": "Video is still being compressed"
                if status == "processing"
                else "Video could not be compressed",
                "module_id": str(module_id),
                "card_id": str(card_id),
                "media_asset_id": str(media_id),
            }
        )

    limit = settings.pack_max_day_bytes
    size = await pack_size(session, {lesson.id})
    if size > limit:
        problems.append(
            {
                "check": "lesson_size",
                "message": "Lesson exceeds the size limit",
                "size_bytes": size,
                "limit_bytes": limit,
            }
        )

    # Урок уже стоїть у розкладі на майбутні дні (публікували раніше): пакет дня не має
    # вирости понад ліміт.
    # Відкладений імпорт: school імпортує цей модуль.
    from app.services import school as school_service

    today = _now().astimezone(ZoneInfo(DEFAULT_TZ)).date()
    scheduled = school_service.scheduled_lessons()
    days = await session.execute(
        select(scheduled.c.class_id, scheduled.c.date)
        .where(scheduled.c.lesson_id == lesson.id, scheduled.c.date >= today)
        .distinct()
        .order_by(scheduled.c.date, scheduled.c.class_id)
    )

    for class_id, day in days:
        klass = await session.get(SchoolClass, class_id)
        assert klass is not None
        day_size = await pack_size(
            session, await school_service.day_lesson_ids(session, klass, day)
        )
        if day_size > limit:
            problems.append(
                {
                    "check": "pack_day_size",
                    "message": "Class pack for a scheduled day exceeds the size limit",
                    "class_id": str(class_id),
                    "date": day.isoformat(),
                    "size_bytes": day_size,
                    "limit_bytes": limit,
                }
            )
    return problems


async def publish(session: AsyncSession, lesson: Lesson, settings: Settings) -> Lesson:
    """Ідемпотентно: опублікований урок повертається як є."""
    if lesson.status == "published":
        return lesson
    problems = await publish_problems(session, lesson, settings)
    if problems:
        raise AppError(
            "LESSON_NOT_PUBLISHABLE",
            "Lesson failed publication checks",
            status_code=422,
            details=problems,
        )
    # Повторна публікація після правок — нова версія; пакети порівнюють версію (B6.4).
    if lesson.published_at is not None:
        lesson.version += 1
    lesson.status = "published"
    lesson.published_at = _now()
    await session.commit()
    return lesson


async def unpublish(session: AsyncSession, lesson: Lesson) -> Lesson:
    """Повертає урок у чернетку для правок. Прив'язки в розкладі лишаються; пакети (B6)
    беруть лише опубліковані уроки. Ідемпотентно."""
    if lesson.status != "draft":
        lesson.status = "draft"
        await session.commit()
    return lesson
