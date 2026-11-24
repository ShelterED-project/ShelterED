"""Стиснення відео сервером (черга `default`, ffmpeg). Задача ідемпотентна: запис не в стані
`processing` пропускається (див. `services/video.py`)."""

import asyncio
import uuid

from app.core.config import get_settings
from app.core.db import standalone_session
from app.core.storage import LocalMediaStorage
from app.services import video as video_service
from app.workers.celery_app import LONG_TASK_LIMITS, TRANSIENT_RETRY, celery_app, enqueue


async def enqueue_process_video(media_id: uuid.UUID) -> None:
    await enqueue("media.process_video", args=[str(media_id)])


async def _process_video(media_id: uuid.UUID) -> str:
    settings = get_settings()
    storage = LocalMediaStorage(settings.media_root, settings.media_url_prefix)
    async with standalone_session() as session:
        return await video_service.process_video(session, storage, settings, media_id)


@celery_app.task(name="media.process_video", **LONG_TASK_LIMITS, **TRANSIENT_RETRY)
def process_video(media_id: str) -> str:
    """Стискає відео (`processing` → `ready` / `failed`). Повертає підсумковий стан."""
    return asyncio.run(_process_video(uuid.UUID(media_id)))
