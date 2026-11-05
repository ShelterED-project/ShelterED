import datetime as dt
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ClassName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=50, pattern=r"^[^\x00-\x1f]+$"
    ),
]
AcademicYear = Annotated[str, StringConstraints(pattern=r"^\d{4}/\d{4}$")]

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"
SLOT_ID = "0192f0a0-0000-7000-8000-000000000101"
SUBJECT_ID = "0192f0a0-0000-7000-8000-000000000201"
LESSON_ID = "0192f0a0-0000-7000-8000-000000000301"


# ---------- класи ----------


class ClassCreate(BaseModel):
    """Створення класу. `id` генерує клієнт; повтор із тими самими даними ідемпотентний."""

    id: uuid.UUID
    name: ClassName
    grade: int = Field(ge=1, le=11)
    academic_year: AcademicYear

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": CLASS_ID, "name": "7-А", "grade": 7, "academic_year": "2026/2027"}]
        }
    )


class ClassUpdate(BaseModel):
    name: ClassName | None = None
    grade: int | None = Field(default=None, ge=1, le=11)
    academic_year: AcademicYear | None = None

    model_config = ConfigDict(json_schema_extra={"examples": [{"name": "7-Б"}]})


class ClassOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID
    name: str
    grade: int
    academic_year: str
    join_code: str = Field(description="Код класу для входу учнів (лише A-Z0-9)")
    join_code_expires_at: dt.datetime | None
    teacher_ids: list[uuid.UUID] = []

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": CLASS_ID,
                    "school_id": "0192f0a0-0000-7000-8000-0000000000aa",
                    "name": "7-А",
                    "grade": 7,
                    "academic_year": "2026/2027",
                    "join_code": "K7M2XQ9P",
                    "join_code_expires_at": None,
                    "teacher_ids": ["0192f0a0-0000-7000-8000-0000000000bb"],
                }
            ]
        },
    )


class JoinCodeRequest(BaseModel):
    """Новий код класу; старий одразу перестає діяти. Без терміну — безстроковий."""

    expires_in_days: int | None = Field(default=None, ge=1, le=365)

    model_config = ConfigDict(json_schema_extra={"examples": [{"expires_in_days": 14}]})


# ---------- розклад ----------


class SlotCreate(BaseModel):
    """Тижневий слот. Час — місцевий час школи (Europe/Kyiv), weekday ISO: 1 = понеділок."""

    id: uuid.UUID
    subject_id: uuid.UUID
    weekday: int = Field(ge=1, le=7)
    starts_at: dt.time
    ends_at: dt.time
    valid_from: dt.date
    valid_to: dt.date | None = None

    @model_validator(mode="after")
    def _check(self) -> "SlotCreate":
        _check_times(self.starts_at, self.ends_at)
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must not be before valid_from")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": SLOT_ID,
                    "subject_id": SUBJECT_ID,
                    "weekday": 1,
                    "starts_at": "09:00:00",
                    "ends_at": "09:45:00",
                    "valid_from": "2026-09-01",
                    "valid_to": "2026-12-26",
                }
            ]
        }
    )


class SlotUpdate(BaseModel):
    subject_id: uuid.UUID | None = None
    weekday: int | None = Field(default=None, ge=1, le=7)
    starts_at: dt.time | None = None
    ends_at: dt.time | None = None
    valid_from: dt.date | None = None
    valid_to: dt.date | None = None

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"starts_at": "10:00:00", "ends_at": "10:45:00"}]}
    )


class SlotOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    subject_id: uuid.UUID
    weekday: int
    starts_at: dt.time
    ends_at: dt.time
    valid_from: dt.date
    valid_to: dt.date | None

    model_config = ConfigDict(from_attributes=True)


class OverrideCreate(BaseModel):
    """Перевизначення на дату.

    - `cancel`: слот скасовано (`slot_id` обов'язковий, решта порожня);
    - `replace`: інший предмет і/або час для слота (`slot_id` обов'язковий);
    - `extra`: додатковий урок без слота (`subject_id`, `starts_at`, `ends_at` обов'язкові).
    """

    id: uuid.UUID
    date: dt.date
    kind: Literal["cancel", "replace", "extra"]
    slot_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    starts_at: dt.time | None = None
    ends_at: dt.time | None = None

    @model_validator(mode="after")
    def _check(self) -> "OverrideCreate":
        if self.kind in ("cancel", "replace") and self.slot_id is None:
            raise ValueError(f"slot_id is required for {self.kind}")
        if self.kind == "cancel" and (self.subject_id or self.starts_at or self.ends_at):
            raise ValueError("cancel takes no subject or time")
        if self.kind == "extra":
            if self.slot_id is not None:
                raise ValueError("extra has no slot_id")
            if not (self.subject_id and self.starts_at and self.ends_at):
                raise ValueError("extra requires subject_id, starts_at and ends_at")
        if self.kind == "replace" and not (self.subject_id or self.starts_at or self.ends_at):
            raise ValueError("replace must change subject or time")
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("starts_at and ends_at go together")
        if self.starts_at and self.ends_at:
            _check_times(self.starts_at, self.ends_at)
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": "0192f0a0-0000-7000-8000-000000000401",
                    "date": "2026-11-09",
                    "kind": "cancel",
                    "slot_id": SLOT_ID,
                }
            ]
        }
    )


class OverrideOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    date: dt.date
    kind: str
    slot_id: uuid.UUID | None
    subject_id: uuid.UUID | None
    starts_at: dt.time | None
    ends_at: dt.time | None

    model_config = ConfigDict(from_attributes=True)


class AssignmentRequest(BaseModel):
    lesson_id: uuid.UUID

    model_config = ConfigDict(json_schema_extra={"examples": [{"lesson_id": LESSON_ID}]})


class AssignmentOut(BaseModel):
    slot_id: uuid.UUID
    date: dt.date
    lesson_id: uuid.UUID
    pack_day_bytes: int = Field(description="Розмір пакета класу на цю дату після прив'язки")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "slot_id": SLOT_ID,
                    "date": "2026-11-09",
                    "lesson_id": LESSON_ID,
                    "pack_day_bytes": 12582912,
                }
            ]
        }
    )


class ScheduleItem(BaseModel):
    """Один урок у розкладі конкретного дня (з урахуванням перевизначень)."""

    kind: Literal["regular", "replaced", "extra"]
    slot_id: uuid.UUID | None
    override_id: uuid.UUID | None
    subject_id: uuid.UUID
    starts_at: dt.time = Field(description="Місцевий час школи")
    ends_at: dt.time
    starts_at_utc: dt.datetime
    ends_at_utc: dt.datetime
    lesson_id: uuid.UUID | None = Field(description="Призначений на цю дату урок, якщо є")


class ScheduleDay(BaseModel):
    date: dt.date
    items: list[ScheduleItem]


class ScheduleOut(BaseModel):
    class_id: uuid.UUID
    timezone: str
    days: list[ScheduleDay]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "class_id": CLASS_ID,
                    "timezone": "Europe/Kyiv",
                    "days": [
                        {
                            "date": "2026-11-09",
                            "items": [
                                {
                                    "kind": "regular",
                                    "slot_id": SLOT_ID,
                                    "override_id": None,
                                    "subject_id": SUBJECT_ID,
                                    "starts_at": "09:00:00",
                                    "ends_at": "09:45:00",
                                    "starts_at_utc": "2026-11-09T07:00:00Z",
                                    "ends_at_utc": "2026-11-09T07:45:00Z",
                                    "lesson_id": LESSON_ID,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )


class CurrentLessonOut(BaseModel):
    """Урок, що йде в момент `at`; `item` = null, якщо зараз уроку немає."""

    class_id: uuid.UUID
    at: dt.datetime
    date: dt.date = Field(description="Місцева дата школи в момент at")
    item: ScheduleItem | None


def _check_times(starts_at: dt.time, ends_at: dt.time) -> None:
    # Час розкладу — місцевий час школи, без поясу.
    if starts_at.tzinfo is not None or ends_at.tzinfo is not None:
        raise ValueError("schedule times are local school time without timezone")
    if ends_at <= starts_at:
        raise ValueError("ends_at must be after starts_at")
