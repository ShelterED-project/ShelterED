"""Розклад класу на дату й «який урок зараз».

Чисті функції без БД: їх викликає і API (B5), і реакція на тривогу (B7).
Час розкладу — місцевий час школи (`school.timezone`, Europe/Kyiv); у БД і на виході — UTC.
"""

import datetime as dt
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Europe/Kyiv"
_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.UTC)


@dataclass(frozen=True)
class SlotData:
    id: uuid.UUID
    subject_id: uuid.UUID
    weekday: int  # ISO: 1 = понеділок
    starts_at: dt.time
    ends_at: dt.time
    valid_from: dt.date
    valid_to: dt.date | None


@dataclass(frozen=True)
class OverrideData:
    id: uuid.UUID
    date: dt.date
    kind: Literal["cancel", "replace", "extra"]
    slot_id: uuid.UUID | None
    subject_id: uuid.UUID | None
    starts_at: dt.time | None
    ends_at: dt.time | None
    # Урок додаткового уроку вчителя (extra без слота); час тоді може бути порожнім.
    lesson_id: uuid.UUID | None = None


@dataclass(frozen=True)
class ResolvedItem:
    kind: Literal["regular", "replaced", "extra"]
    slot_id: uuid.UUID | None
    override_id: uuid.UUID | None
    subject_id: uuid.UUID
    # Порожні лише в додаткового уроку без часу: він є в розкладі й пакеті, але не «зараз».
    starts_at: dt.time | None
    ends_at: dt.time | None
    starts_at_utc: dt.datetime | None
    ends_at_utc: dt.datetime | None
    lesson_id: uuid.UUID | None


def slot_active_on(slot: SlotData, day: dt.date) -> bool:
    return (
        slot.weekday == day.isoweekday()
        and slot.valid_from <= day
        and (slot.valid_to is None or day <= slot.valid_to)
    )


def to_utc(day: dt.date, local: dt.time, tz: ZoneInfo) -> dt.datetime:
    """Місцевий час школи на дату → UTC. Неоднозначна година при переході на зимовий час
    береться в першому значенні (fold=0), неіснуюча при переході на літній — зсувається."""
    return dt.datetime.combine(day, local, tzinfo=tz).astimezone(dt.UTC)


def resolve_day(
    day: dt.date,
    slots: Iterable[SlotData],
    overrides: Iterable[OverrideData],
    assignments: Mapping[tuple[uuid.UUID, dt.date], uuid.UUID],
    tz: ZoneInfo,
) -> list[ResolvedItem]:
    """Уроки класу на дату: тижневі слоти + перевизначення + призначені уроки, за часом."""
    by_slot: dict[uuid.UUID, OverrideData] = {}
    extras: list[OverrideData] = []
    for o in overrides:
        if o.date != day:
            continue
        if o.kind == "extra":
            extras.append(o)
        elif o.slot_id is not None:
            by_slot[o.slot_id] = o

    items: list[ResolvedItem] = []
    for slot in slots:
        if not slot_active_on(slot, day):
            continue
        o = by_slot.get(slot.id)
        if o is not None and o.kind == "cancel":
            continue
        subject_id, starts_at, ends_at = slot.subject_id, slot.starts_at, slot.ends_at
        if o is not None:  # replace
            subject_id = o.subject_id or subject_id
            starts_at = o.starts_at or starts_at
            ends_at = o.ends_at or ends_at
        items.append(
            ResolvedItem(
                kind="replaced" if o is not None else "regular",
                slot_id=slot.id,
                override_id=o.id if o is not None else None,
                subject_id=subject_id,
                starts_at=starts_at,
                ends_at=ends_at,
                starts_at_utc=to_utc(day, starts_at, tz),
                ends_at_utc=to_utc(day, ends_at, tz),
                lesson_id=assignments.get((slot.id, day)),
            )
        )
    for o in extras:
        # Гарантує валідація API: предмет є завжди, час — обидві межі або жодної.
        assert o.subject_id and (o.starts_at is None) == (o.ends_at is None)
        items.append(
            ResolvedItem(
                kind="extra",
                slot_id=None,
                override_id=o.id,
                subject_id=o.subject_id,
                starts_at=o.starts_at,
                ends_at=o.ends_at,
                starts_at_utc=None if o.starts_at is None else to_utc(day, o.starts_at, tz),
                ends_at_utc=None if o.ends_at is None else to_utc(day, o.ends_at, tz),
                lesson_id=o.lesson_id,
            )
        )
    # Уроки без часу — наприкінці дня; стабільне сортування зберігає порядок із БД (за id),
    # тож вміст пакета детермінований.
    items.sort(
        key=lambda i: (
            i.starts_at_utc is None,
            i.starts_at_utc or _EPOCH,
            i.ends_at_utc or _EPOCH,
        )
    )
    return items


def local_date(at: dt.datetime, tz: ZoneInfo) -> dt.date:
    if at.tzinfo is None:
        raise ValueError("at must be timezone-aware")
    return at.astimezone(tz).date()


def current_item(
    at: dt.datetime,
    slots: Iterable[SlotData],
    overrides: Iterable[OverrideData],
    assignments: Mapping[tuple[uuid.UUID, dt.date], uuid.UUID],
    tz: ZoneInfo,
) -> ResolvedItem | None:
    """Який урок іде в момент `at` (aware datetime). Межі: [початок, кінець).

    Якщо уроки перекриваються, повертається той, що почався пізніше.
    """
    day = local_date(at, tz)
    at_utc = at.astimezone(dt.UTC)
    running = [
        i
        for i in resolve_day(day, slots, overrides, assignments, tz)
        if i.starts_at_utc is not None
        and i.ends_at_utc is not None
        and i.starts_at_utc <= at_utc < i.ends_at_utc
    ]
    return running[-1] if running else None
