"""Стиснення відео на сервері (ffmpeg) — запасний шлях для браузерів без WebCodecs і для
відео з Wikimedia Commons.

Оригінал (`MediaAsset.processing_status = 'processing'`, `storage_key` — `video_source/…`)
перекодовується в MP4: H.264 main, не більше 720p (орієнтація й пропорції зберігаються, сторони
парні), CRF 28 з обмеженням бітрейту, AAC 96 кбіт/с (голос вчителя лишається), `+faststart`
(відео починає грати до повного завантаження), без метаданих (GPS із телефона).

Успіх: готовий файл записується під новим ключем `video/…`, рядки з цим оригіналом (і копії
уроків, що посилаються на той самий файл) отримують новий `storage_key`, розмір, sha256, тип,
тривалість і `ready`; оригінал видаляється. Результат більший за `MEDIA_MAX_VIDEO_BYTES` —
`failed` (`too_large`), нечитабельне відео — `failed` (`invalid_video`), довше за
`MEDIA_VIDEO_PROCESS_TIMEOUT_S` — `failed` (`timeout`). Оригінал після `failed` теж видаляється.

Ідемпотентно: запис не в стані `processing` (уже готовий, провалений чи видалений) — нічого
не робить. Транзакція не тримається під час ffmpeg (хвилини), тож два паралельні запуски можуть
обидва стиснути файл: зарахується перший (умовний UPDATE за станом і ключем оригіналу), другий
прибере свою копію.
"""

import hashlib
import logging
import re
import secrets
import subprocess
import tempfile
import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import anyio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.storage import MediaStorage
from app.models.lessons import MediaAsset

logger = logging.getLogger(__name__)

# Причини `failed` (`MediaAsset.processing_error`): клієнт показує вчителю зрозумілий текст.
TOO_LARGE = "too_large"
INVALID_VIDEO = "invalid_video"
TIMEOUT = "timeout"
SOURCE_MISSING = "source_missing"

# Рамка 1280×720 для горизонтального відео, 720×1280 — для вертикального; менше не збільшуємо.
_SCALE = (
    "scale='min(iw,if(gte(iw,ih),1280,720))':'min(ih,if(gte(iw,ih),720,1280))'"
    ":force_original_aspect_ratio=decrease:force_divisible_by=2"
)
_DURATION = re.compile(rb"Duration: (\d+):(\d{2}):(\d{2}(?:\.\d+)?)")


class VideoProcessingError(Exception):
    """ffmpeg не зміг перекодувати файл; `reason` — одна з причин вище."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def ffmpeg_args(settings: Settings, source: Path, target: Path) -> list[str]:
    return [
        settings.ffmpeg_path,
        "-nostdin",
        "-hide_banner",
        "-y",
        "-i",
        str(source),
        # Перша відеодоріжка й перша аудіо, якщо є (`?`): GIF і німі ролики — без звуку.
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-sn",
        "-dn",
        "-vf",
        f"{_SCALE},format=yuv420p",
        "-c:v",
        "libx264",
        "-profile:v",
        "main",
        "-preset",
        "medium",
        "-crf",
        "28",
        "-maxrate",
        "1200k",
        "-bufsize",
        "2400k",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(target),
    ]


def parse_duration(stderr: bytes) -> int | None:
    """Тривалість вхідного файла з журналу ffmpeg («Duration: 00:01:35.40»), секунди."""
    match = _DURATION.search(stderr)
    if match is None:
        return None
    hours, minutes, seconds = match.groups()
    return round(int(hours) * 3600 + int(minutes) * 60 + float(seconds))


def run_ffmpeg(settings: Settings, source: Path, target: Path) -> int | None:
    """Стискає `source` у `target`; повертає тривалість (с). Блокуючий виклик — у потоці.
    Відсутній ffmpeg (FileNotFoundError) — помилка конфігурації: летить далі, задача
    повториться, а запис лишається `processing`."""
    try:
        result = subprocess.run(
            ffmpeg_args(settings, source, target),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=settings.media_video_process_timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoProcessingError(TIMEOUT) from exc
    if result.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        # Кінець журналу ffmpeg — для діагностики; там лише технічні дані файла.
        logger.warning(
            "ffmpeg failed (exit %s): %s",
            result.returncode,
            result.stderr[-500:].decode(errors="replace"),
        )
        raise VideoProcessingError(INVALID_VIDEO)
    return parse_duration(result.stderr)


async def _read_file(path: Path, sha: "hashlib._Hash") -> AsyncIterator[bytes]:
    async with await anyio.open_file(path, "rb") as f:
        while chunk := await f.read(1024 * 1024):
            sha.update(chunk)
            yield chunk


async def _finish(session: AsyncSession, source_key: str, values: dict) -> bool:
    """Умовно оновлює всі записи з цим оригіналом; False — інший запуск уже встиг."""
    result = await session.execute(
        update(MediaAsset)
        .where(MediaAsset.storage_key == source_key, MediaAsset.processing_status == "processing")
        .values(**values)
    )
    await session.commit()
    return bool(result.rowcount)  # type: ignore[attr-defined]


async def _fail(session: AsyncSession, storage: MediaStorage, source_key: str, reason: str) -> str:
    if await _finish(
        session, source_key, {"processing_status": "failed", "processing_error": reason}
    ):
        await storage.delete(source_key)
    return "failed"


async def process_video(
    session: AsyncSession, storage: MediaStorage, settings: Settings, media_id: uuid.UUID
) -> str:
    """Стискає відео запису. Повертає підсумковий стан (`ready`, `failed`) або `skipped`."""
    media = await session.get(MediaAsset, media_id)
    if media is None or media.processing_status != "processing":
        return "skipped"
    source_key = media.storage_key
    # Транзакцію закриваємо: ffmpeg працює хвилинами (idle_in_transaction_session_timeout).
    await session.commit()

    source = storage.local_path(source_key)
    if not await anyio.Path(source).is_file():
        return await _fail(session, storage, source_key, SOURCE_MISSING)

    key = f"video/{media_id}-{secrets.token_hex(4)}.mp4"
    with tempfile.TemporaryDirectory(prefix="sheltered-video-") as tmp:
        target = Path(tmp) / "out.mp4"
        try:
            duration = await anyio.to_thread.run_sync(run_ffmpeg, settings, source, target)
        except VideoProcessingError as exc:
            return await _fail(session, storage, source_key, exc.reason)
        size = target.stat().st_size
        if size > settings.media_max_video_bytes:
            logger.info(
                "Compressed video %s is %d bytes, over the %d limit",
                media_id,
                size,
                settings.media_max_video_bytes,
            )
            return await _fail(session, storage, source_key, TOO_LARGE)
        sha = hashlib.sha256()
        await storage.save(key, _read_file(target, sha))

    done = False
    try:
        done = await _finish(
            session,
            source_key,
            {
                "storage_key": key,
                "mime_type": "video/mp4",
                "size_bytes": size,
                "sha256": sha.hexdigest(),
                "duration_s": duration,
                "processing_status": "ready",
                "processing_error": None,
            },
        )
    finally:
        if not done:  # інший запуск уже завершив запис або помилка БД
            await storage.delete(key)
    await storage.delete(source_key)
    return "ready"
