"""Завантаження медіа (відео, зображення, VTT-субтитри) з перевіркою формату й розміру.

Файл іде потоком: розмір перевіряється на льоту, у пам'яті лише поточний шматок.
Тип перевіряється двічі: заголовок Content-Type і сигнатура (magic bytes) на початку файла.
Ім'я файла від клієнта ніколи не використовується: ключ сховища генерує сервер.

Зображення після прийому перекодовуються у WebP (див. `_to_webp`): довша сторона ≤ 1280 px,
орієнтація з EXIF застосована, метадані (EXIF, GPS, XMP) прибрані — це фото зі школи.

Два хеші в `MediaAsset`:
- `sha256` — хеш збереженого файла, тобто того, що роздається за `url` (його бачить клієнт
  у маніфесті пакета й може звірити завантажене);
- `source_sha256` — хеш файла, який надіслав клієнт. За ним перевіряється ідемпотентність:
  повтор того самого файла під тим самим `media_id` → наявний запис, без повторного перекодування.
Для відео й субтитрів вони однакові.

Дедуплікація: якщо файл з таким самим вмістом (sha256, розмір, тип) уже є у сховищі, новий запис
посилається на його `storage_key`, а щойно записана копія видаляється. Тож один файл може
належати кільком `MediaAsset`: видаляти файл зі сховища можна лише тоді, коли на його
`storage_key` не посилається жоден запис (перевіряти в тій самій транзакції, що й видалення
рядка). Завантаження ніколи не видаляє чужий (спільний) файл — лише власну щойно записану копію.
"""

import codecs
import hashlib
import io
import math
import secrets
import uuid
from collections.abc import AsyncIterable, AsyncIterator

import anyio
from PIL import Image, ImageOps
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


def _bad_image() -> AppError:
    return AppError("INVALID_IMAGE", "Image is corrupt or unsupported", status_code=400)


def _too_many_pixels(limit: int) -> AppError:
    return AppError(
        "IMAGE_TOO_LARGE",
        "Image has too many pixels",
        status_code=400,
        details={"max_pixels": limit},
    )


def _to_webp(data: bytes, max_side: int, quality: int, max_pixels: int) -> bytes | None:
    """WebP-версія зображення або None, якщо краще лишити оригінал.

    Оригінал лишається, лише коли WebP не менший і в оригіналі немає EXIF/XMP: файл із
    метаданими (можливо, GPS) не зберігаємо ніколи. Блокуючий код — викликати в потоці.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            # Розмір з заголовка — до декодування пікселів.
            if width * height > max_pixels:
                raise _too_many_pixels(max_pixels)
            has_metadata = bool(img.getexif()) or any(
                k in img.info for k in ("xmp", "XML:com.adobe.xmp")
            )
            icc_profile = img.info.get("icc_profile")
            scale = min(1.0, max_side / max(width, height))
            # JPEG декодується одразу в зменшеному масштабі (1/2, 1/4, 1/8) — менше пам'яті.
            img.draft("RGB", (math.ceil(width * scale), math.ceil(height * scale)))
            out = ImageOps.exif_transpose(img)
            out.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)  # не збільшує
            out = out.convert("RGBA" if out.has_transparency_data else "RGB")
            buf = io.BytesIO()
            # exif/xmp не передаємо — у WebP вони не потрапляють; ICC лишаємо заради кольорів.
            out.save(buf, "WEBP", quality=quality, icc_profile=icc_profile)
    except Image.DecompressionBombError as exc:
        raise _too_many_pixels(max_pixels) from exc
    except (OSError, ValueError, SyntaxError, EOFError) as exc:  # пошкоджений чи обрізаний файл
        raise _bad_image() from exc
    webp = buf.getvalue()
    if len(webp) >= len(data) and not has_metadata:
        return None
    return webp


async def _once(data: bytes) -> AsyncIterator[bytes]:
    yield data


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
            # mime_type не порівнюємо: збережений файл міг стати WebP, а однаковий вміст
            # (source_sha256) з перевіреною сигнатурою й так означає однаковий тип.
            for name, ours, theirs in (
                ("uploaded_by", user.id, existing.uploaded_by),
                ("kind", kind, existing.kind),
                ("source_sha256", stream.sha.hexdigest(), existing.source_sha256),
            )
            if ours != theirs
        ]
        if diff:
            raise id_conflict(diff)
        return existing, False

    key_base = f"{kind}/{media_id}-{secrets.token_hex(4)}"
    if kind == "image":
        # Зображення ≤ media_max_image_bytes: спершу приймаємо й перевіряємо цілим, потім
        # перекодовуємо в потоці, щоб не блокувати event loop.
        data = b"".join([chunk async for chunk in stream])
        source_sha = stream.sha.hexdigest()
        webp = await anyio.to_thread.run_sync(
            _to_webp,
            data,
            settings.media_image_max_side,
            settings.media_image_webp_quality,
            settings.media_image_max_pixels,
        )
        if webp is not None:
            data, mime = webp, "image/webp"
        key = f"{key_base}.{MEDIA_TYPES[kind][mime]}"
        await storage.save(key, _once(data))
        size, sha = len(data), hashlib.sha256(data).hexdigest()
    else:
        key = f"{key_base}.{MEDIA_TYPES[kind][mime]}"
        await storage.save(key, stream)
        size, sha = stream.size, stream.sha.hexdigest()
        source_sha = sha
    # Спершу пишемо, потім шукаємо дубль: паралельні завантаження однакового вмісту в гіршому
    # разі лишать дві копії, але ніколи не втратять файл.
    shared_key = await session.scalar(
        select(MediaAsset.storage_key)
        .where(
            MediaAsset.sha256 == sha,
            MediaAsset.size_bytes == size,
            MediaAsset.kind == kind,
            MediaAsset.mime_type == mime,
        )
        .limit(1)
    )
    values = {
        "id": media_id,
        "kind": kind,
        "storage_key": shared_key or key,
        "mime_type": mime,
        "size_bytes": size,
        "sha256": sha,
        "source_sha256": source_sha,
        "uploaded_by": user.id,
    }
    keep_new = False
    try:
        media, created = await insert_or_get(
            session,
            MediaAsset,
            values,
            compare=["uploaded_by", "kind", "source_sha256"],
        )
        if created:
            await session.commit()
        keep_new = created and shared_key is None
    finally:
        # Наша копія зайва: помилка, паралельний повтор встиг першим або файл уже був.
        if not keep_new:
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


async def _published_lessons(session: AsyncSession, media_id: uuid.UUID) -> list[uuid.UUID]:
    """Опубліковані уроки, картки яких використовують медіа."""
    rows = await session.scalars(
        select(Lesson.id)
        .join(Module, Module.lesson_id == Lesson.id)
        .join(Card, Card.module_id == Module.id)
        .where(Card.media_asset_id == media_id, Lesson.status == "published")
        .distinct()
        .order_by(Lesson.id)
    )
    return list(rows)


async def set_subtitles(
    session: AsyncSession, user: User, media_id: uuid.UUID, subtitles_id: uuid.UUID | None
) -> tuple[MediaAsset, list[uuid.UUID]]:
    """(медіа, опубліковані уроки з цим відео, якщо субтитри змінились — їхні пакети треба
    перезібрати). Повтор без змін — порожній список."""
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
    elif media.subtitles_id is not None and await _published_lessons(session, media.id):
        # Опублікований урок пройшов перевірку субтитрів — не ламаємо її заднім числом.
        raise AppError("LESSON_PUBLISHED", "Video is used in a published lesson", status_code=409)
    if media.subtitles_id == subtitles_id:
        return media, []
    media.subtitles_id = subtitles_id
    lessons = await _published_lessons(session, media.id)
    await session.commit()
    return media, lessons
