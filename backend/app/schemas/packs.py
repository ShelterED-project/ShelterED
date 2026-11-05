"""Пакети знань «Рюкзак»: маніфест і вміст пакета (контракт B4, логіка — B6)."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.lessons import ModuleOut, Option
from app.schemas.school import ScheduleItem

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"
PACK_ID = "0192f0a0-0000-7000-8000-000000000601"
LESSON_ID = "0192f0a0-0000-7000-8000-000000000301"
MODULE_ID = "0192f0a0-0000-7000-8000-000000000311"
TEST_ID = "0192f0a0-0000-7000-8000-000000000331"
MEDIA_ID = "0192f0a0-0000-7000-8000-000000000501"
HASH = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


class PackManifestItem(BaseModel):
    """Актуальна версія пакета класу на дату."""

    id: uuid.UUID
    class_id: uuid.UUID
    pack_date: dt.date
    version: int
    content_hash: str = Field(description="sha256 вмісту; він же ETag для `GET /packs/{id}`")
    size_bytes: int
    built_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)


class MediaManifestItem(BaseModel):
    """Медіафайл для кешу Service Worker (окремий URL, кешується незалежно від пакета)."""

    id: uuid.UUID
    kind: Literal["video", "image", "subtitles"]
    url: str
    size_bytes: int
    sha256: str
    subtitles_id: uuid.UUID | None = Field(description="VTT-субтитри до відео")
    needed_on: dt.date = Field(description="Перший день, на який файл потрібен")


class PackManifestOut(BaseModel):
    """Маніфест: пакети (текст і тести) на весь діапазон, медіа — лише на сьогодні й завтра."""

    class_id: uuid.UUID
    date_from: dt.date
    date_to: dt.date
    packs: list[PackManifestItem]
    media: list[MediaManifestItem]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "class_id": CLASS_ID,
                    "date_from": "2026-11-09",
                    "date_to": "2026-11-15",
                    "packs": [
                        {
                            "id": PACK_ID,
                            "class_id": CLASS_ID,
                            "pack_date": "2026-11-09",
                            "version": 3,
                            "content_hash": HASH,
                            "size_bytes": 48213,
                            "built_at": "2026-11-08T18:00:00Z",
                        }
                    ],
                    "media": [
                        {
                            "id": MEDIA_ID,
                            "kind": "video",
                            "url": "/media/video/0192f0a0-0000-7000-8000-000000000501-3f9a.mp4",
                            "size_bytes": 7340032,
                            "sha256": HASH,
                            "subtitles_id": "0192f0a0-0000-7000-8000-000000000502",
                            "needed_on": "2026-11-09",
                        }
                    ],
                }
            ]
        }
    )


class PackQuestion(BaseModel):
    """Питання тесту в пакеті. `answer_key` (id правильних варіантів) є лише в тренувальному
    тесті (`window_enabled = false`) для миттєвої перевірки офлайн; в оцінюваному тесті з
    вікном поля немає зовсім — оцінює сервер після синхронізації."""

    id: uuid.UUID
    position: int
    kind: Literal["single", "multiple"]
    prompt: str
    options: list[Option]
    points: int
    answer_key: list[str] | None = Field(default=None, exclude_if=lambda v: v is None)


class PackTest(BaseModel):
    id: uuid.UUID
    title: str
    window_enabled: bool
    window_hours: int | None
    questions: list[PackQuestion]


class PackLesson(BaseModel):
    """Опублікований урок у версії, з якою зібрано пакет."""

    id: uuid.UUID
    version: int
    subject_id: uuid.UUID
    title: str
    shelter_part: str
    main_part: str
    modules: list[ModuleOut]
    tests: list[PackTest]


class PackExplanation(BaseModel):
    """Закешоване пояснення ШІ-репетитора для офлайну (B13.3)."""

    id: uuid.UUID
    lesson_id: uuid.UUID
    module_id: uuid.UUID | None
    text: str


class PackOut(BaseModel):
    """Вміст пакета «Рюкзак»: клас + дата. Медіа — окремими URL із маніфесту."""

    id: uuid.UUID
    class_id: uuid.UUID
    pack_date: dt.date
    version: int
    content_hash: str
    built_at: dt.datetime
    timezone: str
    schedule: list[ScheduleItem]
    lessons: list[PackLesson]
    explanations: list[PackExplanation]
    media: list[uuid.UUID] = Field(
        description="id медіа уроків пакета разом із субтитрами (файли — за URL з маніфесту)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": PACK_ID,
                    "class_id": CLASS_ID,
                    "pack_date": "2026-11-09",
                    "version": 3,
                    "content_hash": HASH,
                    "built_at": "2026-11-08T18:00:00Z",
                    "timezone": "Europe/Kyiv",
                    "schedule": [
                        {
                            "kind": "regular",
                            "slot_id": "0192f0a0-0000-7000-8000-000000000101",
                            "override_id": None,
                            "subject_id": "0192f0a0-0000-7000-8000-000000000201",
                            "starts_at": "09:00:00",
                            "ends_at": "09:45:00",
                            "starts_at_utc": "2026-11-09T07:00:00Z",
                            "ends_at_utc": "2026-11-09T07:45:00Z",
                            "lesson_id": LESSON_ID,
                        }
                    ],
                    "lessons": [
                        {
                            "id": LESSON_ID,
                            "version": 2,
                            "subject_id": "0192f0a0-0000-7000-8000-000000000201",
                            "title": "Звичайні дроби",
                            "shelter_part": "Переглянь коротке відео й розв'яжи 3 задачі.",
                            "main_part": "Розбір задач на уроці.",
                            "modules": [
                                {
                                    "id": MODULE_ID,
                                    "lesson_id": LESSON_ID,
                                    "part": "shelter",
                                    "position": 1,
                                    "title": "Що таке дріб",
                                    "duration_min": 4,
                                    "cards": [
                                        {
                                            "id": "0192f0a0-0000-7000-8000-000000000321",
                                            "module_id": MODULE_ID,
                                            "position": 1,
                                            "kind": "video",
                                            "body": {"caption": "Дроби за 3 хвилини"},
                                            "media_asset_id": MEDIA_ID,
                                        }
                                    ],
                                }
                            ],
                            "tests": [
                                {
                                    "id": TEST_ID,
                                    "title": "Перевір себе",
                                    "window_enabled": True,
                                    "window_hours": 48,
                                    "questions": [
                                        {
                                            "id": "0192f0a0-0000-7000-8000-000000000341",
                                            "position": 1,
                                            "kind": "single",
                                            "prompt": "Скільки буде 1/2 + 1/4?",
                                            "options": [
                                                {"id": "a", "text": "3/4"},
                                                {"id": "b", "text": "2/6"},
                                            ],
                                            "points": 1,
                                        }
                                    ],
                                },
                                {
                                    "id": "0192f0a0-0000-7000-8000-000000000332",
                                    "title": "Тренування",
                                    "window_enabled": False,
                                    "window_hours": None,
                                    "questions": [
                                        {
                                            "id": "0192f0a0-0000-7000-8000-000000000342",
                                            "position": 1,
                                            "kind": "single",
                                            "prompt": "Що більше: 1/2 чи 1/3?",
                                            "options": [
                                                {"id": "a", "text": "1/2"},
                                                {"id": "b", "text": "1/3"},
                                            ],
                                            "points": 1,
                                            "answer_key": ["a"],
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                    "explanations": [
                        {
                            "id": "0192f0a0-0000-7000-8000-000000000701",
                            "lesson_id": LESSON_ID,
                            "module_id": MODULE_ID,
                            "text": "Дріб показує, на скільки частин поділили ціле.",
                        }
                    ],
                    "media": [MEDIA_ID, "0192f0a0-0000-7000-8000-000000000502"],
                }
            ]
        }
    )
