# Імпорт усіх модулів моделей реєструє таблиці в Base.metadata (потрібно Alembic).
from app.models import alerts, lessons, packs, push, rollcall, school, sync
from app.models.base import Base

__all__ = ["Base", "alerts", "lessons", "packs", "push", "rollcall", "school", "sync"]
