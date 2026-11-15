"""ШІ-репетитор (контракт B4, логіка — B13). Бекенд проксує запит до AI-сервісу.

Вільного тексту від дитини немає: лише режим і посилання на матеріал чи спробу тесту,
тож у AI не потрапляють персональні дані (див. docs/ai-contract.md).
"""

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

REQUEST_ID = "0193a1b2-0000-7000-8000-0000000000f1"


class TutorAskRequest(BaseModel):
    """- `explain_again`: пояснити матеріал іншими словами (`lesson_id`, бажано `module_id`);
    - `test_review`: розбір помилок у спробі тесту (`attempt_event_id` — `client_event_id`
      події `test_attempt`)."""

    request_id: uuid.UUID = Field(description="Створює клієнт; повтор повертає ту саму відповідь")
    mode: Literal["explain_again", "test_review"]
    lesson_id: uuid.UUID | None = None
    module_id: uuid.UUID | None = None
    card_id: uuid.UUID | None = None
    attempt_event_id: uuid.UUID | None = None
    previous_explanation_id: uuid.UUID | None = Field(
        default=None, description="Попереднє пояснення, яке не допомогло"
    )

    @model_validator(mode="after")
    def _check(self) -> "TutorAskRequest":
        if self.mode == "explain_again" and self.lesson_id is None:
            raise ValueError("explain_again requires lesson_id")
        if self.mode == "test_review" and self.attempt_event_id is None:
            raise ValueError("test_review requires attempt_event_id")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": REQUEST_ID,
                    "mode": "explain_again",
                    "lesson_id": "0192f0a0-0000-7000-8000-000000000301",
                    "module_id": "0192f0a0-0000-7000-8000-000000000311",
                    "card_id": "0192f0a0-0000-7000-8000-000000000321",
                }
            ]
        }
    )


class TutorAnswerOut(BaseModel):
    request_id: uuid.UUID
    explanation: str
    explanation_id: uuid.UUID
    cached: bool = Field(description="true — готове пояснення з кешу, без виклику LLM")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": REQUEST_ID,
                    "explanation": "Уяви піцу з 4 шматків: 1/2 — це 2 шматки, 1/4 — ще один.",
                    "explanation_id": "0192f0a0-0000-7000-8000-000000000701",
                    "cached": False,
                }
            ]
        }
    )
