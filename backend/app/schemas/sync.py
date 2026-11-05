"""Події синхронізації (docs/sync-protocol.md): пакет подій, payload по типах, зміни для пристрою.

Конверт події перевіряється для всього пакета (422), а `type` і `payload` — по кожній події
окремо: невідомий тип чи невалідний payload дають `rejected` лише цій події, а не всьому пакету
(інакше одна погана подія назавжди заблокувала б outbox).
"""

import uuid
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, WithJsonSchema

DEVICE_ID = "0193a000-0000-7000-8000-000000000001"
EVENT_ID = "0193a1b2-0000-7000-8000-000000000001"
SESSION_ID = "0192f0a0-0000-7000-8000-000000000801"
MODULE_ID = "0192f0a0-0000-7000-8000-000000000311"
TEST_ID = "0192f0a0-0000-7000-8000-000000000331"
QUESTION_ID = "0192f0a0-0000-7000-8000-000000000341"

SyncEventType = Literal["module_progress", "test_attempt", "rollcall_status", "survey_answer"]
RejectReason = Literal[
    "invalid_payload", "unknown_type", "unknown_entity", "forbidden", "session_closed"
]
RollCallStatusValue = Literal["safe", "in_shelter"]
CreditStatus = Literal["credited", "not_credited_late", "not_credited_repeat"]

# Id варіанта відповіді, як Option.id у тестах.
OptionId = Annotated[
    str, StringConstraints(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")
]


# ---------- payload по типах ----------


class ModuleProgressPayload(BaseModel):
    """`module_progress`: прогрес модуля; на сервері береться максимум."""

    module_id: uuid.UUID
    progress_pct: int = Field(ge=0, le=100)
    completed_at: AwareDatetime | None = Field(
        default=None, description="-> module_progress.completed_at_client"
    )

    model_config = ConfigDict(extra="forbid")


class TestAttemptPayload(BaseModel):
    """`test_attempt`: завершена спроба тесту. Оцінює сервер, `score` клієнт не надсилає."""

    __test__ = False

    test_id: uuid.UUID
    answers: dict[uuid.UUID, list[OptionId]] = Field(
        description="question_id -> id обраних варіантів", max_length=200
    )
    completed_at: AwareDatetime = Field(
        description="-> attempt.completed_at_client; від нього рахується вікно тесту"
    )

    model_config = ConfigDict(extra="forbid")


class RollCallStatusPayload(BaseModel):
    """`rollcall_status`: «я в безпеці» / «я в укритті». Час статусу — `occurred_at` події."""

    session_id: uuid.UUID
    status: RollCallStatusValue

    model_config = ConfigDict(extra="forbid")


class SurveyAnswerPayload(BaseModel):
    """`survey_answer`: відповідь на опитування «як ти зараз?» (ЧЕРНЕТКА, B13.4).

    Мінімум даних: лише вибір зі шкали, без вільного тексту. Перелік питань і шкала
    погоджуються з психологом; окремого сховища поки немає (подія лежить у `sync_event`).
    """

    survey_id: uuid.UUID
    question_id: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    value: int = Field(ge=0, le=10)

    model_config = ConfigDict(extra="forbid")


PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    "module_progress": ModuleProgressPayload,
    "test_attempt": TestAttemptPayload,
    "rollcall_status": RollCallStatusPayload,
    "survey_answer": SurveyAnswerPayload,
}

# У специфікації payload описаний як oneOf схем вище; під час виконання це довільний об'єкт,
# який сервер перевіряє за `type` для кожної події окремо.
_PAYLOAD_SCHEMA = {
    "oneOf": [m.model_json_schema() for m in PAYLOAD_MODELS.values()],
    "description": "Схема залежить від `type` (див. docs/sync-protocol.md, розділ 3)",
}


# ---------- POST /sync/events ----------


class SyncEventIn(BaseModel):
    client_event_id: uuid.UUID = Field(description="Створює клієнт (бажано UUID v7)")
    type: Annotated[
        str,
        StringConstraints(max_length=64),
        WithJsonSchema(
            {
                "type": "string",
                "enum": list(PAYLOAD_MODELS),
                "description": "Інший рядок не ламає пакет: подія отримує rejected/unknown_type",
            }
        ),
    ]
    device_id: uuid.UUID = Field(description="Id пристрою, створюється клієнтом один раз")
    occurred_at: AwareDatetime = Field(description="Час події за годинником пристрою")
    payload: Annotated[dict[str, Any], WithJsonSchema(_PAYLOAD_SCHEMA)]


class SyncEventsRequest(BaseModel):
    """Пакет від 1 до 100 подій. Користувач — з JWT; учень надсилає лише свої події."""

    sent_at: AwareDatetime = Field(
        description="Час пристрою в момент відправки; сервер рахує зсув годинника"
    )
    events: list[SyncEventIn] = Field(min_length=1, max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "sent_at": "2026-11-05T09:55:00Z",
                    "events": [
                        {
                            "client_event_id": EVENT_ID,
                            "type": "rollcall_status",
                            "device_id": DEVICE_ID,
                            "occurred_at": "2026-11-05T09:54:10Z",
                            "payload": {"session_id": SESSION_ID, "status": "in_shelter"},
                        },
                        {
                            "client_event_id": "0193a1b2-0000-7000-8000-000000000002",
                            "type": "module_progress",
                            "device_id": DEVICE_ID,
                            "occurred_at": "2026-11-05T09:41:00Z",
                            "payload": {
                                "module_id": MODULE_ID,
                                "progress_pct": 100,
                                "completed_at": "2026-11-05T09:41:00Z",
                            },
                        },
                        {
                            "client_event_id": "0193a1b2-0000-7000-8000-000000000003",
                            "type": "test_attempt",
                            "device_id": DEVICE_ID,
                            "occurred_at": "2026-11-05T09:50:12Z",
                            "payload": {
                                "test_id": TEST_ID,
                                "answers": {QUESTION_ID: ["a"]},
                                "completed_at": "2026-11-05T09:50:12Z",
                            },
                        },
                    ],
                }
            ]
        }
    )


class SyncEventResult(BaseModel):
    """Результат по події. Клієнт видаляє подію з outbox після будь-якого з трьох статусів;
    при мережевій помилці лишає й повторює (повтор дає той самий результат)."""

    client_event_id: uuid.UUID
    status: Literal["accepted", "duplicate", "rejected"]
    reason: RejectReason | None = Field(default=None, description="Лише для `rejected`")


class SyncEventsResponse(BaseModel):
    results: list[SyncEventResult]
    server_time: AwareDatetime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "results": [
                        {"client_event_id": EVENT_ID, "status": "accepted", "reason": None},
                        {
                            "client_event_id": "0193a1b2-0000-7000-8000-000000000002",
                            "status": "duplicate",
                            "reason": None,
                        },
                        {
                            "client_event_id": "0193a1b2-0000-7000-8000-000000000003",
                            "status": "rejected",
                            "reason": "unknown_entity",
                        },
                    ],
                    "server_time": "2026-11-05T09:55:01Z",
                }
            ]
        }
    )


# ---------- GET /sync/changes ----------


class AttemptResultChange(BaseModel):
    """Результат спроби тесту після оцінювання на сервері."""

    kind: Literal["attempt_result"]
    client_event_id: uuid.UUID
    test_id: uuid.UUID
    credit_status: CreditStatus
    score: float | None
    is_suspicious: bool


class ModuleProgressChange(BaseModel):
    """Підсумковий прогрес модуля (максимум з усіх пристроїв)."""

    kind: Literal["module_progress"]
    module_id: uuid.UUID
    progress_pct: int
    completed_at: AwareDatetime | None


class RollCallStatusChange(BaseModel):
    """Актуальний статус учня в перекличці (перемагає найпізніший `occurred_at`)."""

    kind: Literal["rollcall_status"]
    session_id: uuid.UUID
    status: RollCallStatusValue
    occurred_at: AwareDatetime


SyncChange = Annotated[
    AttemptResultChange | ModuleProgressChange | RollCallStatusChange,
    Field(discriminator="kind"),
]


class SyncChangesOut(BaseModel):
    """Зміни для поточного користувача після `cursor`. Курсор непрозорий і монотонний."""

    changes: list[SyncChange]
    next_cursor: str = Field(description="Передати в наступний запит як `cursor`")
    has_more: bool

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "changes": [
                        {
                            "kind": "attempt_result",
                            "client_event_id": "0193a1b2-0000-7000-8000-000000000003",
                            "test_id": TEST_ID,
                            "credit_status": "credited",
                            "score": 85.0,
                            "is_suspicious": False,
                        },
                        {
                            "kind": "module_progress",
                            "module_id": MODULE_ID,
                            "progress_pct": 100,
                            "completed_at": "2026-11-05T09:41:00Z",
                        },
                        {
                            "kind": "rollcall_status",
                            "session_id": SESSION_ID,
                            "status": "safe",
                            "occurred_at": "2026-11-05T10:20:00Z",
                        },
                    ],
                    "next_cursor": "771.1042",
                    "has_more": False,
                }
            ]
        }
    )
