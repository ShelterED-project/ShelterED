"""Перекличка (B12).

Статуси учні надсилають подіями `rollcall_status` через `POST /sync/events` (окремого
ендпоінта «відмітитися» немає, щоб офлайн-відмітка не губилася).
"""

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Header, Response, status

from app.api.deps import (
    AccessibleClass,
    AccessibleStudent,
    CurrentUser,
    Session,
    Teacher,
    TeacherClass,
)
from app.api.packs import _etag_matches
from app.api.stub import example_of
from app.schemas.errors import ErrorResponse
from app.schemas.rollcall import (
    RollCallCurrentOut,
    RollCallSessionOut,
    RollCallStart,
    StudentRollCallOut,
)
from app.services import rollcall as service

router = APIRouter(tags=["rollcall"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}


@router.get(
    "/classes/{class_id}/rollcall/current",
    response_model=RollCallCurrentOut,
    responses={
        200: {
            **example_of(RollCallCurrentOut),
            "headers": {"ETag": {"description": "Хеш відповіді", "schema": {"type": "string"}}},
        },
        304: {"description": "Не змінилась (`If-None-Match` збігся з ETag)"},
        **ACCESS,
    },
)
async def current_rollcall(
    klass: AccessibleClass,
    user: CurrentUser,
    session: Session,
    if_none_match: Annotated[str | None, Header()] = None,
) -> Response:
    """Відкрита перекличка класу. Вчитель класу й адмін школи бачать статуси всіх учнів
    (з часом отримання, щоб було видно застарілі), учень — лише свій (і `id` сесії для події
    `rollcall_status`). Оновлення — опитуванням (кожні 10 с, коли є мережа) з `If-None-Match`:
    без змін — 304 без тіла. Батьки — `GET /students/{id}/rollcall/current`."""
    body = (await service.current(session, user, klass)).model_dump_json().encode()
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": "private, no-cache"}
    if if_none_match and _etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


@router.post(
    "/classes/{class_id}/rollcall",
    response_model=RollCallSessionOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: example_of(RollCallSessionOut, "Перекличку відкрито"),
        200: {"description": "Повтор із тим самим id: наявна сесія"},
        **ACCESS,
        409: {
            "model": ErrorResponse,
            "description": "ROLLCALL_ALREADY_OPEN (інша відкрита сесія, її id у "
            "`details.session_id`) / ID_CONFLICT (id зайнятий сесією іншого класу)",
        },
    },
)
async def start_rollcall(
    body: RollCallStart, klass: TeacherClass, user: Teacher, session: Session, response: Response
) -> RollCallSessionOut:
    """Вчитель класу відкриває перекличку вручну. При тривозі під час уроку сесія
    відкривається автоматично; якщо урок почався, коли тривога вже йшла, ручна сесія
    належить цій тривозі (`alert_event_id`) і закривається її відбоєм. Ідемпотентно за `id`
    (повтор — 200 з наявною сесією, навіть закритою); на клас — одна відкрита сесія."""
    out, created = await service.start(session, user, klass, body)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return out


@router.post(
    "/classes/{class_id}/rollcall/{session_id}/close",
    response_model=RollCallSessionOut,
    responses={200: example_of(RollCallSessionOut), **ACCESS},
)
async def close_rollcall(
    klass: TeacherClass, session_id: uuid.UUID, user: Teacher, session: Session
) -> RollCallSessionOut:
    """Вчитель закриває перекличку (при відбої тривоги — автоматично). Ідемпотентно:
    закрита сесія повертається як є. Сесія іншого класу — 404."""
    return await service.close(session, user, klass, session_id)


@router.get(
    "/students/{student_id}/rollcall/current",
    response_model=StudentRollCallOut,
    responses={200: example_of(StudentRollCallOut), **ACCESS},
)
async def student_rollcall(student: AccessibleStudent, session: Session) -> StudentRollCallOut:
    """Статус дитини в поточній (відкритій) перекличці її класу: батьки — лише своєї дитини,
    учень — свій, вчитель — учнів своїх класів, адмін — учнів школи. Переклички немає —
    `session_id` і `status` = null."""
    return await service.student_current(session, student)
