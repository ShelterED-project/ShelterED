# Імпорт усіх модулів моделей реєструє таблиці в Base.metadata (потрібно Alembic).
from app.models import (
    alerts,
    auth,
    lessons,
    packs,
    privacy,
    push,
    rollcall,
    school,
    stats,
    sync,
    wellbeing,
)
from app.models.base import Base

__all__ = [
    "Base",
    "alerts",
    "auth",
    "lessons",
    "packs",
    "privacy",
    "push",
    "rollcall",
    "school",
    "stats",
    "sync",
    "wellbeing",
]
