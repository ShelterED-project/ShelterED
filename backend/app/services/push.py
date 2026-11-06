"""Web Push (B8): підписки пристроїв, одержувачі повідомлень, доставка одній підписці.

Payload пушу мінімальний: тип + id, без імен і персональних даних. Одержувачі за типом:
- `alert`, `all_clear` — учні класу, вчителі класу, батьки учнів класу;
- `pack_updated` — учні й вчителі класу;
- `rollcall_status` — батьки цієї дитини (B12.4).
Лише активні користувачі. Endpoint і ключі підписки в логи не пишемо (лише id підписки й хост).
"""

import datetime as dt
import json
import logging
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

import anyio
from sqlalchemy import delete, select, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.models.push import PushSubscription
from app.models.school import ClassMembership, ParentChild, User
from app.schemas.push import PushSubscriptionCreate
from app.services.idempotency import id_conflict

logger = logging.getLogger(__name__)

PushType = Literal["alert", "all_clear", "pack_updated", "rollcall_status"]


@dataclass(frozen=True)
class PushOptions:
    ttl: int  # с: скільки push-сервіс тримає повідомлення для пристрою офлайн
    urgency: Literal["very-low", "low", "normal", "high"]


# Тривога й відбій — високий пріоритет і короткий TTL (через годину вже неактуально, а
# актуальний стан клієнт однаково бере з GET /alerts/active). Статус дитини для батьків —
# високий пріоритет. Пакет — звичайний пріоритет, довгий TTL.
PUSH_OPTIONS: dict[str, PushOptions] = {
    "alert": PushOptions(ttl=600, urgency="high"),
    "all_clear": PushOptions(ttl=600, urgency="high"),
    "rollcall_status": PushOptions(ttl=3600, urgency="high"),
    "pack_updated": PushOptions(ttl=12 * 3600, urgency="normal"),
}


def endpoint_host(endpoint: str) -> str:
    """Для логів: лише хост push-сервісу (повний URL — секрет підписки)."""
    return urlsplit(endpoint).hostname or "?"


# ---------- підписки ----------


async def _trim(session: AsyncSession, user_id: uuid.UUID, limit: int) -> None:
    """Понад ліміт пристроїв на користувача видаляються спершу підписки з `failed_at`, далі
    найдавніші за `created_at`. Не за `updated_at`: він змінюється й від спроб доставки."""
    keep = (
        select(PushSubscription.id)
        .where(PushSubscription.user_id == user_id)
        .order_by(
            PushSubscription.failed_at.is_not(None),
            PushSubscription.created_at.desc(),
            PushSubscription.id.desc(),
        )
        .limit(limit)
    )
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id, PushSubscription.id.not_in(keep)
        )
    )


def _refresh(sub: PushSubscription, user: User, body: PushSubscriptionCreate) -> None:
    sub.user_id = user.id
    sub.p256dh = body.keys.p256dh
    sub.auth = body.keys.auth
    sub.failed_at = None


async def subscribe(
    session: AsyncSession, user: User, body: PushSubscriptionCreate, settings: Settings
) -> tuple[PushSubscription, bool]:
    """Ідемпотентно (commit — тут). Повертає (підписка, створена).

    - Той самий `endpoint` (будь-чий) — наявна підписка, переприв'язана до поточного
      користувача з новими ключами (на пристрої увійшов інший користувач): 200, її `id`.
    - Той самий `id` цього користувача з іншим endpoint — оновлення підписки (браузер
      перевидав її): 200. Той самий `id` чужої підписки — 409 `ID_CONFLICT`.
    - Інакше — нова: 201.
    """
    for _ in range(2):
        sub = await session.scalar(
            select(PushSubscription)
            .where(PushSubscription.endpoint == body.endpoint)
            .with_for_update()
        )
        if sub is None:
            sub = await session.get(PushSubscription, body.id, with_for_update=True)
            if sub is not None:
                if sub.user_id != user.id:
                    raise id_conflict(["user_id"])
                sub.endpoint = body.endpoint
        if sub is not None:
            _refresh(sub, user, body)
            await session.flush()
            await _trim(session, user.id, settings.push_max_subscriptions_per_user)
            await session.commit()
            return sub, False
        inserted = await session.scalar(
            pg_insert(PushSubscription)
            .values(
                id=body.id,
                user_id=user.id,
                endpoint=body.endpoint,
                p256dh=body.keys.p256dh,
                auth=body.keys.auth,
            )
            .on_conflict_do_nothing()
            .returning(PushSubscription.id)
        )
        if inserted is not None:
            await _trim(session, user.id, settings.push_max_subscriptions_per_user)
            await session.commit()
            sub = await session.get(PushSubscription, inserted, populate_existing=True)
            assert sub is not None
            return sub, True
        # Паралельний запит щойно вставив той самий id чи endpoint — перечитуємо.
    raise AppError("CONFLICT", "Concurrent subscription update, retry", status_code=409)


async def unsubscribe(session: AsyncSession, user: User, subscription_id: uuid.UUID) -> None:
    """Ідемпотентно видаляє власну підписку. Неіснуюча, вже видалена чи чужа — без дії й без
    помилки (чужу не видаляємо і не розкриваємо, що вона є)."""
    await session.execute(
        delete(PushSubscription).where(
            PushSubscription.id == subscription_id, PushSubscription.user_id == user.id
        )
    )
    await session.commit()


# ---------- одержувачі ----------


def _uuid(payload: Mapping[str, Any], key: str) -> uuid.UUID | None:
    value = payload.get(key)
    try:
        return uuid.UUID(str(value)) if value else None
    except ValueError:
        return None


async def recipients(session: AsyncSession, payload: Mapping[str, Any]) -> list[uuid.UUID]:
    """Активні користувачі, яким іде push цього типу (див. docstring модуля)."""
    push_type = payload.get("type")
    queries = []
    if push_type in ("alert", "all_clear", "pack_updated"):
        class_id = _uuid(payload, "class_id")
        if class_id is None:
            return []
        members = select(ClassMembership.user_id).where(ClassMembership.class_id == class_id)
        queries.append(members)
        if push_type != "pack_updated":
            students = select(ClassMembership.user_id).where(
                ClassMembership.class_id == class_id, ClassMembership.member_role == "student"
            )
            queries.append(select(ParentChild.parent_id).where(ParentChild.child_id.in_(students)))
    elif push_type == "rollcall_status":
        student_id = _uuid(payload, "student_id")
        if student_id is None:
            return []
        queries.append(select(ParentChild.parent_id).where(ParentChild.child_id == student_id))
    else:
        return []
    ids = union(*queries).subquery() if len(queries) > 1 else queries[0].subquery()
    rows = await session.scalars(
        select(User.id).where(User.id.in_(select(ids.c[0])), User.is_active.is_(True))
    )
    return list(rows)


async def subscriptions_of(session: AsyncSession, user_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    if not user_ids:
        return []
    rows = await session.scalars(
        select(PushSubscription.id)
        .where(PushSubscription.user_id.in_(user_ids))
        .order_by(PushSubscription.id)
    )
    return list(rows)


# ---------- доставка ----------


class PushRetry(Exception):
    """Тимчасова помилка push-сервісу (429/5xx, мережа): повторити пізніше."""

    def __init__(self, status: int | None, retry_after: int | None = None) -> None:
        super().__init__(f"status={status}")
        self.status = status
        self.retry_after = retry_after


@dataclass(frozen=True)
class SendResult:
    """Відповідь push-сервісу: HTTP-статус і заголовок Retry-After (с), якщо є."""

    status: int
    retry_after: int | None = None


@dataclass(frozen=True)
class PushTarget:
    """Знімок полів підписки для відправки (поза транзакцією БД)."""

    id: uuid.UUID
    endpoint: str
    p256dh: str
    auth: str


# Статус від sender: payload не зашифрувати ключами підписки (не точка P-256 тощо) — постійна
# помилка, повтор не допоможе.
INVALID_KEYS = -1

# (підписка, payload JSON, налаштування, опції) -> статус. Мережева помилка — status 0.
Sender = Callable[[PushTarget, str, Settings, PushOptions], SendResult]

Outcome = Literal["sent", "gone", "invalid", "failed", "missing", "duplicate", "disabled"]


async def deliver(
    session: AsyncSession,
    subscription_id: uuid.UUID,
    payload: Mapping[str, Any],
    settings: Settings,
    sender: Sender,
    now: dt.datetime | None = None,
) -> Outcome:
    """Надсилає payload одній підписці (commit — тут).

    2xx → `sent` (`last_success_at`); 404/410 → підписка видаляється (`gone`); ключі підписки
    непридатні для шифрування (`INVALID_KEYS`) → видаляється без повторів (`invalid`); 429/5xx
    чи мережа → `PushRetry`; інші 4xx (ключі не ті, завеликий payload) → `failed` (`failed_at`).
    HTTP-запит іде в окремому потоці й поза транзакцією: поля підписки читаються, транзакція
    закривається, результат пишеться короткою окремою транзакцією (якщо за цей час підписку
    перевидали з іншим endpoint чи ключами — результат старої відправки її не чіпає).
    Дедуплікацію повторів робить задача (`app.workers.push`)."""
    if not settings.push_enabled:
        return "disabled"
    sub = await session.get(PushSubscription, subscription_id)
    if sub is None:
        await session.commit()
        return "missing"
    target = PushTarget(id=sub.id, endpoint=sub.endpoint, p256dh=sub.p256dh, auth=sub.auth)
    await session.commit()
    options = PUSH_OPTIONS.get(str(payload.get("type")), PushOptions(ttl=3600, urgency="normal"))
    data = json.dumps(dict(payload), separators=(",", ":"), sort_keys=True)
    result = await anyio.to_thread.run_sync(sender, target, data, settings, options)
    now = now or dt.datetime.now(dt.UTC)
    host = endpoint_host(target.endpoint)
    if result.status in (0, 429) or result.status >= 500:
        raise PushRetry(result.status, result.retry_after)

    sub = await session.get(PushSubscription, target.id, populate_existing=True)
    if sub is None or sub.endpoint != target.endpoint:
        await session.commit()
        return "missing"
    same_keys = (sub.p256dh, sub.auth) == (target.p256dh, target.auth)
    outcome: Outcome
    if 200 <= result.status < 300:
        sub.last_success_at = now
        outcome = "sent"
    elif result.status in (404, 410):
        logger.info("Push subscription expired, removed: id=%s host=%s", sub.id, host)
        await session.delete(sub)
        outcome = "gone"
    elif result.status == INVALID_KEYS:
        logger.warning("Push subscription keys unusable, removed: id=%s host=%s", sub.id, host)
        if same_keys:
            await session.delete(sub)
        outcome = "invalid"
    else:
        logger.warning("Push rejected: id=%s host=%s status=%d", sub.id, host, result.status)
        if same_keys:
            sub.failed_at = now
        outcome = "failed"
    await session.commit()
    return outcome


async def mark_failed(
    session: AsyncSession, subscription_id: uuid.UUID, now: dt.datetime | None = None
) -> None:
    """Повтори вичерпано: позначка `failed_at` (підписку не видаляємо — сервіс міг лежати)."""
    sub = await session.get(PushSubscription, subscription_id)
    if sub is not None:
        sub.failed_at = now or dt.datetime.now(dt.UTC)
        await session.commit()
