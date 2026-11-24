"""Предмети й уроки вчителя: модулі, картки, тести, питання, публікація.

Писати може лише автор уроку (вчитель); адміністрація й інші вчителі школи лише читають.
Опублікований урок незмінний: `POST /lessons/{id}/unpublish` → правки → `publish` (version + 1).
Те саме для зміни порядку (`PUT .../order`): лише в чернетці, тож пакети не перезбираються.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import select

from app.api.deps import (
    Admin,
    EditableCard,
    EditableLesson,
    EditableModule,
    EditableQuestion,
    EditableTest,
    OwnLesson,
    ReadableLesson,
    Session,
    SettingsDep,
    Staff,
    Storage,
    Teacher,
)
from app.core.errors import AppError
from app.models.lessons import Card
from app.schemas.errors import ErrorResponse
from app.schemas.lessons import (
    CardCreate,
    CardOut,
    CardUpdate,
    ItemOrder,
    LessonCopy,
    LessonCreate,
    LessonOut,
    LessonSummary,
    LessonUpdate,
    ModuleCreate,
    ModuleOrder,
    ModuleOut,
    ModuleUpdate,
    QuestionCreate,
    QuestionOut,
    QuestionUpdate,
    SubjectCreate,
    SubjectOut,
    TestCreate,
    TestOut,
    TestUpdate,
)
from app.services import lessons as service
from app.workers.media import enqueue_process_video
from app.workers.packs import enqueue_rebuild_for_lesson
from app.workers.sync import enqueue_regrade_test

# Поля, від яких залежать оцінка й зарахування наявних спроб тесту.
_GRADING_TEST_FIELDS = {"window_enabled", "window_hours"}
_GRADING_QUESTION_FIELDS = {"answer_key", "points", "options", "right_options", "kind"}

router = APIRouter(tags=["lessons"])

R401 = {401: {"model": ErrorResponse, "description": "Не автентифіковано"}}
R403 = {403: {"model": ErrorResponse, "description": "Недостатньо прав"}}
R404 = {404: {"model": ErrorResponse, "description": "Не знайдено"}}
R409 = {
    409: {
        "model": ErrorResponse,
        "description": "ID_CONFLICT / POSITION_TAKEN / LESSON_PUBLISHED",
    }
}
REPEAT = {200: {"description": "Повтор із тим самим id і даними: наявний ресурс"}}
ACCESS = {**R401, **R403, **R404}
WRITE = {**ACCESS, **R409}
# Видалення частини уроку: опублікований урок не змінюється; модуль із прогресом учнів чи
# елемент, на який посилаються результати, не видаляється.
DELETE = {
    **ACCESS,
    409: {"model": ErrorResponse, "description": "LESSON_PUBLISHED / IN_USE"},
}
# Новий порядок: `ids` — рівно поточний набір елементів.
ORDER = {
    **ACCESS,
    409: {"model": ErrorResponse, "description": "LESSON_PUBLISHED"},
    422: {
        "model": ErrorResponse,
        "description": "ORDER_MISMATCH: `ids` не збігаються з поточним набором; `details` — "
        "`missing` (бракує), `unknown` (чужі чи видалені), `duplicates` (повтори)",
    },
}


def _created(response: Response, created: bool) -> None:
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK


def _no_content() -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- предмети ----------


@router.get("/subjects", response_model=list[SubjectOut], responses={**R401, **R403})
async def list_subjects(user: Staff, session: Session) -> list[SubjectOut]:
    """Загальний довідник і предмети своєї школи."""
    return [
        SubjectOut.model_validate(s) for s in await service.list_subjects(session, user.school_id)
    ]


@router.post(
    "/subjects",
    response_model=SubjectOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **R401, **R403, **R409},
)
async def create_subject(
    body: SubjectCreate, admin: Admin, session: Session, response: Response
) -> SubjectOut:
    """Адмін додає предмет своєї школи. Ідемпотентно за `id`."""
    if admin.school_id is None:
        raise AppError("FORBIDDEN", "Admin is not attached to a school", status_code=403)
    subject, created = await service.create_subject(session, admin, body)
    _created(response, created)
    return SubjectOut.model_validate(subject)


# ---------- урок ----------


@router.get("/lessons", response_model=list[LessonSummary], responses={**R401, **R403})
async def list_lessons(
    user: Staff,
    session: Session,
    lesson_status: Annotated[Literal["draft", "published"] | None, Query(alias="status")] = None,
    scope: Literal["mine", "school"] = "mine",
) -> list[LessonSummary]:
    """Вчитель — свої уроки, адмін — уроки вчителів своєї школи. `scope=school`: для вчителя —
    опубліковані уроки колег зі школи (для копіювання, `POST /lessons/{id}/copy`)."""
    lessons = await service.list_lessons(session, user, lesson_status, scope)
    return [LessonSummary.model_validate(lesson) for lesson in lessons]


@router.post(
    "/lessons",
    response_model=LessonOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **R401, **R403, **R404, **R409},
)
async def create_lesson(
    body: LessonCreate, teacher: Teacher, session: Session, storage: Storage, response: Response
) -> LessonOut:
    """Вчитель створює урок-чернетку. Ідемпотентно за `id`."""
    lesson, created = await service.create_lesson(session, teacher, body)
    _created(response, created)
    return await service.lesson_out(session, lesson, storage)


@router.get("/lessons/{lesson_id}", response_model=LessonOut, responses=ACCESS)
async def get_lesson(lesson: ReadableLesson, session: Session, storage: Storage) -> LessonOut:
    """Урок з модулями, картками (з медіа: URL, розмір, субтитри), тестами й питаннями (з
    ключами відповідей і поясненнями). `size_bytes` / `limit_bytes` — для «X МБ з 50 МБ»."""
    return await service.lesson_out(session, lesson, storage)


@router.patch("/lessons/{lesson_id}", response_model=LessonOut, responses=WRITE)
async def update_lesson(
    body: LessonUpdate, lesson: EditableLesson, teacher: Teacher, session: Session, storage: Storage
) -> LessonOut:
    lesson = await service.update_lesson(session, teacher, lesson, body)
    return await service.lesson_out(session, lesson, storage)


@router.delete(
    "/lessons/{lesson_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        **ACCESS,
        409: {"model": ErrorResponse, "description": "LESSON_PUBLISHED / LESSON_IN_USE"},
    },
)
async def delete_lesson(lesson: EditableLesson, session: Session) -> Response:
    """Видаляє чернетку, якої немає в розкладі й за якою немає результатів."""
    await service.delete_lesson(session, lesson)
    return _no_content()


@router.post(
    "/lessons/{lesson_id}/publish",
    response_model=LessonOut,
    responses={
        **ACCESS,
        422: {
            "model": ErrorResponse,
            "description": "LESSON_NOT_PUBLISHABLE: `details` — список усіх провалених перевірок",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "LESSON_NOT_PUBLISHABLE",
                            "message": "Lesson failed publication checks",
                            "details": [
                                {
                                    "check": "shelter_part",
                                    "message": "Lesson has no shelter part (shelter_part)",
                                },
                                {
                                    "check": "video_processing",
                                    "message": "Video is still being compressed",
                                    "module_id": "0192f0a0-0000-7000-8000-000000000311",
                                    "card_id": "0192f0a0-0000-7000-8000-000000000321",
                                    "media_asset_id": "0192f0a0-0000-7000-8000-000000000501",
                                },
                                {
                                    "check": "lesson_size",
                                    "message": "Lesson exceeds the size limit",
                                    "size_bytes": 60000000,
                                    "limit_bytes": 52428800,
                                },
                            ],
                        }
                    }
                }
            },
        },
    },
)
async def publish_lesson(
    lesson: OwnLesson, session: Session, settings: SettingsDep, storage: Storage
) -> LessonOut:
    """Публікація після серверних перевірок: є укриттєва частина й модулі, тести мають питання,
    усі відео стиснуті (`video_processing` — ще стискаються, `video_failed` — не вдалося), урок і
    пакети днів, де він уже стоїть, — у межах ліміту. Відео без VTT-субтитрів не блокує
    публікацію: це попередження `video_subtitles` у `warnings` уроку. Повторна публікація після
    правок збільшує `version`. Ідемпотентно. Пакети класів, де урок стоїть, перезбирає Celery."""
    lesson = await service.publish(session, lesson, settings)
    await enqueue_rebuild_for_lesson(lesson.id)
    return await service.lesson_out(session, lesson, storage, settings)


@router.post("/lessons/{lesson_id}/unpublish", response_model=LessonOut, responses=ACCESS)
async def unpublish_lesson(lesson: OwnLesson, session: Session, storage: Storage) -> LessonOut:
    """Повертає урок у чернетку для правок. Ідемпотентно. Урок зникає з нових версій пакетів;
    уже завантажені версії лишаються на пристроях."""
    lesson = await service.unpublish(session, lesson)
    await enqueue_rebuild_for_lesson(lesson.id)
    return await service.lesson_out(session, lesson, storage)


@router.post(
    "/lessons/{lesson_id}/copy",
    response_model=LessonOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Повтор із тим самим `id` (той самий автор і джерело): наявна копія"},
        **ACCESS,
        409: {"model": ErrorResponse, "description": "ID_CONFLICT: під цим `id` інший урок"},
    },
)
async def copy_lesson(
    body: LessonCopy,
    lesson: ReadableLesson,
    teacher: Teacher,
    session: Session,
    storage: Storage,
    response: Response,
) -> LessonOut:
    """Копія уроку в нову чернетку вчителя: модулі, картки, тести, питання (з ключами й
    поясненнями). Джерело — свій урок або урок колеги зі школи (чернетка чи опублікований).
    Id елементів копії генерує сервер детерміновано від `id` копії, тож повтор нічого не дублює.
    Медіа не дублюються: свої — ті самі записи; медіа колеги — нові записи вчителя на той самий
    файл (інші `id`, той самий `url`), щоб вчитель міг прив'язати субтитри. Розклад і результати
    учнів не копіюються. `copied_from_id` копії — джерело."""
    copy, created = await service.copy_lesson(session, teacher, lesson, body)
    _created(response, created)
    # Відео колеги ще стискається: копія має свій запис на той самий файл — ставимо задачу й
    # для нього (ідемпотентно), інакше він може застрягти в processing.
    for media_id in await service.processing_media(session, copy.id):
        await enqueue_process_video(media_id)
    return await service.lesson_out(session, copy, storage)


# ---------- модулі ----------


@router.post(
    "/lessons/{lesson_id}/modules",
    response_model=ModuleOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **WRITE},
)
async def create_module(
    body: ModuleCreate, lesson: EditableLesson, session: Session, response: Response
) -> ModuleOut:
    module, created = await service.create_module(session, lesson, body)
    _created(response, created)
    return ModuleOut.model_validate(module)


@router.put("/lessons/{lesson_id}/modules/order", response_model=list[ModuleOut], responses=ORDER)
async def reorder_modules(
    body: ModuleOrder, lesson: EditableLesson, session: Session, storage: Storage
) -> list[ModuleOut]:
    """Новий порядок модулів частини `part`: позиції стають 1..n у порядку `ids`. `ids` —
    усі модулі цієї частини, кожен раз. Ідемпотентно. Відповідь — модулі частини з картками."""
    modules = await service.reorder_modules(session, lesson, body)
    cards = await service.card_outs(
        session,
        storage,
        list(
            await session.scalars(
                select(Card)
                .where(Card.module_id.in_([m.id for m in modules]))
                .order_by(Card.position)
            )
        ),
    )
    return [
        ModuleOut.model_validate(m).model_copy(
            update={"cards": [c for c in cards if c.module_id == m.id]}
        )
        for m in modules
    ]


@router.patch("/modules/{module_id}", response_model=ModuleOut, responses=WRITE)
async def update_module(body: ModuleUpdate, module: EditableModule, session: Session) -> ModuleOut:
    return ModuleOut.model_validate(await service.update_module(session, module, body))


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE)
async def delete_module(module: EditableModule, session: Session) -> Response:
    await service.delete_child(session, module)
    return _no_content()


# ---------- картки ----------


@router.post(
    "/modules/{module_id}/cards",
    response_model=CardOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **WRITE},
)
async def create_card(
    body: CardCreate,
    module: EditableModule,
    teacher: Teacher,
    session: Session,
    storage: Storage,
    response: Response,
) -> CardOut:
    """Картка; для `image`/`video` — власний файл вчителя того самого типу. Текст картки —
    проста розмітка (див. `body` у схемі)."""
    card, created = await service.create_card(session, teacher, module, body)
    _created(response, created)
    return (await service.card_outs(session, storage, [card]))[0]


@router.patch("/cards/{card_id}", response_model=CardOut, responses=WRITE)
async def update_card(
    body: CardUpdate, card: EditableCard, teacher: Teacher, session: Session, storage: Storage
) -> CardOut:
    card = await service.update_card(session, teacher, card, body)
    return (await service.card_outs(session, storage, [card]))[0]


@router.put("/modules/{module_id}/cards/order", response_model=list[CardOut], responses=ORDER)
async def reorder_cards(
    body: ItemOrder, module: EditableModule, session: Session, storage: Storage
) -> list[CardOut]:
    """Новий порядок карток модуля: позиції 1..n у порядку `ids` (усі картки модуля, кожна
    раз). Ідемпотентно."""
    cards = await service.reorder_cards(session, module, body)
    return await service.card_outs(session, storage, cards)


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE)
async def delete_card(card: EditableCard, session: Session) -> Response:
    await service.delete_child(session, card)
    return _no_content()


# ---------- тести й питання ----------


@router.post(
    "/lessons/{lesson_id}/tests",
    response_model=TestOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **WRITE},
)
async def create_test(
    body: TestCreate, lesson: EditableLesson, session: Session, response: Response
) -> TestOut:
    test, created = await service.create_test(session, lesson, body)
    _created(response, created)
    return TestOut.model_validate(test)


@router.patch("/tests/{test_id}", response_model=TestOut, responses=WRITE)
async def update_test(body: TestUpdate, test: EditableTest, session: Session) -> TestOut:
    """Зміна вікна (`window_enabled`, `window_hours`) після спроб учнів перераховує їхнє
    зарахування (Celery, черга `sync`); результат учні бачать у `GET /sync/changes`."""
    test = await service.update_test(session, test, body)
    if body.model_fields_set & _GRADING_TEST_FIELDS:
        await enqueue_regrade_test(test.id)
    return TestOut.model_validate(test)


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE)
async def delete_test(test: EditableTest, session: Session) -> Response:
    await service.delete_child(session, test)
    return _no_content()


@router.post(
    "/tests/{test_id}/questions",
    response_model=QuestionOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **WRITE},
)
async def create_question(
    body: QuestionCreate, test: EditableTest, session: Session, response: Response
) -> QuestionOut:
    """Нове питання змінює максимум балів: наявні спроби переоцінюються (Celery). Типи:
    `single`, `multiple`, `text`, `match` — формат полів у схемі `QuestionCreate`."""
    question, created = await service.create_question(session, test, body)
    _created(response, created)
    if created:
        await enqueue_regrade_test(test.id)
    return QuestionOut.model_validate(question)


@router.put("/tests/{test_id}/questions/order", response_model=list[QuestionOut], responses=ORDER)
async def reorder_questions(
    body: ItemOrder, test: EditableTest, session: Session
) -> list[QuestionOut]:
    """Новий порядок питань тесту: позиції 1..n у порядку `ids` (усі питання тесту, кожне
    раз). Ідемпотентно. Оцінка спроб від порядку не залежить."""
    questions = await service.reorder_questions(session, test, body)
    return [QuestionOut.model_validate(q) for q in questions]


@router.patch("/questions/{question_id}", response_model=QuestionOut, responses=WRITE)
async def update_question(
    body: QuestionUpdate, question: EditableQuestion, session: Session
) -> QuestionOut:
    """Зміна ключа, балів, варіантів чи типу переоцінює наявні спроби тесту (Celery, черга
    `sync`): оцінка й зарахування оновлюються в `GET /sync/changes` і кабінетах."""
    question = await service.update_question(session, question, body)
    if body.model_fields_set & _GRADING_QUESTION_FIELDS:
        await enqueue_regrade_test(question.test_id)
    return QuestionOut.model_validate(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT, responses=DELETE)
async def delete_question(question: EditableQuestion, session: Session) -> Response:
    test_id = question.test_id
    await service.delete_child(session, question)
    await enqueue_regrade_test(test_id)
    return _no_content()
