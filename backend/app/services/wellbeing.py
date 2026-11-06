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

from sqlalchemy import delete, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.school import User
from app.models.wellbeing import WellbeingAnswer, WellbeingViewLog
from app.schemas.wellbeing import StudentWellbeingParent, StudentWellbeingSelf, WellbeingDay
from app.services.schedule import DEFAULT_TZ
from app.services.school import school_tz
from app.services.wellbeing_texts import MOOD_WORDS, PICTURES, TEXTS, mood_of

HISTORY_DAYS = 14  # учень бачить себе за 14 днів
WEEK_DAYS = 7  # зведення батькам
# М'який сигнал: ≥ 3 з останніх 5 відповідей за 14 днів — «Гроза» чи «Дощик».
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
    occurred_at: dt.datetime,
    value: int,
) -> None:
    """Одна відповідь на день (дата за поясом школи): пізніша за `occurred_at` замінює ранішу,
    рівний час — більший id події (детерміновано, незалежно від порядку надходження)."""
    school_id = await session.scalar(select(User.school_id).where(User.id == student_id))
    tz = await school_tz(session, school_id)
    stmt = pg_insert(WellbeingAnswer).values(
        id=event_id,
        student_id=student_id,
        answered_on=occurred_at.astimezone(tz).date(),
        value=value,
        occurred_at=occurred_at,
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


# ---------- перегляд ----------


async def _log_view(session: AsyncSession, viewer: User, student_id: uuid.UUID) -> None:
    session.add(WellbeingViewLog(viewer_id=viewer.id, student_id=student_id))
    await session.commit()


async def _answers(
    session: AsyncSession, student_id: uuid.UUID, since: dt.date
) -> list[tuple[dt.date, int]]:
    rows = await session.execute(
        select(WellbeingAnswer.answered_on, WellbeingAnswer.value)
        .where(WellbeingAnswer.student_id == student_id, WellbeingAnswer.answered_on >= since)
        .order_by(WellbeingAnswer.answered_on.desc())
    )
    return [(r.answered_on, r.value) for r in rows]


def _gentle_signal(answers: list[tuple[dt.date, int]], today: dt.date) -> bool:
    since = today - dt.timedelta(days=SIGNAL_WINDOW_DAYS - 1)
    last = [v for d, v in answers if d >= since][:SIGNAL_LAST]
    return sum(v <= LOW_MAX_VALUE for v in last) >= SIGNAL_LOW_COUNT


async def student_view(
    session: AsyncSession, viewer: User, student: User, now: dt.datetime | None = None
) -> StudentWellbeingSelf | StudentWellbeingParent:
    """Учень — себе (картинки), батьки — тижневе зведення словами (перегляд у журнал)."""
    tz = await school_tz(session, student.school_id)
    today = (now or _now()).astimezone(tz).date()
    answers = await _answers(
        session, student.id, today - dt.timedelta(days=max(HISTORY_DAYS, SIGNAL_WINDOW_DAYS) - 1)
    )
    signal = _gentle_signal(answers, today)
    if viewer.role == "student":
        history_since = today - dt.timedelta(days=HISTORY_DAYS - 1)
        return StudentWellbeingSelf(
            student_id=student.id,
            days=[
                WellbeingDay(date=d, picture=PICTURES[v][0])  # type: ignore[arg-type]
                for d, v in answers
                if history_since <= d <= today
            ],
            show_support=signal,
        )

    week_from = today - dt.timedelta(days=WEEK_DAYS - 1)
    week = [v for d, v in answers if week_from <= d <= today]
    mood = None
    if len(week) >= PARENT_MIN_ANSWERS:
        counts = Counter(mood_of(v) for v in week)
        top = max(counts.values())
        mood = next(m for m in _TIE_ORDER if counts[m] == top)
    texts = TEXTS["parent"]
    await _log_view(session, viewer, student.id)
    return StudentWellbeingParent(
        student_id=student.id,
        week_from=week_from,
        week_to=today,
        mood=mood,  # type: ignore[arg-type]
        summary=texts["summary"].format(word=MOOD_WORDS[mood]) if mood else texts["not_enough"],
        gentle_note=texts["gentle_note"] if signal else None,
        tips=list(texts["tips"]) if signal else [],
    )


# ---------- зберігання ----------


async def purge_old(session: AsyncSession, now: dt.datetime | None = None) -> int:
    """Видаляє відповіді, старші за 30 днів (за датою відповіді). Ідемпотентно."""
    cutoff = (now or _now()).astimezone(ZoneInfo(DEFAULT_TZ)).date() - dt.timedelta(
        days=RETENTION_DAYS
    )
    result = await session.execute(
        delete(WellbeingAnswer).where(WellbeingAnswer.answered_on < cutoff)
    )
    await session.commit()
    return result.rowcount or 0
