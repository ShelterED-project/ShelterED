"""«Як ти зараз?» (docs/wellbeing-checkin.md): запис відповіді, перегляди з обмеженнями,
журнал переглядів і видалення старих відповідей.

Не тест, не скринінг і не діагноз. Значення ніколи не пишеться в лог і не обробляється ШІ.
Хто що бачить:
- учень — свої картинки за 14 днів (без журналу);
- батьки прив'язаної дитини — тижневе зведення словами (з журналом);
- вчитель і адміністрація — нічого (ні окремих відповідей, ні зведень класу чи школи).
"""

import datetime as dt
import uuid
from collections import Counter
from zoneinfo import ZoneInfo

from sqlalchemy import delete, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import User
from app.models.sync import SyncEvent
from app.models.wellbeing import WellbeingAnswer, WellbeingViewLog
from app.schemas.wellbeing import StudentWellbeingParent, StudentWellbeingSelf, WellbeingDay
from app.services.schedule import DEFAULT_TZ
from app.services.school import school_tz
from app.services.wellbeing_texts import MOOD_WORDS, PICTURES, TEXTS, mood_of

HISTORY_DAYS = 14  # учень бачить себе за 14 днів
WEEK_DAYS = 7  # зведення батькам
# М'який сигнал дитині: ≥ 3 з останніх 5 відповідей за 14 днів — «Гроза» чи «Дощик».
# Батькам — те саме вікно, що й зведення: ≥ 3 відповіді «Гроза»/«Дощик» за 7 днів.
SIGNAL_WINDOW_DAYS = 14
SIGNAL_LAST = 5
SIGNAL_LOW_COUNT = 3
LOW_MAX_VALUE = 2
PARENT_MIN_ANSWERS = 3  # менше — зведення не показуємо (інакше видно окремий день)
RETENTION_DAYS = 30
# Нічия в зведенні — на користь спокійнішого слова.
_TIE_ORDER = ("cloudy", "sunny", "hard")


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# ---------- запис (з POST /sync/events) ----------


async def apply_answer(
    session: AsyncSession,
    student_id: uuid.UUID,
    event_id: uuid.UUID,
    corrected_at: dt.datetime,
    value: int,
    tz: ZoneInfo,
    received_at: dt.datetime,
) -> bool:
    """Одна відповідь на день: пізніша замінює ранішу, рівний час — більший id події
    (детерміновано, незалежно від порядку надходження).

    `corrected_at` — час пристрою, виправлений на зсув годинника пакета; від нього і дата
    (за поясом школи), і порядок. Дата в майбутньому (пізніше за «сьогодні» школи на момент
    прийому) чи старша за строк зберігання — відповідь не записується (False): подія однаково
    `accepted`, щоб не блокувати outbox, але показувати чи зберігати таке нема сенсу."""
    today = received_at.astimezone(tz).date()
    answered_on = corrected_at.astimezone(tz).date()
    if not today - dt.timedelta(days=RETENTION_DAYS) <= answered_on <= today:
        return False
    stmt = pg_insert(WellbeingAnswer).values(
        id=event_id,
        student_id=student_id,
        answered_on=answered_on,
        value=value,
        occurred_at=corrected_at,
    )
    new = stmt.excluded
    cur = WellbeingAnswer.__table__.c
    await session.execute(
        stmt.on_conflict_do_update(
            index_elements=["student_id", "answered_on"],
            set_={"id": new.id, "value": new.value, "occurred_at": new.occurred_at},
            where=tuple_(new.occurred_at, new.id) > tuple_(cur.occurred_at, cur.id),
        )
    )
    return True


# ---------- перегляд ----------


async def _log_view(session: AsyncSession, viewer: User, student_id: uuid.UUID) -> None:
    session.add(WellbeingViewLog(viewer_id=viewer.id, student_id=student_id))
    await session.commit()


async def _answers(
    session: AsyncSession, student_id: uuid.UUID, since: dt.date, today: dt.date
) -> list[tuple[dt.date, int]]:
    """Відповіді за [since, today], від нових до старих (рядки «з майбутнього» не беремо)."""
    rows = await session.execute(
        select(WellbeingAnswer.answered_on, WellbeingAnswer.value)
        .where(
            WellbeingAnswer.student_id == student_id,
            WellbeingAnswer.answered_on.between(since, today),
        )
        .order_by(WellbeingAnswer.answered_on.desc())
    )
    return [(r.answered_on, r.value) for r in rows]


def _gentle_signal(answers: list[tuple[dt.date, int]], today: dt.date) -> bool:
    since = today - dt.timedelta(days=SIGNAL_WINDOW_DAYS - 1)
    last = [v for d, v in answers if since <= d <= today][:SIGNAL_LAST]
    return sum(v <= LOW_MAX_VALUE for v in last) >= SIGNAL_LOW_COUNT


async def student_view(
    session: AsyncSession, viewer: User, student: User, now: dt.datetime | None = None
) -> StudentWellbeingSelf | StudentWellbeingParent:
    """Учень — себе (картинки), батьки — тижневе зведення словами (перегляд у журнал)."""
    tz = await school_tz(session, student.school_id)
    today = (now or _now()).astimezone(tz).date()
    answers = await _answers(
        session,
        student.id,
        today - dt.timedelta(days=max(HISTORY_DAYS, SIGNAL_WINDOW_DAYS) - 1),
        today,
    )
    if viewer.role == "student":
        history_since = today - dt.timedelta(days=HISTORY_DAYS - 1)
        return StudentWellbeingSelf(
            student_id=student.id,
            days=[
                WellbeingDay(date=d, picture=PICTURES[v][0])  # type: ignore[arg-type]
                for d, v in answers
                if history_since <= d <= today
            ],
            show_support=_gentle_signal(answers, today),
        )

    week_from = today - dt.timedelta(days=WEEK_DAYS - 1)
    week = [v for d, v in answers if week_from <= d <= today]
    mood = None
    if len(week) >= PARENT_MIN_ANSWERS:
        counts = Counter(mood_of(v) for v in week)
        top = max(counts.values())
        mood = next(m for m in _TIE_ORDER if counts[m] == top)
    # М'який рядок батькам — лише з відповідей того самого тижня, що й зведення (не може
    # з'явитися поруч із «замало відповідей» і не розкриває старіші дні).
    parent_signal = len(week) >= PARENT_MIN_ANSWERS and (
        sum(v <= LOW_MAX_VALUE for v in week) >= SIGNAL_LOW_COUNT
    )
    texts = TEXTS["parent"]
    await _log_view(session, viewer, student.id)
    return StudentWellbeingParent(
        student_id=student.id,
        week_from=week_from,
        week_to=today,
        mood=mood,  # type: ignore[arg-type]
        summary=texts["summary"].format(word=MOOD_WORDS[mood]) if mood else texts["not_enough"],
        gentle_note=texts["gentle_note"] if parent_signal else None,
        tips=list(texts["tips"]) if parent_signal else [],
    )


# ---------- зберігання ----------


async def purge_old(session: AsyncSession, now: dt.datetime | None = None) -> dict[str, int]:
    """Строк зберігання 30 днів. Видаляє:
    - відповіді, старші за 30 днів за датою відповіді, і датовані в майбутньому (запас — один
      день на пояс школи, відмінний від Києва; такі рядки могли лишитися лише від старих
      версій, нові запис не пропускає);
    - записи `sync_event` типу `survey_answer`, отримані понад 30 днів тому: payload у них
      порожній, але видно, коли й з якого пристрою дитина відповідала.

    Ідемпотентно й безпечно в будь-який момент (зокрема при старті воркера): повторний запуск
    видаляє лише те, що ще лишилось. Повторно надіслана подія після видалення її запису
    прийметься знову, але її дата вже поза строком — відповідь не запишеться."""
    now = now or _now()
    today = now.astimezone(ZoneInfo(DEFAULT_TZ)).date()
    answers = await session.execute(
        delete(WellbeingAnswer).where(
            or_(
                WellbeingAnswer.answered_on < today - dt.timedelta(days=RETENTION_DAYS),
                WellbeingAnswer.answered_on > today + dt.timedelta(days=1),
            )
        )
    )
    events = await session.execute(
        delete(SyncEvent).where(
            SyncEvent.type == "survey_answer",
            SyncEvent.received_at < now - dt.timedelta(days=RETENTION_DAYS),
        )
    )
    await session.commit()
    return {"answers": answers.rowcount or 0, "events": events.rowcount or 0}
