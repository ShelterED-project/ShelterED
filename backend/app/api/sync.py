"""Синхронізація подій з пристроїв (протокол — docs/sync-protocol.md v1)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import Session, SettingsDep, require_roles
from app.api.stub import example_of
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.sync import SyncChangesOut, SyncEventsRequest, SyncEventsResponse
from app.services import sync as service

router = APIRouter(tags=["sync"])

AUTH = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
}

# Вчитель — для QR-подій учнів своїх класів (B10).
EventSender = Annotated[User, Depends(require_roles("student", "teacher"))]
Student = Annotated[User, Depends(require_roles("student"))]


@router.post(
    "/sync/events",
    response_model=SyncEventsResponse,
    responses={
        200: example_of(SyncEventsResponse, "Результат по кожній події пакета"),
        **AUTH,
        422: {"model": ErrorResponse, "description": "Невалідний конверт або понад 100 подій"},
        429: {"model": ErrorResponse, "description": "RATE_LIMITED"},
        500: {
            "model": ErrorResponse,
            "description": "INTERNAL_ERROR: частину подій не оброблено — повторити пакет",
        },
        501: {
            "model": ErrorResponse,
            "description": "NOT_IMPLEMENTED: QR-ретрансляція вчителем (B10) ще не реалізована",
        },
    },
)
async def post_events(
    body: SyncEventsRequest, user: EventSender, session: Session, settings: SettingsDep
) -> SyncEventsResponse:
    """Пакет 1–100 подій. Кожна подія приймається один раз за `client_event_id`: повтор
    прийнятої дає `duplicate`, повтор відхиленої — той самий `rejected` з причиною; нічого не
    дублюється. Погана подія отримує `rejected` і не блокує решту пакета. Події обробляються
    в порядку `occurred_at`, кожна у своїй транзакції; результати — у порядку запиту.
    Статус 200, якщо конверт пакета валідний; 500 — частину подій не записано (повторити
    пакет: записані дадуть `duplicate`). Вчитель (QR, B10) поки отримує 501."""
    return await service.receive_events(session, user, body, settings)


@router.get(
    "/sync/changes",
    response_model=SyncChangesOut,
    responses={
        200: example_of(SyncChangesOut),
        **AUTH,
        422: {"model": ErrorResponse, "description": "INVALID_CURSOR"},
    },
)
async def get_changes(
    user: Student,
    session: Session,
    cursor: Annotated[
        str | None, Query(max_length=64, description="`next_cursor` з попередньої відповіді")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> SyncChangesOut:
    """Зміни для поточного учня після `cursor` (без нього — з початку): результати спроб,
    підсумковий прогрес модулів, статуси переклички — актуальний стан кожного зміненого рядка.
    Курсор непрозорий, монотонний, без пропусків (віддаються лише точно закомічені зміни);
    повтор із тим самим курсором повертає ті самі зміни (або новіший стан тих самих рядків).
    Невідомий формат курсора — 422 `INVALID_CURSOR`."""
    return await service.changes(session, user, cursor, limit)
