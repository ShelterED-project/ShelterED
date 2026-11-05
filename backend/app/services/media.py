"""Завантаження медіа (відео, зображення, VTT-субтитри) з перевіркою формату й розміру.

Файл іде потоком: розмір перевіряється на льоту, у пам'яті лише поточний шматок.
Тип перевіряється двічі: заголовок Content-Type і сигнатура (magic bytes) на початку файла.
Ім'я файла від клієнта ніколи не використовується: ключ сховища генерує сервер.
"""

import codecs
import hashlib
import secrets
import uuid
from collections.abc import AsyncIterable, AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.storage import MediaStorage
from app.models.lessons import Card, Lesson, MediaAsset, Module
from app.models.school import User
from app.schemas.lessons import MediaOut
from app.services.idempotency import id_conflict, insert_or_get

# kind → дозволені MIME-типи → розширення файла у сховищі.
MEDIA_TYPES: dict[str, dict[str, str]] = {
    "video": {"video/mp4": "mp4", "video/webm": "webm"},
    "image": {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"},
    "subtitles": {"text/vtt": "vtt"},
}
HEAD_BYTES = 16


def max_bytes(kind: str, settings: Settings) -> int:
    return {
        "video": settings.media_max_video_bytes,
        "image": settings.media_max_image_bytes,
        "subtitles": settings.media_max_subtitles_bytes,
    }[kind]


def magic_ok(mime: str, head: bytes) -> bool:
    """Сигнатура файла відповідає заявленому MIME-типу."""
    match mime:
        case "video/mp4":
            return head[4:8] == b"ftyp"
        case "video/webm":
            return head[:4] == b"\x1a\x45\xdf\xa3"
        case "image/jpeg":
            return head[:3] == b"\xff\xd8\xff"
        case "image/png":
            return head[:8] == b"\x89PNG\r\n\x1a\n"
        case "image/webp":
            return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
        case "text/vtt":
            body = head.removeprefix(b"\xef\xbb\xbf")
            return body[:6] == b"WEBVTT" and (len(body) == 6 or body[6:7] in b" \t\r\n")
    return False


def _too_large(limit: int) -> AppError:
    return AppError(
        "MEDIA_TOO_LARGE", "File exceeds the size limit", status_code=413, details={"limit": limit}
    )


def _invalid(message: str) -> AppError:
    return AppError("INVALID_MEDIA", message, status_code=422)


def parse_content_type(kind: str, content_type: str | None) -> str:
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime not in MEDIA_TYPES[kind]:
        raise AppError(
            "UNSUPPORTED_MEDIA_TYPE",
            f"Unsupported content type for {kind}",
            status_code=415,
            details={"allowed": sorted(MEDIA_TYPES[kind])},
        )
    return mime


class _CheckedStream:
    """Пропускає шматки далі, рахуючи розмір і sha256, і перевіряє сигнатуру й ліміт."""

    def __init__(self, chunks: AsyncIterable[bytes], mime: str, limit: int) -> None:
        self.chunks, self.mime, self.limit = chunks, mime, limit
        self.size = 0
        self.sha = hashlib.sha256()
        self._head = b""
        self._checked = False
        self._utf8 = codecs.getincrementaldecoder("utf-8")() if mime == "text/vtt" else None

    def _check_head(self) -> None:
        if not magic_ok(self.mime, self._head):
            raise _invalid("File content does not match its content type")
        self._checked = True

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async for chunk in self.chunks:
            if not chunk:
                continue
            self.size += len(chunk)
            if self.size > self.limit:
                raise _too_large(self.limit)
            if not self._checked:
                self._head += chunk[: HEAD_BYTES - len(self._head)]
                if len(self._head) >= HEAD_BYTES:
                    self._check_head()
            if self._utf8 is not None:
                try:
                    self._utf8.decode(chunk)
                except UnicodeDecodeError as exc:
                    raise _invalid("Subtitles must be UTF-8") from exc
            self.sha.update(chunk)
            yield chunk
        if self.size == 0:
            raise _invalid("Empty file")
        if not self._checked:
            self._check_head()
        if self._utf8 is not None:
            try:
                self._utf8.decode(b"", final=True)
            except UnicodeDecodeError as exc:
                raise _invalid("Subtitles must be UTF-8") from exc


def media_out(media: MediaAsset, storage: MediaStorage) -> MediaOut:
    return MediaOut(
        id=media.id,
        kind=media.kind,  # type: ignore[arg-type]
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        sha256=media.sha256,
        duration_s=media.duration_s,
        subtitles_id=media.subtitles_id,
        url=storage.url(media.storage_key),
    )


async def upload(
    session: AsyncSession,
    storage: MediaStorage,
    user: User,
    *,
    media_id: uuid.UUID,
    kind: str,
    content_type: str | None,
    content_length: int | None,
    chunks: AsyncIterable[bytes],
    settings: Settings,
) -> tuple[MediaAsset, bool]:
    """Ідемпотентно за клієнтським `media_id`: повтор того самого файла повертає наявний запис,
    інший файл під тим самим id — 409."""
    mime = parse_content_type(kind, content_type)
    limit = max_bytes(kind, settings)
    if content_length is not None and content_length > limit:
        raise _too_large(limit)
    stream = _CheckedStream(chunks, mime, limit)

    existing = await session.get(MediaAsset, media_id)
    if existing is not None:
        async for _ in stream:  # лише рахуємо хеш, нічого не пишемо
            pass
        diff = [
            name
            for name, ours, theirs in (
                ("uploaded_by", user.id, existing.uploaded_by),
                ("kind", kind, existing.kind),
                ("mime_type", mime, existing.mime_type),
                ("sha256", stream.sha.hexdigest(), existing.sha256),
            )
            if ours != theirs
        ]
        if diff:
            raise id_conflict(diff)
        return existing, False

    key = f"{kind}/{media_id}-{secrets.token_hex(4)}.{MEDIA_TYPES[kind][mime]}"
    await storage.save(key, stream)
    values = {
        "id": media_id,
        "kind": kind,
        "storage_key": key,
        "mime_type": mime,
        "size_bytes": stream.size,
        "sha256": stream.sha.hexdigest(),
        "uploaded_by": user.id,
    }
    try:
        media, created = await insert_or_get(
            session,
            MediaAsset,
            values,
            compare=["uploaded_by", "kind", "mime_type", "sha256"],
        )
        if created:
            await session.commit()
    except BaseException:
        await storage.delete(key)
        raise
    if not created:  # паралельний повтор встиг першим: наш файл зайвий
        await storage.delete(key)
    return media, created


async def get_readable_media(session: AsyncSession, user: User, media_id: uuid.UUID) -> MediaAsset:
    """Автор файла, а також вчителі й адміністрація його школи."""
    media = await session.get(MediaAsset, media_id)
    if media is None:
        raise AppError("NOT_FOUND", "Media not found", status_code=404)
    if media.uploaded_by == user.id:
        return media
    school_id = await session.scalar(select(User.school_id).where(User.id == media.uploaded_by))
    if user.school_id is not None and school_id == user.school_id:
        return media
    raise AppError("FORBIDDEN", "No access to this media", status_code=403)


async def _in_published_lesson(session: AsyncSession, media_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(Card.id)
        .join(Module, Module.id == Card.module_id)
        .join(Lesson, Lesson.id == Module.lesson_id)
        .where(Card.media_asset_id == media_id, Lesson.status == "published")
        .limit(1)
    )
    return found is not None


async def set_subtitles(
    session: AsyncSession, user: User, media_id: uuid.UUID, subtitles_id: uuid.UUID | None
) -> MediaAsset:
    media = await get_readable_media(session, user, media_id)
    if media.uploaded_by != user.id:
        raise AppError("FORBIDDEN", "Only the uploader can change media", status_code=403)
    if media.kind != "video":
        raise _invalid("Subtitles can be attached only to video")
    if subtitles_id is not None:
        subtitles = await session.get(MediaAsset, subtitles_id)
        if subtitles is None or subtitles.uploaded_by != user.id:
            raise AppError("NOT_FOUND", "Subtitles not found", status_code=404)
        if subtitles.kind != "subtitles":
            raise _invalid("subtitles_id must reference a VTT file")
    elif media.subtitles_id is not None and await _in_published_lesson(session, media.id):
        # Опублікований урок пройшов перевірку субтитрів — не ламаємо її заднім числом.
        raise AppError("LESSON_PUBLISHED", "Video is used in a published lesson", status_code=409)
    media.subtitles_id = subtitles_id
    await session.commit()
    return media
