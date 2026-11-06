"""«Як ти зараз?» (docs/wellbeing-checkin.md). Людям — лише картинки й слова, без чисел-оцінок."""

import datetime as dt
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

Picture = Literal["storm", "rain", "cloud", "sun_cloud", "sun"]
Mood = Literal["sunny", "cloudy", "hard"]

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


class WellbeingTextsOut(BaseModel):
    """Усі тексти «Як ти зараз?» (діти, батьки); `version` — для кешу фронтенду."""

    version: str
    child: dict[str, Any]
    parent: dict[str, Any]
    disclaimer: str
