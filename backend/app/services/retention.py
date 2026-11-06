"""Строки зберігання (B15.1, docs/data-inventory.md): щоденне прибирання сирих даних, які
після певного часу не потрібні. Ідемпотентно: повторний запуск змінює лише те, що лишилось.

- `sync_event`: після `RETENTION_SYNC_EVENT_DAYS` (180) стираються payload (`{}`), `device_id`
  і `clock_skew_ms` (NULL); `is_suspicious` лишається (його бачить вчитель). Рядок
  лишається — на ньому тримається ідемпотентність (PK `client_event_id`: повтор старої події
  дає `duplicate`, а не другу спробу) і FK зі спроб, прогресу та переклички. Результат події вже
  живе у своїй таблиці (`attempt.answers`, `module_progress`, `rollcall_status`). Відхилені
  події (на них ніщо не посилається) видаляються цілком: повтор такої події після цього строку
  оброблявся б наново — пристрій стільки офлайн не буває (outbox прибирає подію, щойно отримав
  відповідь), тож строк із великим запасом над горизонтом офлайну (дні–тижні).
  Обробка пакетами по `SYNC_EVENT_BATCH` рядків, кожен у своїй короткій транзакції (без
  довгих блокувань), не довше `SYNC_EVENT_MAX_S` за запуск — решту добере наступний запуск.
  Вибірка йде частковим індексом `ix_sync_event_retention` (`received_at` WHERE
  `device_id IS NOT NULL`): очищені рядки з нього випадають.
- `refresh_token`, `auth_code`: через `RETENTION_AUTH_DAYS` (7) після закінчення строку дії.
  Прострочений токен чи код і так не працює; запас — щоб повтор старого refresh-токена ще
  кілька днів після строку відкликав родину (виявлення крадіжки).
- `parent_link_code`: через `RETENTION_PARENT_LINK_CODE_DAYS` (30) після закінчення строку
  (використаний чи ні).
- `wellbeing_view_log`: `RETENTION_WELLBEING_VIEW_LOG_DAYS` (365).

Сирі відповіді «Як ти зараз?» (30 днів) прибирає окрема задача `wellbeing.purge`.
"""

import datetime as dt
import time

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.auth import AuthCode, ParentLinkCode, RefreshToken
from app.models.sync import SyncEvent
from app.models.wellbeing import WellbeingViewLog

SYNC_EVENT_BATCH = 5000
SYNC_EVENT_MAX_S = 300.0


def _days(n: int) -> dt.timedelta:
    return dt.timedelta(days=n)


async def _purge_sync_events(
    session: AsyncSession, before: dt.datetime, batch_size: int, max_s: float
) -> tuple[int, int]:
    """(видалено відхилених, очищено прийнятих). Кожен пакет — окремий commit."""
    deadline = time.monotonic() + max_s
    rejected = cleared = 0
    while True:
        ids = list(
            await session.scalars(
                select(SyncEvent.client_event_id)
                .where(SyncEvent.received_at < before, SyncEvent.device_id.is_not(None))
                .order_by(SyncEvent.received_at)
                .limit(batch_size)
                .with_for_update(skip_locked=True)
            )
        )
        if not ids:
            break
        result = await session.execute(
            delete(SyncEvent).where(
                SyncEvent.client_event_id.in_(ids), SyncEvent.status == "rejected"
            )
        )
        rejected += result.rowcount or 0
        result = await session.execute(
            update(SyncEvent)
            .where(SyncEvent.client_event_id.in_(ids), SyncEvent.status != "rejected")
            .values(payload={}, device_id=None, clock_skew_ms=None)
        )
        cleared += result.rowcount or 0
        await session.commit()
        if len(ids) < batch_size or time.monotonic() >= deadline:
            break
    return rejected, cleared


async def purge(
    session: AsyncSession,
    settings: Settings,
    now: dt.datetime | None = None,
    *,
    batch_size: int = SYNC_EVENT_BATCH,
    max_s: float = SYNC_EVENT_MAX_S,
) -> dict[str, int]:
    """Кількість змінених рядків по кожному правилу (значень не повертає й не логує)."""
    now = now or dt.datetime.now(dt.UTC)
    events_before = now - _days(settings.retention_sync_event_days)
    auth_before = now - _days(settings.retention_auth_days)
    counts: dict[str, int] = {}

    counts["sync_event_rejected"], counts["sync_event_payloads"] = await _purge_sync_events(
        session, events_before, batch_size, max_s
    )

    # Посилання `replaced_by_id` на токени, що видаляються, спершу обнуляються (FK без каскаду).
    stale = select(RefreshToken.id).where(RefreshToken.expires_at < auth_before)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.replaced_by_id.in_(stale))
        .values(replaced_by_id=None)
    )
    result = await session.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < auth_before)
    )
    counts["refresh_tokens"] = result.rowcount or 0
    result = await session.execute(delete(AuthCode).where(AuthCode.expires_at < auth_before))
    counts["auth_codes"] = result.rowcount or 0
    result = await session.execute(
        delete(ParentLinkCode).where(
            ParentLinkCode.expires_at < now - _days(settings.retention_parent_link_code_days)
        )
    )
    counts["parent_link_codes"] = result.rowcount or 0
    result = await session.execute(
        delete(WellbeingViewLog).where(
            WellbeingViewLog.viewed_at < now - _days(settings.retention_wellbeing_view_log_days)
        )
    )
    counts["wellbeing_view_log"] = result.rowcount or 0
    await session.commit()
    return counts
