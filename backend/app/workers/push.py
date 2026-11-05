"""Web Push (B8). Тут — лише постановка в чергу `push`; відправку (pywebpush, підписки
класу, TTL і пріоритет) реалізує B8 у тілі задачі `push.send`.

Payload мінімальний: тип + id, без персональних даних.
"""

import logging
import uuid
from typing import Literal

from app.workers.celery_app import celery_app, enqueue

logger = logging.getLogger(__name__)

PushType = Literal["alert", "all_clear", "pack_updated"]


async def enqueue_push(push_type: PushType, *, class_id: uuid.UUID, **ids: object) -> None:
    """Єдина точка постановки push. Одержувачі — пристрої класу `class_id` (учні, вчителі;
    для тривоги — і батьки) визначає задача B8. `ids`: alert_id, lesson_id, pack_id тощо."""
    payload = {"type": push_type, "class_id": str(class_id)}
    payload.update({k: None if v is None else str(v) for k, v in ids.items()})
    await enqueue("push.send", args=[payload], queue="push")


@celery_app.task(name="push.send")
def send(payload: dict[str, str | None]) -> None:
    """Заглушка B8: відправка ще не реалізована, задача лише фіксує тип повідомлення."""
    logger.info("Push %s queued (sending is not implemented yet)", payload.get("type"))
