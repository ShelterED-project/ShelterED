"""ШІ-репетитор (B13): `POST /tutor/ask`. Бекенд проксує запит до AI-сервісу
(docs/ai-contract.md) і сам зберігає стан розмови.

Учень надсилає лише своє питання/відповідь і посилання на матеріал; клас, предмет і тему
backend бере з БД. В AI не потрапляють ім'я, email, школа. `task` у відповіді учню — без
правильної відповіді й підказок (`answer`, `hints` тощо лишаються на сервері).
"""

import base64
import binascii
import re
import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

REQUEST_ID = "0193a1b2-0000-7000-8000-0000000000f1"
CONVERSATION_ID = "0193a1b2-0000-7000-8000-0000000000c1"

TutorAction = Literal["explain", "practice", "check"]
TutorIntent = Literal["explain", "practice", "check", "safety"]

# Підпис JPEG і PNG (перші байти файла).
_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_DATA_URL = re.compile(r"^data:image/(jpeg|jpg|png);base64,", re.IGNORECASE)


def decode_image(value: str, max_bytes: int) -> tuple[str, bytes]:
    """(MIME, байти) фото з base64 або data URL. JPEG/PNG до `max_bytes`, інакше ValueError."""
    raw = _DATA_URL.sub("", value.strip(), count=1)
    if len(raw) > max_bytes * 4 // 3 + 4:
        raise ValueError("image is too large")
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("image_base64 is not valid base64") from None
    if len(data) > max_bytes:
        raise ValueError("image is too large")
    if data.startswith(_JPEG):
        return "image/jpeg", data
    if data.startswith(_PNG):
        return "image/png", data
    raise ValueError("image must be JPEG or PNG")


class TutorAskRequest(BaseModel):
    """Один крок розмови з репетитором.

    - `action` — режим, якщо він уже відомий (кнопки «Поясни», «Дай задачу»/«Підказка»,
      «Перевірити»); без нього режим вибирає AI за `message`.
    - Контекст: `lesson_id`, `module_id`, `card_id` (досить найвужчого — решту backend
      знайде сам). Без них — контекст, збережений у розмові раніше. Урок має бути в розкладі
      чи пакеті класу учня, інакше 403.
    - `explain` з `card_id` — пояснити текст картки іншими словами.
    - `check` — відповідь на поточне завдання розмови (`message` або фото `image_base64`,
      JPEG/PNG до `TUTOR_MAX_IMAGE_BYTES`, base64 без префікса або data URL); без завдання
      в розмові — 422 `TUTOR_TASK_REQUIRED`.
    - Історію реплік клієнт не надсилає: її зберігає сервер (до 8 останніх).
    """

    request_id: uuid.UUID = Field(
        description="Створює клієнт на кожне надсилання; повтор того самого id повертає ту саму "
        "відповідь без нового виклику AI"
    )
    conversation_id: uuid.UUID = Field(
        description="Створює клієнт, один на чат (модуль); чужий id — 404"
    )
    action: TutorAction | None = None
    lesson_id: uuid.UUID | None = None
    module_id: uuid.UUID | None = None
    card_id: uuid.UUID | None = None
    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None
    image_base64: str | None = Field(
        default=None, description="Фото зошита для `check`: JPEG/PNG, base64 або data URL"
    )

    @field_validator("message")
    @classmethod
    def _empty_message(cls, value: str | None) -> str | None:
        return value or None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": REQUEST_ID,
                    "conversation_id": CONVERSATION_ID,
                    "action": "explain",
                    "lesson_id": "0192f0a0-0000-7000-8000-000000000301",
                    "module_id": "0192f0a0-0000-7000-8000-000000000311",
                    "card_id": "0192f0a0-0000-7000-8000-000000000321",
                }
            ]
        }
    )


class TutorTaskOut(BaseModel):
    """Завдання для учня — лише умова. Правильної відповіді, підказок і типових помилок
    тут немає ніколи: перевіряє AI через `action: check`."""

    question: str
    answer_type: str | None = Field(description="`choice` | `number` | `fraction` | `text`")
    options: list[str] | None = Field(default=None, description="Варіанти для `choice`")


class TutorCheckResult(BaseModel):
    correct: bool
    score: float


class TutorAnswerOut(BaseModel):
    """`reply` — Markdown. Кнопки й екран вибирати за `intent` (що AI зробив насправді):
    `safety` — показати `reply` як є, без кнопок уроку (завдання не змінюється)."""

    request_id: uuid.UUID
    conversation_id: uuid.UUID
    reply: str
    intent: TutorIntent
    task: TutorTaskOut | None
    hints_used: int
    suggestions: list[str]
    check_result: TutorCheckResult | None
    cached: bool = Field(
        description="true — готове пояснення з кешу без виклику LLM: спільне для цього "
        "матеріалу (перше «Поясни» розмови) або, коли AI недоступний, пояснення модуля з пакета"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": REQUEST_ID,
                    "conversation_id": CONVERSATION_ID,
                    "reply": "Знайди **20%** від числа 150.",
                    "intent": "practice",
                    "task": {
                        "question": "Знайди 20% від числа 150.",
                        "answer_type": "number",
                        "options": None,
                    },
                    "hints_used": 0,
                    "suggestions": ["💡 Дай підказку", "✅ Відповісти"],
                    "check_result": None,
                    "cached": False,
                }
            ]
        }
    )
