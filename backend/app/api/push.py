"""Підписки Web Push (заглушки B4, логіка — B8)."""

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser
from app.api.stub import R501, example_of, not_implemented
from app.schemas.errors import ErrorResponse
from app.schemas.push import PushSubscriptionCreate, PushSubscriptionOut

router = APIRouter(tags=["push"])

R401 = {401: {"model": ErrorResponse, "description": "Не автентифіковано"}}
R404 = {404: {"model": ErrorResponse, "description": "Не знайдено"}}


@router.post(
    "/push/subscriptions",
    response_model=PushSubscriptionOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: example_of(PushSubscriptionOut, "Підписку збережено"),
        200: {"description": "Повтор із тим самим endpoint: наявна підписка"},
        **R401,
        **R501,
    },
)
async def subscribe(body: PushSubscriptionCreate, user: CurrentUser) -> PushSubscriptionOut:
    """Підписка пристрою на Web Push (будь-яка роль). Payload пушів мінімальний: тип + id."""
    raise not_implemented()


@router.delete(
    "/push/subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**R401, **R404, **R501},
)
async def unsubscribe(subscription_id: uuid.UUID, user: CurrentUser) -> Response:
    """Видаляє власну підписку. Ідемпотентно (повтор — теж 204)."""
    raise not_implemented()
