"""Синхронізація подій з пристроїв (заглушки B4, логіка — B9; протокол — docs/sync-protocol.md)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_roles
from app.api.stub import R501, example_of, not_implemented
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.sync import SyncChangesOut, SyncEventsRequest, SyncEventsResponse

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
        **R501,
    },
)
async def post_events(body: SyncEventsRequest, user: EventSender) -> SyncEventsResponse:
    """Пакет 1–100 подій. Кожна подія приймається один раз за `client_event_id`: повтор дає
    `duplicate`, нічого не дублюючи. Погана подія отримує `rejected` з причиною й не блокує
    решту пакета. Статус відповіді 200, якщо конверт пакета валідний."""
    raise not_implemented()


@router.get(
    "/sync/changes",
    response_model=SyncChangesOut,
    responses={200: example_of(SyncChangesOut), **AUTH, **R501},
)
async def get_changes(
    user: Student,
    cursor: Annotated[
        str | None, Query(max_length=64, description="`next_cursor` з попередньої відповіді")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> SyncChangesOut:
    """Зміни для поточного учня після `cursor` (без нього — з початку): результати спроб,
    підсумковий прогрес модулів, статуси переклички. Курсор монотонний, без пропусків;
    повтор із тим самим курсором повертає ті самі зміни."""
    raise not_implemented()
