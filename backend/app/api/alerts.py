"""Тривоги: ручна кнопка, відбій, активні тривоги, журнал (B7).

Тривоги з API бекенд опитує й розбирає сам (Celery beat `alerts.poll`); публічного вебхука немає.
"""

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import Admin, CurrentUser, Session, SettingsDep, Staff
from app.api.stub import example, example_of
from app.schemas.alerts import ALERT_EXAMPLES, ActiveAlertsOut, AlertOut, ManualAlertCreate
from app.schemas.errors import ErrorResponse
from app.services import alerts as service

router = APIRouter(tags=["alerts"])

R401 = {401: {"model": ErrorResponse, "description": "Не автентифіковано"}}
R403 = {403: {"model": ErrorResponse, "description": "Недостатньо прав"}}
R404 = {404: {"model": ErrorResponse, "description": "Не знайдено"}}
R409 = {409: {"model": ErrorResponse, "description": "ID_CONFLICT / ALERT_NOT_MANUAL"}}


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
        **R409,
    },
)
async def manual_alert(
    body: ManualAlertCreate, user: Staff, session: Session, response: Response
) -> AlertOut:
    """Ручна кнопка «Тривога» для класу (зокрема тренувальна): вчитель цього класу або
    адміністрація його школи. Відкриває перекличку класу й ставить push класу з id уроку,
    що йде зараз. Ідемпотентно за `id` (повтор — 200 без нового push); чужий клас — 403."""
    alert, created = await service.create_manual(session, user, body)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return AlertOut.model_validate(alert)


@router.post(
    "/alerts/{alert_id}/end",
    response_model=AlertOut,
    responses={
        200: example({**ALERT_EXAMPLES["manual"], "ended_at": "2026-11-05T09:50:00Z"}),
        **R401,
        **R403,
        **R404,
        **R409,
    },
)
async def end_alert(alert_id: uuid.UUID, user: Staff, session: Session) -> AlertOut:
    """Відбій ручної тривоги вчителем її класу або адміністрацією школи; закриває
    перекличку й ставить push «відбій». Ідемпотентно. Тривога з API закінчується лише
    з API (409 `ALERT_NOT_MANUAL`)."""
    return AlertOut.model_validate(await service.end_manual(session, user, alert_id))


@router.get(
    "/alerts/active",
    response_model=ActiveAlertsOut,
    responses={200: example_of(ActiveAlertsOut), **R401},
)
async def active_alerts(
    user: CurrentUser, session: Session, settings: SettingsDep
) -> ActiveAlertsOut:
    """Активні тривоги для шкіл і класів користувача (батьки — шкіл і класів своїх дітей,
    адміністрація — усієї школи). Запасний шлях для клієнта, який не отримав push.
    `source_available = false` — API тривог давно не відповідало: лишається ручна кнопка."""
    alerts = await service.active_alerts(session, user)
    return ActiveAlertsOut(
        alerts=[AlertOut.model_validate(a) for a in alerts],
        source_available=await service.source_available(session, settings),
    )


@router.get(
    "/alerts",
    response_model=list[AlertOut],
    responses={
        200: example([{**ALERT_EXAMPLES["api"], "ended_at": "2026-11-05T10:45:00Z"}]),
        **R401,
        **R403,
    },
)
async def alert_journal(
    admin: Admin,
    session: Session,
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AlertOut]:
    """Журнал тривог школи адміна (з API і ручних), найновіші першими.
    `from`/`to` — дати за київським часом, включно."""
    rows = await service.journal(session, admin, date_from, date_to, limit, offset)
    return [AlertOut.model_validate(a) for a in rows]
