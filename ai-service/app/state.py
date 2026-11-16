from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas import UserProfile


class AgentState(BaseModel):
  user_id: Optional[str] = None
  action: Optional[str] = None  
  grade: int
  subject: Optional[str] = None
  topic: Optional[str] = None
  topic_id: Optional[str] = None

  user_input: str = ""
  history: List[dict] = Field(default_factory=list)
  profile: Optional[UserProfile] = None

  current_action: str = "explain"
  current_task: Optional[dict] = None
  hints_used: int = 0

  output_text: str = ""
  suggestions: List[str] = Field(default_factory=list)