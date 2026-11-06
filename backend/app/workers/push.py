"""Web Push (B8, черга `push`): постановка, розсилка по підписках, доставка.

`enqueue_push` (після commit) → `push.send` визначає одержувачів і ставить `push.deliver` на
кожну підписку → `push.deliver` шифрує й надсилає payload (pywebpush). Payload мінімальний:
тип + id, без персональних даних (`app.services.push`).

Ідемпотентність: у кожного повідомлення є ключ (`key`); перед відправкою підписці задача
бере в Redis `SET NX` на (ключ, підписка) з TTL — повтор задачі (acks_late, повторна
доставка брокером) не надсилає те саме вдруге. Тимчасова помилка знімає ключ і повторює
з відступом. Redis недоступний — надсилаємо без дедуплікації (fail-open: дубль тривоги
кращий за пропущену). Збій воркера між `SET NX` і відправкою — повідомлення не дійде
(at-most-once для цієї підписки); актуальний стан клієнт однаково бере з API.
"""

import asyncio
import hashlib
import json
import logging
import uuid
from typing import Any

import requests
from celery import Task
from py_vapid import Vapid
from pywebpush import WebPushException, webpush
from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings, get_settings
from app.core.db import standalone_session
from app.models.push import PushSubscription
from app.services import push as service
from app.services.push import PushOptions, PushRetry, PushType, SendResult
from app.workers.celery_app import celery_app, enqueue

logger = logging.getLogger(__name__)

# Скільки пам'ятаємо, що повідомлення вже надіслане підписці.
DEDUPE_TTL_S = 24 * 3600
# Повтори тимчасових помилок: 30 с, 1, 2, 4, 8 хв (не довше за `MAX_RETRY_DELAY_S`).
MAX_RETRIES = 5
RETRY_BASE_S = 30
MAX_RETRY_DELAY_S = 15 * 60
HTTP_TIMEOUT_S = 10


def notification_key(payload: dict[str, str | None]) -> str:
    """Ключ за замовчуванням — хеш payload: та сама подія (тривога класу, пакет) дає той
    самий ключ, тож навіть подвійна постановка не надсилає її двічі."""
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


async def enqueue_push(
    push_type: PushType,
    *,
    class_id: uuid.UUID | None = None,
    key: str | None = None,
    **ids: object,
) -> None:
    """Єдина точка постановки push (після commit). Одержувачів за типом визначає `push.send`.
    `ids`: alert_id, lesson_id, pack_id, student_id, session_id, status тощо — лише id і коди.
    `key` — ідентичність повідомлення для дедуплікації (за замовчуванням — хеш payload)."""
    payload: dict[str, str | None] = {"type": push_type}
    if class_id is not None:
        payload["class_id"] = str(class_id)
    payload.update({k: None if v is None else str(v) for k, v in ids.items()})
    await enqueue("push.send", args=[payload, key or notification_key(payload)], queue="push")


# ---------- розсилка ----------


async def _fan_out(payload: dict[str, str | None]) -> list[uuid.UUID]:
    async with standalone_session() as session:
        users = await service.recipients(session, payload)
        return await service.subscriptions_of(session, users)


@celery_app.task(name="push.send")
def send(payload: dict[str, str | None], key: str | None = None) -> int:
    """Ставить `push.deliver` на кожну підписку одержувачів. Повертає кількість підписок."""
    if not get_settings().push_enabled:
        logger.warning("Push %s skipped: VAPID keys are not configured", payload.get("type"))
        return 0
    key = key or notification_key(payload)
    subscriptions = asyncio.run(_fan_out(payload))
    for sub_id in subscriptions:
        deliver.apply_async(args=[str(sub_id), payload, key], queue="push")
    logger.info("Push %s fan-out: %d subscriptions", payload.get("type"), len(subscriptions))
    return len(subscriptions)


# ---------- доставка ----------


def _retry_after(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None  # HTTP-дата замість секунд — беремо свій відступ


def webpush_sender(
    sub: PushSubscription, data: str, settings: Settings, options: PushOptions
) -> SendResult:
    """Відправка через pywebpush. Текст помилки (може містити endpoint) не логуємо."""
    assert settings.vapid_private_key is not None and settings.vapid_subject
    try:
        response = webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=data,
            vapid_private_key=Vapid.from_string(settings.vapid_private_key.get_secret_value()),
            # Новий словник щоразу: pywebpush дописує в нього aud і exp.
            vapid_claims={"sub": settings.vapid_subject},
            ttl=options.ttl,
            headers={"Urgency": options.urgency},
            timeout=HTTP_TIMEOUT_S,
        )
    except WebPushException as exc:
        if exc.response is None:
            return SendResult(0)
        return SendResult(
            exc.response.status_code, _retry_after(exc.response.headers.get("Retry-After"))
        )
    except requests.RequestException:
        return SendResult(0)
    return SendResult(response.status_code)  # type: ignore[union-attr]  # curl=False → Response


def _dedupe_key(key: str, sub_id: str) -> str:
    return f"sheltered:push:sent:{key}:{sub_id}"


def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)


def claim(key: str, sub_id: str) -> bool:
    """True — надсилати (перша спроба або Redis недоступний, fail-open)."""
    try:
        with _redis() as redis:
            return bool(redis.set(_dedupe_key(key, sub_id), 1, nx=True, ex=DEDUPE_TTL_S))
    except (RedisError, OSError) as exc:
        logger.warning("Push dedup unavailable, sending anyway: %s", type(exc).__name__)
        return True


def release(key: str, sub_id: str) -> None:
    try:
        with _redis() as redis:
            redis.delete(_dedupe_key(key, sub_id))
    except (RedisError, OSError) as exc:
        logger.warning("Push dedup unavailable: %s", type(exc).__name__)


async def _deliver(sub_id: uuid.UUID, payload: dict[str, Any]) -> service.Outcome:
    async with standalone_session() as session:
        return await service.deliver(session, sub_id, payload, get_settings(), webpush_sender)


async def _mark_failed(sub_id: uuid.UUID) -> None:
    async with standalone_session() as session:
        await service.mark_failed(session, sub_id)


def retry_delay(retries: int, retry_after: int | None) -> int:
    delay = RETRY_BASE_S * 2**retries
    if retry_after is not None:
        delay = max(delay, retry_after)
    return min(delay, MAX_RETRY_DELAY_S)


@celery_app.task(name="push.deliver", bind=True, max_retries=MAX_RETRIES)
def deliver(self: Task, subscription_id: str, payload: dict[str, Any], key: str) -> str:
    """Одне повідомлення одній підписці; повтор задачі те саме вдруге не надсилає."""
    if not claim(key, subscription_id):
        return "duplicate"
    sub_id = uuid.UUID(subscription_id)
    try:
        return asyncio.run(_deliver(sub_id, payload))
    except PushRetry as exc:
        release(key, subscription_id)
        if self.request.retries >= MAX_RETRIES:
            logger.warning(
                "Push gave up after %d retries: id=%s status=%s",
                MAX_RETRIES,
                subscription_id,
                exc.status,
            )
            asyncio.run(_mark_failed(sub_id))
            return "failed"
        raise self.retry(
            countdown=retry_delay(self.request.retries, exc.retry_after), exc=exc
        ) from None
    except Exception:
        release(key, subscription_id)
        raise
