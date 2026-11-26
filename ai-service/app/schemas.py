"""Pydantic-моделі API. Контракт: contracts/openapi.yaml (зміни — спершу там)."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class IntentEnum(str, Enum):
  explain = "explain"
  practice = "practice"
  check = "check"
  safety = "safety"


class MasteryItem(BaseModel):
  topic_id: str
  mastery: float = Field(..., ge=0.0, le=1.0)


class Traits(BaseModel):
  pace: Literal["slow", "normal", "fast"] = "normal"
  needs_detailed_steps: bool = False


class UserProfile(BaseModel):
  mastery: Optional[List[MasteryItem]] = Field(None, max_length=10)
  # Використовується practice._difficulty; без цього поля запит із profile падав з 500
  traits: Optional[Traits] = None


class CheckResult(BaseModel):
  correct: bool
  score: float = Field(..., ge=0.0, le=1.0)
  error_type: Optional[str] = None
  method: Literal["code", "llm"]


class HistoryItem(BaseModel):
  role: Literal["user", "assistant"]
  text: str = Field(..., max_length=4000)


class ChatRequest(BaseModel):
  user_id: Optional[str] = Field(None, max_length=128)
  action: Optional[Literal["explain", "practice", "check"]] = None
  grade: int = Field(..., ge=1, le=11)
  subject: Optional[str] = None
  topic: Optional[str] = None
  topic_id: Optional[str] = None
  message: Optional[str] = ""
  image_base64: Optional[str] = None
  task: Optional[Dict[str, Any]] = None
  hints_used: int = Field(0, ge=0, le=3)
  history: Optional[List[HistoryItem]] = Field(None, max_length=8)
  profile: Optional[UserProfile] = None


class ChatResponse(BaseModel):
  reply: str
  intent: IntentEnum
  topic_id: Optional[str] = None
  task: Optional[Dict[str, Any]] = None
  hints_used: Optional[int] = None
  check_result: Optional[CheckResult] = None
  suggestions: List[str] = Field(default_factory=list)


# ---------- /ai/v1/test-analysis ----------

class TAOption(BaseModel):
  id: str = Field(..., min_length=1, max_length=16)
  text: str = Field(..., max_length=500)


class TAQuestion(BaseModel):
  id: str = Field(..., min_length=1, max_length=64)
  prompt: str = Field(..., min_length=1, max_length=2000)
  kind: Literal["single", "multiple"] = "single"
  options: List[TAOption] = Field(..., min_length=2, max_length=10)
  answer_key: List[str] = Field(..., min_length=1, max_length=10)
  points: int = Field(1, ge=1, le=100)


class TAStudent(BaseModel):
  # Псевдонім (як user_id у /chat). Імен не передавати: у LLM id не потрапляє взагалі
  student_id: str = Field(..., min_length=1, max_length=128)
  answers: Dict[str, List[str]] = Field(default_factory=dict)


class TestAnalysisRequest(BaseModel):
  grade: int = Field(..., ge=1, le=11)
  subject: Optional[str] = Field(None, max_length=100)
  lesson_title: Optional[str] = Field(None, max_length=200)
  test_title: Optional[str] = Field(None, max_length=200)
  pass_score_pct: float = Field(60, ge=0, le=100)
  questions: List[TAQuestion] = Field(..., min_length=1, max_length=50)
  students: List[TAStudent] = Field(..., min_length=1, max_length=60)


StatusEnum = Literal["ok", "attention", "critical"]


class TAWrongAnswer(BaseModel):
  option_ids: List[str]
  option_text: str
  count: int
  student_ids: List[str]


class TAQuestionStat(BaseModel):
  question_id: str
  position: int
  skill: str
  correct_pct: float
  correct_count: int
  answered_count: int
  status: StatusEnum
  wrong_answers: List[TAWrongAnswer]


class TASkill(BaseModel):
  skill: str
  question_ids: List[str]
  correct_pct: float
  status: StatusEnum


class TAEvidence(BaseModel):
  question_id: str
  option_ids: List[str]
  option_text: str
  count: int


class TAMisconception(BaseModel):
  id: str
  title: str
  explanation: str
  question_ids: List[str]
  student_ids: List[str]
  share_pct: float
  evidence: List[TAEvidence]


class TAFeedback(BaseModel):
  teacher: str
  student: str
  parent: str


class TAStudentResult(BaseModel):
  student_id: str
  score_pct: float
  passed: bool
  status: Literal["strong", "ok", "needs_support"]
  correct_question_ids: List[str]
  wrong_question_ids: List[str]
  strong_skills: List[str]
  weak_skills: List[str]
  misconception_ids: List[str]
  feedback: TAFeedback


class TAClassSummary(BaseModel):
  students_total: int
  average_score_pct: float
  passed_count: int
  pass_score_pct: float
  needs_support_ids: List[str]
  overview: str
  recommendations: List[str]


class TestAnalysisResponse(BaseModel):
  class_summary: TAClassSummary
  skills: List[TASkill]
  questions: List[TAQuestionStat]
  misconceptions: List[TAMisconception]
  students: List[TAStudentResult]
  llm_used: bool
