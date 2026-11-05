"""Тривоги: ручна кнопка, відбій, активні тривоги, журнал (заглушки B4, логіка — B7).

Тривоги з API бекенд опитує й розбирає сам (B7); публічного вебхука немає.
"""

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import Admin, CurrentUser, Teacher
from app.api.stub import R501, example, example_of, not_implemented
from app.schemas.alerts import ALERT_EXAMPLES, ActiveAlertsOut, AlertOut, ManualAlertCreate
from app.schemas.errors import ErrorResponse

router = APIRouter(tags=["alerts"])

R401 = {401: {"model": ErrorResponse, "description": "Не автентифіковано"}}
R403 = {403: {"model": ErrorResponse, "description": "Недостатньо прав"}}
R404 = {404: {"model": ErrorResponse, "description": "Не знайдено"}}


@router.post(
    "/alerts/manual",
    response_model=AlertOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: example(ALERT_EXAMPLES["manual"], "Тривогу оголошено"),
        200: {"description": "Повтор із тим самим id: наявна тривога"},
        **R401,
        **R403,
        **R404,
        **R501,
    },
)
async def manual_alert(body: ManualAlertCreate, teacher: Teacher) -> AlertOut:
    """Ручна кнопка «Тривога» вчителя для свого класу (зокрема тренувальна): відкриває
    перекличку й розсилає push класу. Ідемпотентно за `id`; чужий клас — 403."""
    raise not_implemented()


@router.post(
    "/alerts/{alert_id}/end",
    response_model=AlertOut,
    responses={
        200: example({**ALERT_EXAMPLES["manual"], "ended_at": "2026-11-05T09:50:00Z"}),
        **R401,
        **R403,
        **R404,
        **R501,
    },
)
async def end_alert(alert_id: uuid.UUID, teacher: Teacher) -> AlertOut:
    """Відбій ручної тривоги вчителем її класу; закриває перекличку. Ідемпотентно.
    Відбій тривоги з API приходить лише з API."""
    raise not_implemented()


@router.get(
    "/alerts/active",
    response_model=ActiveAlertsOut,
    responses={200: example_of(ActiveAlertsOut), **R401, **R501},
)
async def active_alerts(user: CurrentUser) -> ActiveAlertsOut:
    """Активні тривоги для шкіл і класів користувача (батьки — шкіл своїх дітей).
    Запасний шлях для клієнта, який не отримав push."""
    raise not_implemented()


@router.get(
    "/alerts",
    response_model=list[AlertOut],
    responses={
        200: example([{**ALERT_EXAMPLES["api"], "ended_at": "2026-11-05T10:45:00Z"}]),
        **R401,
        **R403,
        **R501,
    },
)
async def alert_journal(
    admin: Admin,
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AlertOut]:
    """Журнал тривог школи адміна (з API і ручних), найновіші першими."""
    raise not_implemented()
