"""Дрібні помічники: UUID v7 і час."""

import secrets
import time
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")


def uuid7() -> uuid.UUID:
    """UUID версії 7 (RFC 9562): 48 біт мілісекунд Unix + випадкові біти.

    У Python до 3.14 немає uuid.uuid7(), тому генеруємо самі.
    """
    ms = time.time_ns() // 1_000_000
    rand = secrets.randbits(74)
    value = (ms & ((1 << 48) - 1)) << 80  # unix_ts_ms
    value |= 0x7 << 76  # версія 7
    value |= (rand >> 62) << 64  # rand_a, 12 біт
    value |= 0b10 << 62  # варіант RFC
    value |= rand & ((1 << 62) - 1)  # rand_b, 62 біти
    return uuid.UUID(int=value)


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso_utc(dt: datetime) -> str:
    """ISO 8601 з часовим поясом, напр. 2026-11-05T09:31:40.123456Z."""
    if dt.tzinfo is None:
        raise ValueError("naive datetime")
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def to_kyiv(dt: datetime | None, fmt: str = "%H:%M:%S") -> str:
    if dt is None:
        return ""
    return dt.astimezone(KYIV_TZ).strftime(fmt)
