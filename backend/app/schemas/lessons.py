import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00-\x1f]+$"
    ),
]
# Текст частин уроку: чернетка може бути порожньою, публікація вимагає укриттєву частину.
LongText = Annotated[str, StringConstraints(max_length=20_000)]
Position = Annotated[int, Field(ge=0, le=1000)]

SUBJECT_ID = "0192f0a0-0000-7000-8000-000000000201"
LESSON_ID = "0192f0a0-0000-7000-8000-000000000301"
MODULE_ID = "0192f0a0-0000-7000-8000-000000000311"
CARD_ID = "0192f0a0-0000-7000-8000-000000000321"
TEST_ID = "0192f0a0-0000-7000-8000-000000000331"
QUESTION_ID = "0192f0a0-0000-7000-8000-000000000341"
MEDIA_ID = "0192f0a0-0000-7000-8000-000000000501"


# ---------- предмети ----------


class SubjectCreate(BaseModel):
    id: uuid.UUID
    name: Title

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": SUBJECT_ID, "name": "Математика"}]}
    )


class SubjectOut(BaseModel):
    id: uuid.UUID
    school_id: uuid.UUID | None = Field(description="null — загальний довідник")
    name: str

    model_config = ConfigDict(from_attributes=True)


# ---------- урок ----------


class LessonCreate(BaseModel):
    """Новий урок (чернетка). `id` генерує клієнт; повтор ідемпотентний."""

    id: uuid.UUID
    subject_id: uuid.UUID
    title: Title
    shelter_part: LongText = Field(description="Укриттєва частина: що робити в укритті")
    main_part: LongText = ""
    grade: int | None = Field(default=None, ge=1, le=11)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": LESSON_ID,
                    "subject_id": SUBJECT_ID,
                    "title": "Звичайні дроби",
                    "shelter_part": "Переглянь коротке відео й розв'яжи 3 задачі.",
                    "main_part": "Розбір задач на уроці.",
                    "grade": 7,
                }
            ]
        }
    )


class LessonUpdate(BaseModel):
    subject_id: uuid.UUID | None = None
    title: Title | None = None
    shelter_part: LongText | None = None
    main_part: LongText | None = None
    grade: int | None = Field(default=None, ge=1, le=11)

    model_config = ConfigDict(json_schema_extra={"examples": [{"title": "Дроби: повторення"}]})


class CardCreate(BaseModel):
    """Картка модуля. `text` — без медіа; `image`/`video` — з медіа того самого типу."""

    id: uuid.UUID
    position: Position
    kind: Literal["text", "image", "video"]
    body: dict[str, Any] = Field(description="Вміст картки (текст, розмітка, підписи)")
    media_asset_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _check(self) -> "CardCreate":
        if self.kind == "text" and self.media_asset_id is not None:
            raise ValueError("text card has no media")
        if self.kind != "text" and self.media_asset_id is None:
            raise ValueError(f"{self.kind} card requires media_asset_id")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": CARD_ID,
                    "position": 1,
                    "kind": "video",
                    "body": {"caption": "Що таке дріб"},
                    "media_asset_id": MEDIA_ID,
                }
            ]
        }
    )


class CardUpdate(BaseModel):
    position: Position | None = None
    kind: Literal["text", "image", "video"] | None = None
    body: dict[str, Any] | None = None
    media_asset_id: uuid.UUID | None = None

    model_config = ConfigDict(json_schema_extra={"examples": [{"body": {"text": "Новий текст"}}]})


class CardOut(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    position: int
    kind: str
    body: dict[str, Any]
    media_asset_id: uuid.UUID | None

    model_config = ConfigDict(from_attributes=True)


class ModuleCreate(BaseModel):
    """Мікромодуль 3–5 хв у частині `shelter` або `main`."""

    id: uuid.UUID
    part: Literal["shelter", "main"]
    position: Position
    title: Title
    duration_min: int = Field(ge=1, le=10)

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": MODULE_ID,
                    "part": "shelter",
                    "position": 1,
                    "title": "Що таке дріб",
                    "duration_min": 4,
                }
            ]
        }
    )


class ModuleUpdate(BaseModel):
    part: Literal["shelter", "main"] | None = None
    position: Position | None = None
    title: Title | None = None
    duration_min: int | None = Field(default=None, ge=1, le=10)

    model_config = ConfigDict(json_schema_extra={"examples": [{"duration_min": 5}]})


class ModuleOut(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    part: str
    position: int
    title: str
    duration_min: int
    cards: list[CardOut] = []

    model_config = ConfigDict(from_attributes=True)


class Option(BaseModel):
    id: Annotated[str, StringConstraints(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")]
    text: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


class QuestionCreate(BaseModel):
    """Питання тесту. `answer_key` — id правильних варіантів (`single` — рівно один)."""

    id: uuid.UUID
    position: Position
    kind: Literal["single", "multiple"]
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    options: list[Option] = Field(min_length=2, max_length=10)
    answer_key: list[str] = Field(min_length=1, max_length=10)
    points: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def _check(self) -> "QuestionCreate":
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError("option ids must be unique")
        if len(set(self.answer_key)) != len(self.answer_key) or not set(self.answer_key) <= set(
            ids
        ):
            raise ValueError("answer_key must be unique ids from options")
        if self.kind == "single" and len(self.answer_key) != 1:
            raise ValueError("single question has exactly one correct option")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": QUESTION_ID,
                    "position": 1,
                    "kind": "single",
                    "prompt": "Скільки буде 1/2 + 1/4?",
                    "options": [{"id": "a", "text": "3/4"}, {"id": "b", "text": "2/6"}],
                    "answer_key": ["a"],
                    "points": 1,
                }
            ]
        }
    )


class QuestionUpdate(BaseModel):
    position: Position | None = None
    kind: Literal["single", "multiple"] | None = None
    prompt: str | None = None
    options: list[Option] | None = None
    answer_key: list[str] | None = None
    points: int | None = Field(default=None, ge=1, le=100)

    model_config = ConfigDict(json_schema_extra={"examples": [{"points": 2}]})


class QuestionOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    position: int
    kind: str
    prompt: str
    options: list[Option]
    answer_key: list[str]
    points: int

    model_config = ConfigDict(from_attributes=True)


class TestCreate(BaseModel):
    __test__ = False  # не збирати pytest-ом

    id: uuid.UUID
    title: Title
    window_enabled: bool = False
    window_hours: Literal[24, 48, 72] | None = None

    @model_validator(mode="after")
    def _check(self) -> "TestCreate":
        if self.window_enabled and self.window_hours is None:
            raise ValueError("window_hours is required when window_enabled")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"id": TEST_ID, "title": "Перевір себе", "window_enabled": True, "window_hours": 48}
            ]
        }
    )


class TestUpdate(BaseModel):
    __test__ = False

    title: Title | None = None
    window_enabled: bool | None = None
    window_hours: Literal[24, 48, 72] | None = None

    model_config = ConfigDict(json_schema_extra={"examples": [{"title": "Підсумковий тест"}]})


class TestOut(BaseModel):
    __test__ = False

    id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    window_enabled: bool
    window_hours: int | None
    questions: list[QuestionOut] = []

    model_config = ConfigDict(from_attributes=True)


class LessonSummary(BaseModel):
    id: uuid.UUID
    subject_id: uuid.UUID
    author_id: uuid.UUID
    title: str
    status: Literal["draft", "published"]
    version: int
    published_at: dt.datetime | None
    grade: int | None
    updated_at: dt.datetime

    model_config = ConfigDict(from_attributes=True)


class LessonOut(LessonSummary):
    """Урок повністю: модулі з картками, тести з питаннями, розмір для ліміту пакета."""

    shelter_part: str
    main_part: str
    modules: list[ModuleOut] = []
    tests: list[TestOut] = []
    size_bytes: int = Field(0, description="Текст + унікальні медіа уроку (з субтитрами)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": LESSON_ID,
                    "subject_id": SUBJECT_ID,
                    "author_id": "0192f0a0-0000-7000-8000-0000000000bb",
                    "title": "Звичайні дроби",
                    "status": "draft",
                    "version": 1,
                    "published_at": None,
                    "grade": 7,
                    "updated_at": "2026-11-05T10:00:00Z",
                    "shelter_part": "Переглянь коротке відео й розв'яжи 3 задачі.",
                    "main_part": "Розбір задач на уроці.",
                    "modules": [],
                    "tests": [],
                    "size_bytes": 1024,
                }
            ]
        },
    )


# ---------- медіа ----------


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: Literal["video", "image", "subtitles"]
    mime_type: str
    size_bytes: int
    sha256: str
    duration_s: int | None
    subtitles_id: uuid.UUID | None = Field(description="VTT-субтитри до відео")
    url: str = Field(description="URL файла (роздає Nginx)")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": MEDIA_ID,
                    "kind": "video",
                    "mime_type": "video/mp4",
                    "size_bytes": 7340032,
                    "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                    "duration_s": None,
                    "subtitles_id": "0192f0a0-0000-7000-8000-000000000502",
                    "url": "/media/video/0192f0a0-0000-7000-8000-000000000501-3f9a.mp4",
                }
            ]
        }
    )


class MediaUpdate(BaseModel):
    """Прив'язка VTT-субтитрів до відео (`null` — відв'язати)."""

    subtitles_id: uuid.UUID | None

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"subtitles_id": "0192f0a0-0000-7000-8000-000000000502"}]}
    )
