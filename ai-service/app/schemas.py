from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field 
from enum import Enum

class IntentEnum(str, Enum): #joint
    explain = "explain"
    practice = "practice"
    check = "check"

class MasteryItem(BaseModel): # for Request
    topic_id: str
    mastery: float = Field(..., ge=0.0, le=1.0)  # 0 до 1

class UserProfile(BaseModel): # for Request
    mastery: Optional[List[MasteryItem]] = Field(None, max_length=10) 

class CheckResult(BaseModel): # for response
    correct: bool
    score: float = Field(..., ge=0.0, le=1.0)
    error_type: Optional[str] = None
    method: str  # "code" або "llm"

class ChatRequest(BaseModel):
    action: str = 'explain'
    grade: int = Field(5,ge=1, le=11)
    subject: str = 'math'
    topic: str = "Fractions"
    topic_id: Optional[str] = None
    message: Optional[str] = "Поясни як рахувати дроби" #message by student
    style: Optional[str] = "detailed "
    level: Optional[str] = "1"
    task: Optional[Dict[str, Any]] = None
    hints_used: Optional[int] = Field(0, ge=0, le=3)
    history: Optional[List[Dict[str, str]]] = None
    profile: Optional[UserProfile] = None

class ChatResponse(BaseModel):
    reply: str
    intent: IntentEnum
    topic_id: Optional[str] = None
    task: Optional[Dict[str, Any]] = None
    hints_used: Optional[int] = None
    check_result: Optional[CheckResult] = None