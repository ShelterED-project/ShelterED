"""«Як ти зараз?» (docs/wellbeing-checkin.md). Запис — лише через `POST /sync/events`
(`survey_answer`); тут читання з обмеженнями й журналом переглядів.

Дані бачать лише сама дитина й її батьки. Вчитель і адміністрація не бачать нічого, навіть
зведень класу чи школи (ролі психолога немає)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, Session, get_accessible_student, require_roles
from app.api.stub import example
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.wellbeing import (
    PARENT_EXAMPLE,
    StudentWellbeingOut,
    WellbeingTextsOut,
)
from app.services import wellbeing as service
from app.services.wellbeing_texts import TEXTS

router = APIRouter(tags=["wellbeing"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}


async def get_wellbeing_student(
    student_id: uuid.UUID,
    user: Annotated[User, Depends(require_roles("student", "parent"))],
    session: Session,
) -> User:
    """Учень — лише себе, батьки — лише прив'язану дитину; вчитель і адмін — 403."""
    return await get_accessible_student(student_id, user, session)


@router.get("/wellbeing/texts", response_model=WellbeingTextsOut, responses={401: ACCESS[401]})
async def wellbeing_texts(_: CurrentUser) -> WellbeingTextsOut:
    """Усі тексти «Як ти зараз?»: питання, картинки погоди, відповіді дитині, дихальна вправа,
    блок підтримки з гарячою лінією, тексти для батьків. Будь-яка роль."""
    return WellbeingTextsOut.model_validate(TEXTS)


@router.get(
    "/students/{student_id}/wellbeing",
    response_model=StudentWellbeingOut,
    responses={200: example(PARENT_EXAMPLE), **ACCESS},
)
async def student_wellbeing(
    student: Annotated[User, Depends(get_wellbeing_student)], user: CurrentUser, session: Session
) -> StudentWellbeingOut:
    """Учень бачить свої картинки за 14 днів і `show_support`; батьки — лише тижневе зведення
    словами (без днів і чисел), кожен перегляд батьків пишеться в журнал. Вчитель (навіть
    свого класу), адмін, інші батьки й учні — 403."""
    return await service.student_view(session, user, student)
