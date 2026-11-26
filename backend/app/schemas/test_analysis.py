"""AI-аналіз тесту класу (контракт B: docs/test-analysis.md).

`result` — відповідь AI-сервісу (`/ai/v1/test-analysis`) зі справжніми id учнів і правками
вчителя в `students[].feedback`; структуру описує контракт AI, backend її не звужує, лише
додає `students[].feedback_edited`.
"""

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"
TEST_ID = "0192f0a0-0000-7000-8000-000000000301"
ANALYSIS_ID = "0192f0a0-0000-7000-8000-000000000a01"
TEACHER_ID = "0192f0a0-0000-7000-8000-0000000000aa"
STUDENT_ID = "0192f0a0-0000-7000-8000-0000000000cc"
QUESTION_ID = "0192f0a0-0000-7000-8000-000000000401"

AnalysisStatus = Literal["processing", "draft", "published", "failed"]

FEEDBACK_MAX_CHARS = 3000

_STUDENT_EXAMPLE: dict[str, Any] = {
    "student_id": STUDENT_ID,
    "score_pct": 50.0,
    "passed": False,
    "status": "needs_support",
    "correct_question_ids": [],
    "wrong_question_ids": [QUESTION_ID],
    "strong_skills": [],
    "weak_skills": ["Додавання дробів"],
    "misconception_ids": ["m1"],
    "feedback": {
        "teacher": "Додає чисельники й знаменники окремо.",
        "student": "Ти добре стараєшся! Повтори правило: знаменник лишається тим самим.",
        "parent": "Варто разом повторити додавання дробів з однаковими знаменниками.",
    },
    "feedback_edited": False,
}


class AnalysisError(BaseModel):
    code: str = Field(description="AI_UNAVAILABLE / AI_BAD_REQUEST / AI_TIMEOUT")


class TestAnalysisOut(BaseModel):
    __test__ = False  # не збирати pytest-ом

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": ANALYSIS_ID,
                    "class_id": CLASS_ID,
                    "test_id": TEST_ID,
                    "status": "draft",
                    "attempts_count": 24,
                    "created_at": "2026-12-08T10:15:02Z",
                    "created_by": TEACHER_ID,
                    "completed_at": "2026-12-08T10:15:41Z",
                    "published_at": None,
                    "error": None,
                    "result": {
                        "class_summary": {
                            "students_total": 24,
                            "average_score_pct": 68.5,
                            "passed_count": 17,
                            "pass_score_pct": 60,
                            "needs_support_ids": [STUDENT_ID],
                            "overview": "Клас загалом засвоїв тему…",
                            "recommendations": ["Повторити правило додавання дробів"],
                        },
                        "skills": [],
                        "questions": [],
                        "misconceptions": [],
                        "students": [_STUDENT_EXAMPLE],
                        "llm_used": True,
                    },
                }
            ]
        }
    )

    id: uuid.UUID
    class_id: uuid.UUID
    test_id: uuid.UUID
    status: AnalysisStatus
    attempts_count: int = Field(description="Зараховані спроби класу на момент запуску")
    created_at: dt.datetime
    created_by: uuid.UUID | None
    completed_at: dt.datetime | None
    published_at: dt.datetime | None
    error: AnalysisError | None = Field(description="Лише при `failed`")
    result: dict[str, Any] | None = Field(
        description="Відповідь AI зі справжніми id учнів і правками вчителя; "
        "null, поки `processing` чи `failed`"
    )


class FeedbackEditIn(BaseModel):
    """Обидва поля необов'язкові: відсутнє — без змін, `null` — повернути текст AI."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"examples": [{"student": "Новий текст для учня", "parent": None}]},
    )

    student: str | None = Field(default=None, max_length=FEEDBACK_MAX_CHARS)
    parent: str | None = Field(default=None, max_length=FEEDBACK_MAX_CHARS)


class AnalysisStudentOut(BaseModel):
    """Елемент `result.students[]` після правки."""

    model_config = ConfigDict(extra="allow", json_schema_extra={"examples": [_STUDENT_EXAMPLE]})

    student_id: uuid.UUID
    feedback: dict[str, str]
    feedback_edited: bool


class TestFeedbackItem(BaseModel):
    __test__ = False  # не збирати pytest-ом

    analysis_id: uuid.UUID
    test_id: uuid.UUID
    test_title: str
    lesson_title: str
    subject: str | None
    score_pct: float | None
    correct_count: int
    questions_total: int
    text: str = Field(description="Учню — текст для учня, батькам — для батьків (Markdown)")
    published_at: dt.datetime


class TestFeedbackOut(BaseModel):
    __test__ = False  # не збирати pytest-ом

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "items": [
                        {
                            "analysis_id": ANALYSIS_ID,
                            "test_id": TEST_ID,
                            "test_title": "Дроби: перевір себе",
                            "lesson_title": "Додавання дробів з однаковими знаменниками",
                            "subject": "Математика",
                            "score_pct": 62.5,
                            "correct_count": 5,
                            "questions_total": 8,
                            "text": "Правильних відповідей: **5 з 8**…",
                            "published_at": "2026-12-08T10:21:30Z",
                        }
                    ]
                }
            ]
        }
    )

    items: list[TestFeedbackItem]
