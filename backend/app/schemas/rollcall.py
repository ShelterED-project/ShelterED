"""Перекличка (контракт B4, логіка — B12). Статуси надходять подіями `rollcall_status` (B9)."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"
SESSION_ID = "0192f0a0-0000-7000-8000-000000000801"
ALERT_ID = "0192f0a0-0000-7000-8000-000000000901"
STUDENT_ID = "0192f0a0-0000-7000-8000-0000000000cc"

# «Немає відповіді» в БД = рядка немає; у відповідях API — окреме значення.
RollCallStatusView = Literal["safe", "in_shelter", "no_response"]


class RollCallStart(BaseModel):
    """Ручний старт переклички вчителем. `id` генерує клієнт; повтор ідемпотентний."""

    id: uuid.UUID
    is_drill: bool = Field(default=False, description="Тренувальна перекличка")

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": SESSION_ID, "is_drill": False}]}
    )


class RollCallStudentStatus(BaseModel):
    student_id: uuid.UUID
    display_name: str
    last_name: str | None
    status: RollCallStatusView
    occurred_at: dt.datetime | None = Field(description="Час статусу за годинником пристрою")
    received_at: dt.datetime | None = Field(
        description="Коли сервер отримав статус: видно, що він міг застаріти"
    )


class RollCallSummary(BaseModel):
    safe: int
    in_shelter: int
    no_response: int


_SESSION_EXAMPLE = {
    "id": SESSION_ID,
    "class_id": CLASS_ID,
    "alert_event_id": ALERT_ID,
    "is_drill": False,
    "opened_at": "2026-11-05T09:30:05Z",
    "closed_at": None,
    "summary": {"safe": 1, "in_shelter": 1, "no_response": 1},
    "students": [
        {
            "student_id": STUDENT_ID,
            "display_name": "Іван",
            "last_name": "Петренко",
            "status": "in_shelter",
            "occurred_at": "2026-11-05T09:31:40Z",
            "received_at": "2026-11-05T09:31:42Z",
        },
        {
            "student_id": "0192f0a0-0000-7000-8000-0000000000cd",
            "display_name": "Марко",
            "last_name": "Коваль",
            "status": "safe",
            "occurred_at": "2026-11-05T09:33:00Z",
            "received_at": "2026-11-05T11:02:10Z",
        },
        {
            "student_id": "0192f0a0-0000-7000-8000-0000000000ce",
            "display_name": "Оксана",
            "last_name": "Бойко",
            "status": "no_response",
            "occurred_at": None,
            "received_at": None,
        },
    ],
}


class RollCallSessionOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    alert_event_id: uuid.UUID | None = Field(description="null — відкрита вчителем вручну")
    is_drill: bool
    opened_at: dt.datetime
    closed_at: dt.datetime | None
    summary: RollCallSummary
    students: list[RollCallStudentStatus] = Field(
        description="Вчитель і адмін бачать увесь клас, учень — лише себе"
    )

    model_config = ConfigDict(json_schema_extra={"examples": [_SESSION_EXAMPLE]})


class RollCallCurrentOut(BaseModel):
    """Відкрита перекличка класу; `session` = null, якщо зараз переклички немає."""

    class_id: uuid.UUID
    session: RollCallSessionOut | None

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"class_id": CLASS_ID, "session": _SESSION_EXAMPLE}]}
    )


class StudentRollCallOut(BaseModel):
    """Статус дитини в поточній перекличці її класу (для батьків)."""

    student_id: uuid.UUID
    session_id: uuid.UUID | None = Field(description="null — переклички зараз немає")
    is_drill: bool | None
    opened_at: dt.datetime | None
    status: RollCallStatusView | None = Field(description="null, якщо переклички немає")
    occurred_at: dt.datetime | None
    received_at: dt.datetime | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "student_id": STUDENT_ID,
                    "session_id": SESSION_ID,
                    "is_drill": False,
                    "opened_at": "2026-11-05T09:30:05Z",
                    "status": "in_shelter",
                    "occurred_at": "2026-11-05T09:31:40Z",
                    "received_at": "2026-11-05T09:31:42Z",
                }
            ]
        }
    )
