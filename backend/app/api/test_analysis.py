"""AI-аналіз тесту класу: кнопка «Проаналізувати» в «Мапі класу» → висновок для вчителя й
фідбек кожному учню та батькам (`app/services/test_analysis.py`).

Аналізи бачить і змінює лише вчитель класу; учень і батьки — лише опублікований текст для
себе (B5). Адміністрація — ні (навчальні дані окремих учнів їй не потрібні).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import (
    Session,
    SettingsDep,
    Teacher,
    TeacherClass,
    get_accessible_student,
    require_roles,
)
from app.api.stub import example_of
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.test_analysis import (
    AnalysisStudentOut,
    FeedbackEditIn,
    TestAnalysisOut,
    TestFeedbackOut,
)
from app.services import test_analysis as service
from app.workers.test_analysis import enqueue_run

router = APIRouter(tags=["test-analysis"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}
CONFLICT = {409: {"model": ErrorResponse, "description": "Конфлікт стану"}}

StudentOrParent = Annotated[User, Depends(require_roles("student", "parent"))]


@router.post(
    "/classes/{class_id}/tests/{test_id}/analysis",
    response_model=TestAnalysisOut,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        202: example_of(TestAnalysisOut, "Аналіз запущено (`processing`)"),
        200: {"description": "Аналіз цього тесту вже йде — повернуто його"},
        **ACCESS,
        **CONFLICT,
    },
)
async def start_analysis(
    klass: TeacherClass,
    test_id: uuid.UUID,
    teacher: Teacher,
    session: Session,
    settings: SettingsDep,
    response: Response,
) -> TestAnalysisOut:
    """Запускає AI-аналіз тесту за зарахованими спробами учнів класу. Лише вчитель класу.

    409 `NOT_ENOUGH_ATTEMPTS` (`details: {attempts, required}`) — замало спроб;
    409 `TEST_NOT_ANALYZABLE` — у тесті немає питань з вибором. Повторний запуск після
    `draft`/`published`/`failed` створює новий аналіз (старі лишаються)."""
    analysis, created = await service.start(session, klass, test_id, teacher, settings)
    if created:
        await enqueue_run(analysis.id)
    else:
        response.status_code = status.HTTP_200_OK
    return analysis


@router.get(
    "/classes/{class_id}/tests/{test_id}/analysis",
    response_model=TestAnalysisOut,
    responses={200: example_of(TestAnalysisOut), **ACCESS},
)
async def get_analysis(
    klass: TeacherClass, test_id: uuid.UUID, session: Session, settings: SettingsDep
) -> TestAnalysisOut:
    """Останній аналіз тесту в класі (будь-який статус). 404 `ANALYSIS_NOT_FOUND` — тест ще
    не аналізували. Поки `processing`, клієнт опитує кожні 3 с."""
    return await service.get_latest(session, klass, test_id, settings)


@router.patch(
    "/test-analyses/{analysis_id}/students/{student_id}",
    response_model=AnalysisStudentOut,
    responses={200: example_of(AnalysisStudentOut), **ACCESS, **CONFLICT},
)
async def edit_student_feedback(
    analysis_id: uuid.UUID,
    student_id: uuid.UUID,
    body: FeedbackEditIn,
    teacher: Teacher,
    session: Session,
) -> AnalysisStudentOut:
    """Правка тексту для учня та/або батьків (Markdown, ≤ 3000 символів). Відсутнє поле — без
    змін, `null` — повернути текст AI. Лише чернетка (409 `ANALYSIS_NOT_DRAFT`)."""
    analysis = await service.get_for_teacher(session, teacher, analysis_id)
    return await service.edit_feedback(session, teacher, analysis, student_id, body)


@router.post(
    "/test-analyses/{analysis_id}/publish",
    response_model=TestAnalysisOut,
    responses={200: example_of(TestAnalysisOut), **ACCESS, **CONFLICT},
)
async def publish_analysis(
    analysis_id: uuid.UUID, teacher: Teacher, session: Session
) -> TestAnalysisOut:
    """Надсилає фідбек учням і батькам. Ідемпотентно. 409 `ANALYSIS_NOT_READY` — аналіз ще
    `processing` або `failed`."""
    analysis = await service.get_for_teacher(session, teacher, analysis_id)
    return await service.publish(session, analysis)


@router.get(
    "/students/{student_id}/test-feedback",
    response_model=TestFeedbackOut,
    responses={200: example_of(TestFeedbackOut), **ACCESS},
)
async def student_test_feedback(
    student_id: uuid.UUID, user: StudentOrParent, session: Session
) -> TestFeedbackOut:
    """Опубліковані відгуки вчителя за тестами: учень — про себе, батьки — про свою дитину.
    `text` — версія для того, хто питає."""
    student = await get_accessible_student(student_id, user, session)
    return await service.student_feedback(session, user, student)
