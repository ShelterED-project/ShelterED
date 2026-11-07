import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Index, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, uuid_pk


class TaskOutbox(Base):
    """Задачі Celery, які не вдалося поставити в чергу (брокер недоступний у момент `enqueue`).

    Рядок пише `app.workers.celery_app.enqueue`, публікує задача `outbox.flush` (beat), після
    успіху ставить `sent_at`. Усі задачі ідемпотентні, тож повторна публікація безпечна.
    """

    __tablename__ = "task_outbox"
    __table_args__ = (
        # Вибірка неопублікованих — частковим індексом, опубліковані з нього випадають.
        Index(
            "ix_task_outbox_pending",
            "created_at",
            postgresql_where=text("sent_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    task_name: Mapped[str]
    args: Mapped[Any] = mapped_column(JSONB)
    queue: Mapped[str]
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now())
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    sent_at: Mapped[dt.datetime | None]
