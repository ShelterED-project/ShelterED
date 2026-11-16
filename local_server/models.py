from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
import uuid
from database import Base

class RollCall(Base):
    __tablename__ = "roll_call"
    id = Column(Integer, primary_key=True, index=True)
    client_event_id = Column(String, unique=True, index=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, index=True)
    student_name = Column(String, index=True)
    status = Column(String, default="in_shelter")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_synced = Column(Boolean, default=False)