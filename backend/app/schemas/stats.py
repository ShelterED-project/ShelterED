"""Кабінети й дашборди (B14). Дані — з агрегатів, які рахує Celery (`computed_at` — коли)."""

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CLASS_ID = "0192f0a0-0000-7000-8000-000000000001"
LESSON_ID = "0192f0a0-0000-7000-8000-000000000101"
TEST_ID = "0192f0a0-0000-7000-8000-000000000301"
QUESTION_ID = "0192f0a0-0000-7000-8000-000000000401"
SUBJECT_ID = "0192f0a0-0000-7000-8000-000000000051"
STUDENT_ID = "0192f0a0-0000-7000-8000-0000000000cc"
ALERT_ID = "0192f0a0-0000-7000-8000-000000000901"

# passed — зарахована спроба з оцінкою ≥ порогу; not_passed — оцінка нижча або вікно минуло
# без зарахованої спроби; closing_soon — до кінця вікна < STATS_CLOSING_SOON_H год і спроби
# ще немає; pending — спроби ще немає (вікно не почалось, відкрите чи тест без вікна).
StudentTestStatus = Literal["passed", "not_passed", "closing_soon", "pending"]

DEADLINE_DESCRIPTION = (
    "Кінець вікна тесту: завершення уроку (годинник пристрою) + `window_hours`; "
    "null — тест без вікна або урок ще не завершено"
)


class ClassLessonProgress(BaseModel):
    lesson_id: uuid.UUID
    title: str
    subject_name: str
    first_date: dt.date = Field(description="Перша дата уроку в розкладі класу")
    students_total: int
    students_completed: int = Field(description="Учні, що завершили всі модулі уроку")
    avg_progress_pct: int
    tests_scored: int = Field(description="Пари (учень, тест уроку) із зарахованою спробою")
    tests_passed: int
    avg_score: float | None


class ClassProgressOut(BaseModel):
    class_id: uuid.UUID
    computed_at: dt.datetime | None
    lessons: list[ClassLessonProgress]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "class_id": CLASS_ID,
                    "computed_at": "2026-11-05T10:00:00Z",
                    "lessons": [
                        {
                            "lesson_id": LESSON_ID,
                            "title": "Дроби",
                            "subject_name": "Математика",
                            "first_date": "2026-11-05",
                            "students_total": 25,
                            "students_completed": 18,
                            "avg_progress_pct": 81,
                            "tests_scored": 15,
                            "tests_passed": 12,
                            "avg_score": 74.5,
                        }
                    ],
                }
            ]
        }
    )


class StudentTestResult(BaseModel):
    student_id: uuid.UUID
    display_name: str
    last_name: str | None
    status: StudentTestStatus
    score: float | None
    attempts: int
    deadline: dt.datetime | None = Field(description=DEADLINE_DESCRIPTION)
    is_suspicious: bool = Field(description="Час пристрою підозрілий — перевірити (не блокується)")


class TestStatusCounts(BaseModel):
    passed: int
    not_passed: int
    closing_soon: int
    pending: int


class ClassTestOut(BaseModel):
    test_id: uuid.UUID
    lesson_id: uuid.UUID
    lesson_title: str
    title: str
    window_hours: int | None = Field(description="Тривалість вікна; null — тест без вікна")
    counts: TestStatusCounts
    students: list[StudentTestResult]


class ClassTestsOut(BaseModel):
    class_id: uuid.UUID
    pass_score: int = Field(description="Поріг «склав», %")
    tests: list[ClassTestOut]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "class_id": CLASS_ID,
                    "pass_score": 60,
                    "tests": [
                        {
                            "test_id": TEST_ID,
                            "lesson_id": LESSON_ID,
                            "lesson_title": "Дроби",
                            "title": "Перевір себе",
                            "window_hours": 48,
                            "counts": {
                                "passed": 0,
                                "not_passed": 0,
                                "closing_soon": 1,
                                "pending": 0,
                            },
                            "students": [
                                {
                                    "student_id": STUDENT_ID,
                                    "display_name": "Іван",
                                    "last_name": "Петренко",
                                    "status": "closing_soon",
                                    "score": None,
                                    "attempts": 0,
                                    "deadline": "2026-11-07T09:41:00Z",
                                    "is_suspicious": False,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )


class GapQuestion(BaseModel):
    question_id: uuid.UUID
    test_id: uuid.UUID
    prompt: str
    answered: int
    correct: int
    correct_pct: int


class GapTopic(BaseModel):
    lesson_id: uuid.UUID
    title: str
    subject_name: str
    avg_score: float | None
    tests_scored: int
    tests_passed: int
    is_gap: bool = Field(description="Середня оцінка класу нижча за поріг «склав»")
    questions: list[GapQuestion] = Field(description="Від найгірше засвоєного")


class ClassGapsOut(BaseModel):
    class_id: uuid.UUID
    pass_score: int
    topics: list[GapTopic] = Field(description="Тема = урок; від найнижчої середньої оцінки")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "class_id": CLASS_ID,
                    "pass_score": 60,
                    "topics": [
                        {
                            "lesson_id": LESSON_ID,
                            "title": "Дроби",
                            "subject_name": "Математика",
                            "avg_score": 48.0,
                            "tests_scored": 10,
                            "tests_passed": 3,
                            "is_gap": True,
                            "questions": [
                                {
                                    "question_id": QUESTION_ID,
                                    "test_id": TEST_ID,
                                    "prompt": "1/2 + 1/4 = ?",
                                    "answered": 10,
                                    "correct": 3,
                                    "correct_pct": 30,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
    )


class StudentLessonProgress(BaseModel):
    lesson_id: uuid.UUID
    title: str
    subject_name: str
    progress_pct: int
    modules_done: int
    modules_total: int
    completed_at: dt.datetime | None = Field(description="Завершення уроку (годинник пристрою)")
    study_minutes: int


class StudentTestOut(BaseModel):
    test_id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    window_hours: int | None
    status: StudentTestStatus
    score: float | None
    attempts: int
    deadline: dt.datetime | None = Field(description=DEADLINE_DESCRIPTION)


class StudyDay(BaseModel):
    day: dt.date
    minutes: int


class StudyTime(BaseModel):
    """Час навчання = плановий час (`duration_min`) завершених модулів, день — за поясом школи."""

    total_minutes: int
    last_7_days_minutes: int
    days: list[StudyDay] = Field(description="Останні 7 днів, включно з сьогодні")


class StudentProgressOut(BaseModel):
    student_id: uuid.UUID
    computed_at: dt.datetime | None
    lessons: list[StudentLessonProgress]
    tests: list[StudentTestOut]
    study: StudyTime

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "student_id": STUDENT_ID,
                    "computed_at": "2026-11-05T10:00:00Z",
                    "lessons": [
                        {
                            "lesson_id": LESSON_ID,
                            "title": "Дроби",
                            "subject_name": "Математика",
                            "progress_pct": 100,
                            "modules_done": 3,
                            "modules_total": 3,
                            "completed_at": "2026-11-05T09:41:00Z",
                            "study_minutes": 12,
                        }
                    ],
                    "tests": [
                        {
                            "test_id": TEST_ID,
                            "lesson_id": LESSON_ID,
                            "title": "Перевір себе",
                            "window_hours": 48,
                            "status": "pending",
                            "score": None,
                            "attempts": 0,
                            "deadline": "2026-11-07T09:41:00Z",
                        }
                    ],
                    "study": {
                        "total_minutes": 12,
                        "last_7_days_minutes": 12,
                        "days": [{"day": "2026-11-05", "minutes": 12}],
                    },
                }
            ]
        }
    )


class KnowledgeMapSubject(BaseModel):
    subject_id: uuid.UUID
    name: str
    lessons_total: int
    lessons_completed: int
    avg_score: float | None
    is_gap: bool = Field(description="Середня оцінка тестів предмета нижча за поріг «склав»")


class KnowledgeMapOut(BaseModel):
    student_id: uuid.UUID
    subjects: list[KnowledgeMapSubject]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "student_id": STUDENT_ID,
                    "subjects": [
                        {
                            "subject_id": SUBJECT_ID,
                            "name": "Математика",
                            "lessons_total": 4,
                            "lessons_completed": 3,
                            "avg_score": 72.5,
                            "is_gap": False,
                        }
                    ],
                }
            ]
        }
    )


class AlertStudyItem(BaseModel):
    alert_id: uuid.UUID
    source: Literal["api", "manual"]
    is_drill: bool
    class_id: uuid.UUID | None = Field(description="Лише для ручної тривоги класу")
    started_at: dt.datetime
    ended_at: dt.datetime | None
    duration_minutes: int = Field(description="Тривалість (триває — до зараз)")
    students: int | None = Field(description="Учні, що завершували модулі під час тривоги")
    study_minutes: int | None = Field(
        description="Плановий час модулів, завершених під час тривоги; null — ще не пораховано"
    )


class AlertStudyOut(BaseModel):
    """Журнал тривог школи з навчанням, що на них припало (дашборд адміністрації, P2)."""

    computed_at: dt.datetime | None
    alert_minutes: int
    study_minutes: int
    alerts: list[AlertStudyItem]

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "computed_at": "2026-11-05T11:00:00Z",
                    "alert_minutes": 75,
                    "study_minutes": 96,
                    "alerts": [
                        {
                            "alert_id": ALERT_ID,
                            "source": "api",
                            "is_drill": False,
                            "class_id": None,
                            "started_at": "2026-11-05T09:30:00Z",
                            "ended_at": "2026-11-05T10:45:00Z",
                            "duration_minutes": 75,
                            "students": 12,
                            "study_minutes": 96,
                        }
                    ],
                }
            ]
        }
    )
