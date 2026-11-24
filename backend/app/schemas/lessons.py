import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.services.grading import normalize_text

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


class LessonCopy(BaseModel):
    """Копія уроку в нову чернетку. `id` генерує клієнт; повтор ідемпотентний."""

    id: uuid.UUID
    title: Title | None = Field(default=None, description="Назва копії; без неї — як у джерела")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"id": "0192f0a0-0000-7000-8000-000000000302", "title": "Дроби (7-Б)"}]
        }
    )


class MediaOut(BaseModel):
    id: uuid.UUID
    kind: Literal["video", "image", "subtitles"]
    mime_type: str = Field(description="Тип збереженого файла (зображення зазвичай image/webp)")
    size_bytes: int
    sha256: str = Field(description="sha256 збереженого файла (того, що за `url`)")
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


class CardMediaOut(MediaOut):
    """Медіа картки для редактора: файл і (для відео) його субтитри."""

    subtitles: MediaOut | None = Field(description="VTT-субтитри відео (`null` — немає)")


CARD_TEXT_DOC = (
    "Текст картки (`body.text`) — проста розмітка Markdown, решту клієнт показує як є: "
    "`**жирний**`, `*курсив*`, рядок `## ` — заголовок, рядки `- ` — список, рядки `1. ` — "
    "нумерований список, порожній рядок — новий абзац. HTML не підтримується (показується "
    "текстом). Підпис медіа — `body.caption` (звичайний текст)."
)


class CardCreate(BaseModel):
    """Картка модуля. `text` — без медіа; `image`/`video` — з медіа того самого типу."""

    id: uuid.UUID
    position: Position
    kind: Literal["text", "image", "video"]
    body: dict[str, Any] = Field(description=CARD_TEXT_DOC)
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
    body: dict[str, Any] | None = Field(default=None, description=CARD_TEXT_DOC)
    media_asset_id: uuid.UUID | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"body": {"text": "## Дроби\n\n**Дріб** — частина цілого"}}]
        }
    )


class CardOut(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    position: int
    kind: str
    body: dict[str, Any] = Field(description=CARD_TEXT_DOC)
    media_asset_id: uuid.UUID | None
    # Лише у відповідях редактора (урок, картка); у пакеті поля немає — медіа там у маніфесті.
    media: CardMediaOut | None = Field(
        default=None,
        exclude_if=lambda v: v is None,
        description="Медіа картки з URL і субтитрами (у відповідях редактора; у пакеті немає)",
    )

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


OrderIds = Annotated[list[uuid.UUID], Field(max_length=1000)]


class ModuleOrder(BaseModel):
    """Новий порядок модулів однієї частини уроку: `ids` — усі модулі частини, кожен раз."""

    part: Literal["shelter", "main"]
    ids: OrderIds

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"part": "shelter", "ids": [MODULE_ID]}]}
    )


class ItemOrder(BaseModel):
    """Новий порядок карток модуля чи питань тесту: `ids` — усі елементи, кожен раз."""

    ids: OrderIds

    model_config = ConfigDict(json_schema_extra={"examples": [{"ids": [CARD_ID]}]})


class Option(BaseModel):
    id: Annotated[str, StringConstraints(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")]
    text: Annotated[str, StringConstraints(min_length=1, max_length=1000)]


QuestionKind = Literal["single", "multiple", "text", "match"]
OptionIdStr = Annotated[
    str, StringConstraints(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9_-]+$")
]
# Ключ: id варіантів (`single`/`multiple`), прийнятні відповіді (`text`) або
# {id лівого: id правого} (`match`).
AnswerKey = (
    list[Annotated[str, StringConstraints(min_length=1, max_length=200)]]
    | dict[OptionIdStr, OptionIdStr]
)
Explanation = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
TEXT_ANSWERS_MAX = 20

_QUESTION_DOC = """Питання тесту. Формат залежить від `kind`:

- `single` / `multiple` — `options` (2–10 варіантів), `answer_key` — id правильних варіантів
  (`single` — рівно один);
- `text` — учень вводить коротку відповідь: `options` порожній, `answer_key` — 1–20 прийнятних
  відповідей (до 200 символів). Порівняння без різниці регістру, пробілів на краях і всередині
  (кілька поспіль = один) та виду апострофа (’ ʼ ' ` — однакові);
- `match` — відповідність: `options` — ліві елементи (2–10), `right_options` — праві (2–10,
  можна із зайвими), `answer_key` — `{id лівого: id правого}` для кожного лівого, праві не
  повторюються.

Питання зараховане лише повністю правильною відповіддю (часткових балів немає).
`explanation` (до 2000 символів) — розбір для учня; у пакет потрапляє лише в тренувальному
тесті (без вікна), разом із ключем."""


def _check_question(
    kind: str,
    options: list[Option],
    right_options: list[Option] | None,
    answer_key: list[str] | dict[str, str],
) -> None:
    ids = [o.id for o in options]
    if len(set(ids)) != len(ids):
        raise ValueError("option ids must be unique")
    if kind != "match" and right_options is not None:
        raise ValueError("right_options are allowed only for match question")
    if kind in ("single", "multiple"):
        if len(options) < 2:
            raise ValueError(f"{kind} question needs at least 2 options")
        if not isinstance(answer_key, list) or not answer_key:
            raise ValueError("answer_key must be a non-empty list of option ids")
        if len(set(answer_key)) != len(answer_key) or not set(answer_key) <= set(ids):
            raise ValueError("answer_key must be unique ids from options")
        if kind == "single" and len(answer_key) != 1:
            raise ValueError("single question has exactly one correct option")
    elif kind == "text":
        if options:
            raise ValueError("text question has no options")
        if not isinstance(answer_key, list) or not 1 <= len(answer_key) <= TEXT_ANSWERS_MAX:
            raise ValueError(f"answer_key must be a list of 1..{TEXT_ANSWERS_MAX} accepted answers")
        if not all(normalize_text(a) for a in answer_key):
            raise ValueError("accepted answer cannot be blank")
    else:  # match
        if len(options) < 2:
            raise ValueError("match question needs at least 2 left items (options)")
        if right_options is None or len(right_options) < 2:
            raise ValueError("match question needs at least 2 right_options")
        right = [o.id for o in right_options]
        if len(set(right)) != len(right):
            raise ValueError("right_options ids must be unique")
        if not isinstance(answer_key, dict) or set(answer_key) != set(ids):
            raise ValueError("answer_key must map every left id to a right id")
        values = list(answer_key.values())
        if not set(values) <= set(right) or len(set(values)) != len(values):
            raise ValueError("answer_key values must be distinct ids from right_options")


class QuestionCreate(BaseModel):
    __doc__ = _QUESTION_DOC

    id: uuid.UUID
    position: Position
    kind: QuestionKind
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    options: list[Option] = Field(default=[], max_length=10)
    right_options: list[Option] | None = Field(
        default=None, max_length=10, description="Лише `match`: праві елементи"
    )
    answer_key: AnswerKey
    points: int = Field(default=1, ge=1, le=100)
    explanation: Explanation | None = Field(
        default=None, description="Розбір для учня (у пакеті лише в тренувальному тесті)"
    )

    @model_validator(mode="after")
    def _check(self) -> "QuestionCreate":
        _check_question(self.kind, self.options, self.right_options, self.answer_key)
        if self.explanation == "":
            self.explanation = None
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
                    "explanation": "Зведи до спільного знаменника: 2/4 + 1/4 = 3/4.",
                },
                {
                    "id": "0192f0a0-0000-7000-8000-000000000342",
                    "position": 2,
                    "kind": "text",
                    "prompt": "Як називається число над рискою дробу?",
                    "options": [],
                    "answer_key": ["чисельник"],
                    "points": 1,
                },
                {
                    "id": "0192f0a0-0000-7000-8000-000000000343",
                    "position": 3,
                    "kind": "match",
                    "prompt": "Зістав дріб і десятковий запис",
                    "options": [{"id": "l1", "text": "1/2"}, {"id": "l2", "text": "1/4"}],
                    "right_options": [
                        {"id": "r1", "text": "0,25"},
                        {"id": "r2", "text": "0,5"},
                        {"id": "r3", "text": "0,75"},
                    ],
                    "answer_key": {"l1": "r2", "l2": "r1"},
                    "points": 2,
                },
            ]
        }
    )


class QuestionUpdate(BaseModel):
    """Часткова зміна; після злиття з наявним питання перевіряється як `QuestionCreate`.
    Зміна `kind` на не-`match` без `right_options` прибирає праві елементи.
    `explanation: null` чи `""` — прибрати пояснення."""

    position: Position | None = None
    kind: QuestionKind | None = None
    prompt: str | None = None
    options: list[Option] | None = None
    right_options: list[Option] | None = None
    answer_key: AnswerKey | None = None
    points: int | None = Field(default=None, ge=1, le=100)
    explanation: Explanation | None = None

    model_config = ConfigDict(json_schema_extra={"examples": [{"points": 2}]})


class QuestionOut(BaseModel):
    id: uuid.UUID
    test_id: uuid.UUID
    position: int
    kind: QuestionKind
    prompt: str
    options: list[Option]
    right_options: list[Option] | None = Field(description="Лише `match`: праві елементи")
    answer_key: list[str] | dict[str, str]
    points: int
    explanation: str | None

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
    limit_bytes: int = Field(
        0, description="Ліміт розміру уроку й пакета дня (публікація понад нього не пройде)"
    )
    copied_from_id: uuid.UUID | None = Field(
        default=None, description="Урок-джерело, якщо урок створено копіюванням"
    )

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
                    "limit_bytes": 52428800,
                    "copied_from_id": None,
                }
            ]
        },
    )


# ---------- медіа ----------


class MediaUpdate(BaseModel):
    """Прив'язка VTT-субтитрів до відео (`null` — відв'язати)."""

    subtitles_id: uuid.UUID | None

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"subtitles_id": "0192f0a0-0000-7000-8000-000000000502"}]}
    )
