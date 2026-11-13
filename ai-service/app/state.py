from typing import List, Optional
from pydantic import BaseModel, Field


class AgentState(BaseModel):
  user_id: str
  grade: int
  subject: Optional[str] = None
  topic: Optional[str] = None
  topic_id: Optional[str] = None

  user_input: str = ""
  history: List[dict] = Field(default_factory=list)

  current_action: str = "explain"  # "explain", "practice", "test"
  depth_level: int = 1  # Для Крота-Дослідника (1-3)

  output_text: str = ""
  suggestions: List[str] = Field(default_factory=list)