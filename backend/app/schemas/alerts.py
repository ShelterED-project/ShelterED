"""Тривоги (контракт B4, логіка — B7). Тривоги з API бекенд отримує сам (B7), без AI-сервісу."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"
SCHOOL_ID = "0192f0a0-0000-7000-8000-0000000000aa"
ALERT_ID = "0192f0a0-0000-7000-8000-000000000901"


class ManualAlertCreate(BaseModel):
    """Ручна кнопка «Тривога» вчителя для свого класу. `id` генерує клієнт; повтор ідемпотентний."""

    id: uuid.UUID
    class_id: uuid.UUID
    is_drill: bool = Field(default=False, description="Тренувальна тривога")

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": ALERT_ID, "class_id": CLASS_ID, "is_drill": True}]}
    )


class AlertOut(BaseModel):
    id: uuid.UUID
    region_code: str
    school_id: uuid.UUID | None
    class_id: uuid.UUID | None = Field(description="Лише для ручної тривоги класу")
    source: Literal["api", "manual"]
    is_drill: bool
    started_at: dt.datetime
    ended_at: dt.datetime | None = Field(description="Відбій; null — тривога триває")
    # Чому спрацювала тривога з API: тривога провайдера, з якої почалась тривога школи
    # (найраніша з тих, що її стосуються). Ручна тривога й старі записи — null.
    location_type: str | None = Field(
        default=None, description="oblast / raion / hromada / city (лише source = api)"
    )
    location_uid: str | None = Field(default=None, description="uid локації alerts.in.ua")
    location_title: str | None = Field(default=None, description="Назва локації від провайдера")
    alert_type: str | None = Field(
        default=None,
        description="air_raid, artillery_shelling, urban_fights, chemical, nuclear (лише api)",
    )

    model_config = ConfigDict(from_attributes=True)


_ALERT_EXAMPLE = {
    "id": ALERT_ID,
    "region_code": "14",
    "school_id": SCHOOL_ID,
    "class_id": None,
    "source": "api",
    "is_drill": False,
    "started_at": "2026-11-05T09:30:00Z",
    "ended_at": None,
    "location_type": "raion",
    "location_uid": "56",
    "location_title": "Бориспільський район",
    "alert_type": "air_raid",
}
_MANUAL_EXAMPLE = {
    **_ALERT_EXAMPLE,
    "id": "0192f0a0-0000-7000-8000-000000000902",
    "class_id": CLASS_ID,
    "source": "manual",
    "is_drill": True,
    "location_type": None,
    "location_uid": None,
    "location_title": None,
    "alert_type": None,
}


class ActiveAlertsOut(BaseModel):
    """Запасний шлях для клієнта, який не отримав пуш (B7.5)."""

    alerts: list[AlertOut] = Field(description="Тривоги шкіл і класів користувача без відбою")
    source_available: bool = Field(
        description="false — API тривог довго мовчить; лишається ручна кнопка (B7.6)"
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"alerts": [_ALERT_EXAMPLE], "source_available": True}]}
    )


ALERT_EXAMPLES = {"api": _ALERT_EXAMPLE, "manual": _MANUAL_EXAMPLE}
