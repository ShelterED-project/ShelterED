"""Предмети й уроки вчителя: модулі, картки, тести, питання, публікація.

Писати може лише автор уроку (вчитель); адміністрація й інші вчителі школи лише читають.
Опублікований урок незмінний: `POST /lessons/{id}/unpublish` → правки → `publish` (version + 1).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

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
    Teacher,
)
from app.core.errors import AppError
from app.schemas.errors import ErrorResponse
from app.schemas.lessons import (
    CardCreate,
    CardOut,
    CardUpdate,
    LessonCreate,
    LessonOut,
    LessonSummary,
    LessonUpdate,
    ModuleCreate,
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
) -> list[LessonSummary]:
    """Вчитель — свої уроки, адмін — уроки вчителів своєї школи."""
    lessons = await service.list_lessons(session, user, lesson_status)
    return [LessonSummary.model_validate(lesson) for lesson in lessons]


@router.post(
    "/lessons",
    response_model=LessonOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **R401, **R403, **R404, **R409},
)
async def create_lesson(
    body: LessonCreate, teacher: Teacher, session: Session, response: Response
) -> LessonOut:
    """Вчитель створює урок-чернетку. Ідемпотентно за `id`."""
    lesson, created = await service.create_lesson(session, teacher, body)
    _created(response, created)
    return await service.lesson_out(session, lesson)


@router.get("/lessons/{lesson_id}", response_model=LessonOut, responses=ACCESS)
async def get_lesson(lesson: ReadableLesson, session: Session) -> LessonOut:
    """Урок з модулями, картками, тестами й питаннями (з ключами відповідей)."""
    return await service.lesson_out(session, lesson)


@router.patch("/lessons/{lesson_id}", response_model=LessonOut, responses=WRITE)
async def update_lesson(
    body: LessonUpdate, lesson: EditableLesson, teacher: Teacher, session: Session
) -> LessonOut:
    lesson = await service.update_lesson(session, teacher, lesson, body)
    return await service.lesson_out(session, lesson)


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
                                    "check": "video_subtitles",
                                    "message": "Video has no VTT subtitles",
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
async def publish_lesson(lesson: OwnLesson, session: Session, settings: SettingsDep) -> LessonOut:
    """Публікація після серверних перевірок: є укриттєва частина, у кожного відео є VTT-субтитри,
    урок і пакети днів, де він уже стоїть, — у межах ліміту. Повторна публікація після правок
    збільшує `version`. Ідемпотентно."""
    return await service.lesson_out(session, await service.publish(session, lesson, settings))


@router.post("/lessons/{lesson_id}/unpublish", response_model=LessonOut, responses=ACCESS)
async def unpublish_lesson(lesson: OwnLesson, session: Session) -> LessonOut:
    """Повертає урок у чернетку для правок. Ідемпотентно."""
    return await service.lesson_out(session, await service.unpublish(session, lesson))


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


@router.patch("/modules/{module_id}", response_model=ModuleOut, responses=WRITE)
async def update_module(body: ModuleUpdate, module: EditableModule, session: Session) -> ModuleOut:
    return ModuleOut.model_validate(await service.update_module(session, module, body))


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT, responses=WRITE)
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
    response: Response,
) -> CardOut:
    """Картка; для `image`/`video` — власний файл вчителя того самого типу."""
    card, created = await service.create_card(session, teacher, module, body)
    _created(response, created)
    return CardOut.model_validate(card)


@router.patch("/cards/{card_id}", response_model=CardOut, responses=WRITE)
async def update_card(
    body: CardUpdate, card: EditableCard, teacher: Teacher, session: Session
) -> CardOut:
    return CardOut.model_validate(await service.update_card(session, teacher, card, body))


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT, responses=WRITE)
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
    return TestOut.model_validate(await service.update_test(session, test, body))


@router.delete("/tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT, responses=WRITE)
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
    question, created = await service.create_question(session, test, body)
    _created(response, created)
    return QuestionOut.model_validate(question)


@router.patch("/questions/{question_id}", response_model=QuestionOut, responses=WRITE)
async def update_question(
    body: QuestionUpdate, question: EditableQuestion, session: Session
) -> QuestionOut:
    return QuestionOut.model_validate(await service.update_question(session, question, body))


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT, responses=WRITE)
async def delete_question(question: EditableQuestion, session: Session) -> Response:
    await service.delete_child(session, question)
    return _no_content()
