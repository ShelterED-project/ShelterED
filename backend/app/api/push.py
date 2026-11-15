"""Web Push: ключ VAPID і підписки пристроїв (B8)."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, Session, SettingsDep
from app.api.stub import example_of
from app.core.errors import AppError
from app.schemas.errors import ErrorResponse
from app.schemas.push import PushSubscriptionCreate, PushSubscriptionOut, VapidKeyOut
from app.services import push as service

router = APIRouter(tags=["push"])

R401 = {401: {"model": ErrorResponse, "description": "Не автентифіковано"}}


@router.get(
    "/push/vapid-key",
    response_model=VapidKeyOut,
    responses={
        200: example_of(VapidKeyOut),
        **R401,
        503: {"model": ErrorResponse, "description": "PUSH_NOT_CONFIGURED: ключі VAPID не задані"},
    },
)
async def vapid_key(user: CurrentUser, settings: SettingsDep) -> VapidKeyOut:
    """Публічний ключ VAPID (`applicationServerKey` для `pushManager.subscribe`)."""
    if not settings.push_enabled or not settings.vapid_public_key:
        raise AppError("PUSH_NOT_CONFIGURED", "Web Push is not configured", status_code=503)
    return VapidKeyOut(public_key=settings.vapid_public_key)


@router.post(
    "/push/subscriptions",
    response_model=PushSubscriptionOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: example_of(PushSubscriptionOut, "Підписку збережено"),
        200: {"description": "Повтор із тим самим endpoint чи id: наявна підписка"},
        **R401,
        409: {"model": ErrorResponse, "description": "ID_CONFLICT: id чужої підписки"},
    },
)
async def subscribe(
    body: PushSubscriptionCreate,
    user: CurrentUser,
    session: Session,
    settings: SettingsDep,
    response: Response,
) -> PushSubscriptionOut:
    """Підписка пристрою на Web Push (будь-яка роль). Payload пушів мінімальний: тип + id.

    Ідемпотентно: той самий `endpoint` — наявна підписка (переприв'язана до поточного
    користувача, з новими ключами; її `id` клієнт зберігає); той самий `id` власної
    підписки з новим `endpoint` — оновлення. До `PUSH_MAX_SUBSCRIPTIONS_PER_USER` (10)
    пристроїв на користувача, понад ліміт найдавніші видаляються."""
    sub, created = await service.subscribe(session, user, body, settings)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return PushSubscriptionOut.model_validate(sub)


@router.delete(
    "/push/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Підписки цього користувача з таким id більше немає"},
        **R401,
    },
)
async def unsubscribe(subscription_id: uuid.UUID, user: CurrentUser, session: Session) -> Response:
    """Ідемпотентно видаляє власну підписку: повтор, неіснуюча чи чужа — теж 204 (чужа не
    видаляється, і відповідь не розкриває, чи вона існує)."""
    await service.unsubscribe(session, user, subscription_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
