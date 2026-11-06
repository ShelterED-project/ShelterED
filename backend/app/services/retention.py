"""Строки зберігання (B15.1, docs/data-inventory.md): щоденне прибирання сирих даних, які
після певного часу не потрібні. Ідемпотентно: повторний запуск змінює лише те, що лишилось.

- `sync_event`: після `RETENTION_SYNC_EVENT_DAYS` (180) payload стирається (`{}`), а рядок
  лишається — на ньому тримається ідемпотентність (PK `client_event_id`: повтор старої події
  дає `duplicate`, а не другу спробу) і FK зі спроб, прогресу та переклички. Результат події вже
  живе у своїй таблиці (`attempt.answers`, `module_progress`, `rollcall_status`). Відхилені
  події (на них ніщо не посилається) видаляються цілком: повтор такої події після цього строку
  оброблявся б наново — пристрій стільки офлайн не буває (outbox прибирає подію, щойно отримав
  відповідь), тож строк із великим запасом над горизонтом офлайну (дні–тижні).
- `refresh_token`, `auth_code`: через `RETENTION_AUTH_DAYS` (7) після закінчення строку дії.
  Прострочений токен чи код і так не працює; запас — щоб повтор старого refresh-токена ще
  кілька днів після строку відкликав родину (виявлення крадіжки).
- `parent_link_code`: через `RETENTION_PARENT_LINK_CODE_DAYS` (30) після закінчення строку
  (використаний чи ні).
- `wellbeing_view_log`: `RETENTION_WELLBEING_VIEW_LOG_DAYS` (365).

Сирі відповіді «Як ти зараз?» (30 днів) прибирає окрема задача `wellbeing.purge`.
"""

import datetime as dt

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.auth import AuthCode, ParentLinkCode, RefreshToken
from app.models.sync import SyncEvent
from app.models.wellbeing import WellbeingViewLog


def _days(n: int) -> dt.timedelta:
    return dt.timedelta(days=n)


async def purge(
    session: AsyncSession, settings: Settings, now: dt.datetime | None = None
) -> dict[str, int]:
    """Кількість змінених рядків по кожному правилу (значень не повертає й не логує)."""
    now = now or dt.datetime.now(dt.UTC)
    events_before = now - _days(settings.retention_sync_event_days)
    auth_before = now - _days(settings.retention_auth_days)
    counts: dict[str, int] = {}

    result = await session.execute(
        delete(SyncEvent).where(
            SyncEvent.received_at < events_before, SyncEvent.status == "rejected"
        )
    )
    counts["sync_event_rejected"] = result.rowcount or 0
    result = await session.execute(
        update(SyncEvent)
        .where(SyncEvent.received_at < events_before, SyncEvent.payload != {})
        .values(payload={})
    )
    counts["sync_event_payloads"] = result.rowcount or 0

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
