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
