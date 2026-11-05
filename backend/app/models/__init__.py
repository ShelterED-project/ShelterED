# Імпорт усіх модулів моделей реєструє таблиці в Base.metadata (потрібно Alembic).
from app.models import alerts, auth, lessons, packs, push, rollcall, school, stats, sync
from app.models.base import Base

__all__ = [
    "Base",
    "alerts",
    "auth",
    "lessons",
    "packs",
    "push",
    "rollcall",
    "school",
    "stats",
    "sync",
]
