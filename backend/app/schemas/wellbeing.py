"""«Як ти зараз?» (docs/wellbeing-checkin.md). Людям — лише картинки й слова, без чисел-оцінок."""

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Picture = Literal["storm", "rain", "cloud", "sun_cloud", "sun"]
Mood = Literal["sunny", "cloudy", "hard"]

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"
SCHOOL_ID = "0192f0a0-0000-7000-8000-0000000000aa"
STUDENT_ID = "0192f0a0-0000-7000-8000-0000000000cc"


class WellbeingDay(BaseModel):
    date: dt.date
    picture: Picture


class StudentWellbeingSelf(BaseModel):
    """Учень бачить себе: свої картинки за 14 днів."""

    view: Literal["self"] = "self"
    student_id: uuid.UUID
    days: list[WellbeingDay] = Field(description="Останні 14 днів, від нових до старих")
    show_support: bool = Field(
        description="Показати в наступній відповіді спокійний блок «Якщо хочеш поговорити»"
    )


class StudentWellbeingParent(BaseModel):
    """Батьки бачать лише тижневе зведення словами, без днів і чисел."""

    view: Literal["parent"] = "parent"
    student_id: uuid.UUID
    week_from: dt.date
    week_to: dt.date
    mood: Mood | None = Field(description="Більшість днів тижня; null — замало відповідей")
    summary: str
    gentle_note: str | None = Field(description="М'який рядок, коли кілька днів були непрості")
    tips: list[str] = Field(description="Поради для розмови (лише разом із gentle_note)")


# Учень — `view: self`, батьки — `view: parent`.
StudentWellbeingOut = Annotated[
    StudentWellbeingSelf | StudentWellbeingParent, Field(discriminator="view")
]

PARENT_EXAMPLE = {
    "view": "parent",
    "student_id": STUDENT_ID,
    "week_from": "2026-10-31",
    "week_to": "2026-11-06",
    "mood": "sunny",
    "summary": "Цього тижня більшість днів — сонячні.",
    "gentle_note": None,
    "tips": [],
}


class WellbeingDistribution(BaseModel):
    """Кількість відповідей за тиждень у трьох групах (не дітей і не оцінок)."""

    sunny: int
    cloudy: int
    hard: int


class GroupWellbeingOut(BaseModel):
    """Зведення класу чи школи за 7 днів; менше 5 різних дітей — `too_few`, без чисел."""

    scope: Literal["class", "school"]
    class_id: uuid.UUID | None = None
    school_id: uuid.UUID | None = None
    week_from: dt.date
    week_to: dt.date
    status: Literal["ok", "too_few"]
    message: str | None = Field(description="«Замало відповідей…» для `too_few`")
    distribution: WellbeingDistribution | None

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "scope": "class",
                    "class_id": CLASS_ID,
                    "school_id": None,
                    "week_from": "2026-10-31",
                    "week_to": "2026-11-06",
                    "status": "ok",
                    "message": None,
                    "distribution": {"sunny": 14, "cloudy": 6, "hard": 3},
                }
            ]
        }
    )


class WellbeingTextsOut(BaseModel):
    """Усі тексти «Як ти зараз?» (діти, батьки, персонал); `version` — для кешу фронтенду."""

    version: str
    child: dict[str, Any]
    parent: dict[str, Any]
    staff: dict[str, Any]
    disclaimer: str
