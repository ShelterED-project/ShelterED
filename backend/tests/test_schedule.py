"""Чисті функції розкладу: дата, перевизначення, «який урок зараз», перехід на зимовий час."""

import datetime as dt
import uuid
from zoneinfo import ZoneInfo

from app.services.schedule import OverrideData, SlotData, current_item, resolve_day

KYIV = ZoneInfo("Europe/Kyiv")
SUBJECT = uuid.uuid4()
OTHER_SUBJECT = uuid.uuid4()


def slot(weekday: int = 1, start=(9, 0), end=(9, 45), **kw) -> SlotData:
    return SlotData(
        id=kw.get("id", uuid.uuid4()),
        subject_id=SUBJECT,
        weekday=weekday,
        starts_at=dt.time(*start),
        ends_at=dt.time(*end),
        valid_from=kw.get("valid_from", dt.date(2026, 9, 1)),
        valid_to=kw.get("valid_to"),
    )


def override(day: dt.date, kind: str, slot_id=None, **kw) -> OverrideData:
    return OverrideData(
        id=uuid.uuid4(),
        date=day,
        kind=kind,  # type: ignore[arg-type]
        slot_id=slot_id,
        subject_id=kw.get("subject_id"),
        starts_at=kw.get("starts_at"),
        ends_at=kw.get("ends_at"),
    )


MONDAY = dt.date(2026, 11, 9)


def test_regular_day_in_kyiv_converted_to_utc() -> None:
    s = slot()
    lesson_id = uuid.uuid4()
    items = resolve_day(MONDAY, [s], [], {(s.id, MONDAY): lesson_id}, KYIV)
    assert len(items) == 1
    # Листопад: EET (UTC+2).
    assert items[0].starts_at_utc == dt.datetime(2026, 11, 9, 7, 0, tzinfo=dt.UTC)
    assert items[0].lesson_id == lesson_id
    assert items[0].kind == "regular"
    # Вівторок — слота немає.
    assert resolve_day(MONDAY + dt.timedelta(days=1), [s], [], {}, KYIV) == []


def test_validity_window() -> None:
    s = slot(valid_from=dt.date(2026, 11, 10), valid_to=dt.date(2026, 11, 20))
    assert resolve_day(MONDAY, [s], [], {}, KYIV) == []
    assert len(resolve_day(MONDAY + dt.timedelta(days=7), [s], [], {}, KYIV)) == 1
    assert resolve_day(MONDAY + dt.timedelta(days=14), [s], [], {}, KYIV) == []


def test_overrides_cancel_replace_extra() -> None:
    a, b = slot(), slot(start=(10, 0), end=(10, 45))
    overrides = [
        override(MONDAY, "cancel", a.id),
        override(MONDAY, "replace", b.id, subject_id=OTHER_SUBJECT),
        override(MONDAY, "extra", subject_id=SUBJECT, starts_at=dt.time(8), ends_at=dt.time(8, 30)),
        # Перевизначення іншої дати не впливає.
        override(MONDAY + dt.timedelta(days=7), "cancel", b.id),
    ]
    items = resolve_day(MONDAY, [a, b], overrides, {}, KYIV)
    assert [i.kind for i in items] == ["extra", "replaced"]
    assert items[1].subject_id == OTHER_SUBJECT
    assert items[1].starts_at == dt.time(10, 0)  # час слота лишився


def test_current_lesson_boundaries() -> None:
    s = slot()
    at = dt.datetime(2026, 11, 9, 7, 0, tzinfo=dt.UTC)  # 09:00 Київ
    assert current_item(at, [s], [], {}, KYIV).slot_id == s.id
    assert current_item(at - dt.timedelta(seconds=1), [s], [], {}, KYIV) is None
    assert current_item(at + dt.timedelta(minutes=45), [s], [], {}, KYIV) is None


def test_current_lesson_across_dst_change() -> None:
    """25.10.2026 Київ переходить з EEST (UTC+3) на EET (UTC+2): той самий UTC-момент
    потрапляє в урок 09:00 лише після переходу."""
    s = slot()  # понеділок 09:00–09:45
    at_utc = dt.time(6, 30)
    before = dt.datetime.combine(dt.date(2026, 10, 19), at_utc, tzinfo=dt.UTC)  # 09:30 EEST
    after = dt.datetime.combine(dt.date(2026, 10, 26), at_utc, tzinfo=dt.UTC)  # 08:30 EET
    assert current_item(before, [s], [], {}, KYIV) is not None
    assert current_item(after, [s], [], {}, KYIV) is None
    assert current_item(after + dt.timedelta(hours=1), [s], [], {}, KYIV) is not None
    items = resolve_day(dt.date(2026, 10, 19), [s], [], {}, KYIV)
    assert items[0].starts_at_utc.hour == 6
    items = resolve_day(dt.date(2026, 10, 26), [s], [], {}, KYIV)
    assert items[0].starts_at_utc.hour == 7


def test_local_date_differs_from_utc_date() -> None:
    """23:30 UTC неділі — це вже понеділок у Києві."""
    s = slot(start=(0, 0), end=(2, 0))
    at = dt.datetime(2026, 11, 8, 23, 30, tzinfo=dt.UTC)
    assert current_item(at, [s], [], {}, KYIV) is not None
