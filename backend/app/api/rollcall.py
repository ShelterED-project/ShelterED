"""Перекличка (заглушки B4, логіка — B12).

Статуси учні надсилають подіями `rollcall_status` через `POST /sync/events` (окремого
ендпоінта «відмітитися» немає, щоб офлайн-відмітка не губилася).
"""

import uuid

from fastapi import APIRouter, status

from app.api.deps import AccessibleClass, AccessibleStudent, TeacherClass
from app.api.stub import R501, example_of, not_implemented
from app.schemas.errors import ErrorResponse
from app.schemas.rollcall import (
    RollCallCurrentOut,
    RollCallSessionOut,
    RollCallStart,
    StudentRollCallOut,
)

router = APIRouter(tags=["rollcall"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}


@router.get(
    "/classes/{class_id}/rollcall/current",
    response_model=RollCallCurrentOut,
    responses={200: example_of(RollCallCurrentOut), **ACCESS, **R501},
)
async def current_rollcall(klass: AccessibleClass) -> RollCallCurrentOut:
    """Відкрита перекличка класу. Вчитель класу й адмін школи бачать статуси всіх учнів
    (з часом отримання, щоб було видно застарілі), учень — лише свій (і `id` сесії для події
    `rollcall_status`). Оновлення — опитуванням (кожні 10 с, коли є мережа)."""
    raise not_implemented()


@router.post(
    "/classes/{class_id}/rollcall",
    response_model=RollCallSessionOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: example_of(RollCallSessionOut, "Перекличку відкрито"),
        200: {"description": "Повтор із тим самим id: наявна сесія"},
        **ACCESS,
        409: {"model": ErrorResponse, "description": "ROLLCALL_ALREADY_OPEN (інша сесія)"},
        **R501,
    },
)
async def start_rollcall(body: RollCallStart, klass: TeacherClass) -> RollCallSessionOut:
    """Вчитель класу відкриває перекличку вручну (без тривоги). При тривозі сесія
    відкривається автоматично. Ідемпотентно за `id`; на клас — одна відкрита сесія."""
    raise not_implemented()


@router.post(
    "/classes/{class_id}/rollcall/{session_id}/close",
    response_model=RollCallSessionOut,
    responses={200: example_of(RollCallSessionOut), **ACCESS, **R501},
)
async def close_rollcall(klass: TeacherClass, session_id: uuid.UUID) -> RollCallSessionOut:
    """Вчитель закриває перекличку (при відбої тривоги — автоматично). Ідемпотентно."""
    raise not_implemented()


@router.get(
    "/students/{student_id}/rollcall/current",
    response_model=StudentRollCallOut,
    responses={200: example_of(StudentRollCallOut), **ACCESS, **R501},
)
async def student_rollcall(student: AccessibleStudent) -> StudentRollCallOut:
    """Статус дитини в поточній перекличці: батьки — лише своєї дитини, учень — свій,
    вчитель — учнів своїх класів, адмін — учнів школи."""
    raise not_implemented()
