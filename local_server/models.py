from sqlalchemy import Column, Integer, String, Boolean, DateTime
from datetime import datetime
from database import Base

class RollCall(Base):
    __tablename__ = "roll_call"

    id = Column(Integer, primary_key=True, index=True)
    student_name = Column(String, index=True)
    status = Column(String, default="В укритті")
    created_at = Column(DateTime, default=datetime.utcnow)
    is_synced = Column(Boolean, default=False)