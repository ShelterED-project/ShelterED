"""Видалення даних учня на запит батьків або школи (B15.5)."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

REQUEST_ID = "0192f0a0-0000-7000-8000-000000000d01"
STUDENT_ID = "0192f0a0-0000-7000-8000-000000000101"

DeletionReason = Literal["left_school", "consent_withdrawn", "duplicate_account", "other"]
DeletionStatus = Literal["pending", "confirmed", "rejected"]


class DeletionRequestCreate(BaseModel):
    id: uuid.UUID = Field(description="Id запиту, створює клієнт (повтор — той самий запит)")
    reason: DeletionReason | None = Field(
        default=None, description="Причина з переліку; вільного тексту немає (мінімум даних)"
    )

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": REQUEST_ID, "reason": "left_school"}]}
    )


class DeletionRequestOut(BaseModel):
    id: uuid.UUID
    student_id: uuid.UUID | None = Field(description="NULL після видалення даних учня")
    student_name: str | None = Field(description="Ім'я та прізвище, доки учень існує")
    status: DeletionStatus
    reason: DeletionReason | None
    requested_by_role: Literal["parent", "admin"]
    created_at: dt.datetime
    decided_at: dt.datetime | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": REQUEST_ID,
                    "student_id": STUDENT_ID,
                    "student_name": "Іван Петренко",
                    "status": "pending",
                    "reason": "left_school",
                    "requested_by_role": "parent",
                    "created_at": "2026-11-06T09:00:00Z",
                    "decided_at": None,
                }
            ]
        }
    )
