"""Імпорт медіа з Wikimedia Commons за посиланням (`POST /media/import/commons`).

Сервер сам питає API Commons (`action=query&prop=imageinfo`) про файл: URL, розмір, тип і
метадані ліцензії. Приймаються лише вільні ліцензії: суспільне надбання, CC0, CC BY і CC BY-SA
будь-якої версії (без NC/ND); інакше 422 `LICENSE_NOT_ALLOWED`. Підпис автора й ліцензії
(`MediaAsset.attribution`) і сторінка файла (`source_url`) зберігаються з медіа й ідуть у
маніфест пакета, щоб учень бачив авторство.

- Зображення (JPEG, PNG, WebP, а також SVG і TIFF — як PNG/JPEG-мініатюра Commons) — мініатюра
  ширини 1280 px (або оригінал, якщо він менший) через звичайний шлях завантаження зображень
  (перевірка сигнатури, WebP, без метаданих).
- Відео (WebM, Ogg, MP4) і GIF-анімація — оригінал (≤ `MEDIA_MAX_VIDEO_SOURCE_BYTES`) і
  стиснення сервером (`kind=video_source`, `services/video.py`).

Захист від SSRF: кожен URL, який запитує сервер (API, файл, кожен редирект), має бути
`https://…wikimedia.org` без порту й облікових даних; редиректи перевіряються вручну. Таймаути
й ліміти розміру — з налаштувань. User-Agent — назва проєкту без контактів людей.

Ідемпотентно за клієнтським `id`: повтор із тим самим файлом (та сама нормалізована назва) —
наявний запис без мережі; інший файл або чужий запис під цим id — 409 `ID_CONFLICT`.
"""

import html
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, unquote

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.storage import MediaStorage
from app.models.lessons import MediaAsset
from app.models.school import User
from app.services import media as media_service
from app.services.idempotency import id_conflict

COMMONS_HOSTS = {"commons.wikimedia.org", "commons.m.wikimedia.org"}
UPLOAD_HOST = "upload.wikimedia.org"
ALLOWED_SUFFIX = ".wikimedia.org"
THUMB_WIDTH = 1280
MAX_REDIRECTS = 3
MAX_ARTIST_CHARS = 200

IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/svg+xml", "image/tiff"}
VIDEO_MIMES = {"video/webm", "video/ogg", "application/ogg", "video/mp4", "image/gif"}

# Вільні ліцензії: значення `License` (машинне) або `LicenseShortName` з extmetadata.
_FREE = re.compile(
    r"^(pd|pd-.+|public[ -]domain|cc0|cc0[ -]1\.0|cc[ -]zero|"
    r"cc[ -]by([ -]sa)?([ -]\d(\.\d)?)?([ -][a-z]{2,3})?)$"
)


def _invalid_url() -> AppError:
    return AppError(
        "INVALID_COMMONS_URL",
        "Expected a Wikimedia Commons file page, an upload.wikimedia.org link or File:Name",
        status_code=422,
    )


def _unavailable() -> AppError:
    return AppError(
        "COMMONS_UNAVAILABLE", "Wikimedia Commons did not respond, try later", status_code=502
    )


def _not_found() -> AppError:
    return AppError("COMMONS_FILE_NOT_FOUND", "File not found on Wikimedia Commons", 404)


def _normalize(name: str) -> str:
    """Назва файла як у MediaWiki: підкреслення — пробіли, без зайвих пробілів, перша літера
    велика."""
    name = re.sub(r"\s+", " ", unquote(name).replace("_", " ")).strip()
    if not name or any(ch in name for ch in "#<>[]|{}/"):
        raise _invalid_url()
    return name[0].upper() + name[1:]


def parse_title(raw: str) -> str:
    """`File:Назва` з посилання на сторінку файла, на upload.wikimedia.org або з назви."""
    raw = raw.strip()
    if re.match(r"^(file|файл):", raw, re.IGNORECASE):
        return "File:" + _normalize(raw.split(":", 1)[1])
    try:
        url = httpx.URL(raw)
    except (httpx.InvalidURL, ValueError) as exc:
        raise _invalid_url() from exc
    if url.scheme != "https":
        raise _invalid_url()
    if url.host in COMMONS_HOSTS:
        title = url.params.get("title")
        if title is None and url.path.startswith("/wiki/"):
            title = url.path.removeprefix("/wiki/")
        if title is None:
            raise _invalid_url()
        title = unquote(title)
        if not re.match(r"^(file|файл):", title, re.IGNORECASE):
            raise _invalid_url()
        return "File:" + _normalize(title.split(":", 1)[1])
    if url.host == UPLOAD_HOST:
        # /wikipedia/commons/a/ab/Name.jpg або /wikipedia/commons/thumb/a/ab/Name.jpg/1280px-…
        parts = [p for p in url.path.split("/") if p]
        if len(parts) < 5 or parts[:2] != ["wikipedia", "commons"]:
            raise _invalid_url()
        rest = parts[3:] if parts[2] == "thumb" else parts[2:]
        if len(rest) < 3:
            raise _invalid_url()
        return "File:" + _normalize(rest[2])
    raise _invalid_url()


def source_url(title: str) -> str:
    return "https://commons.wikimedia.org/wiki/" + quote(title.replace(" ", "_"), safe=":(),'!")


def check_fetch_url(url: str | httpx.URL) -> httpx.URL:
    """Лише https на *.wikimedia.org без порту й облікових даних (захист від SSRF)."""
    try:
        parsed = httpx.URL(url)
    except (httpx.InvalidURL, ValueError) as exc:
        raise _unavailable() from exc
    host = parsed.host or ""
    if (
        parsed.scheme != "https"
        or not host.endswith(ALLOWED_SUFFIX)
        or parsed.port not in (None, 443)
        or parsed.userinfo
    ):
        raise AppError(
            "COMMONS_UNAVAILABLE",
            "Wikimedia Commons returned a link outside wikimedia.org",
            status_code=502,
        )
    return parsed


class _TextOnly(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def strip_html(value: str) -> str:
    parser = _TextOnly()
    parser.feed(value)
    parser.close()
    text = html.unescape("".join(parser.parts))
    return re.sub(r"\s+", " ", text).strip()


def _meta(info: dict[str, Any], name: str) -> str:
    item = (info.get("extmetadata") or {}).get(name) or {}
    value = item.get("value") if isinstance(item, dict) else None
    return strip_html(value) if isinstance(value, str) else ""


def license_name(info: dict[str, Any]) -> str:
    """Коротка назва вільної ліцензії або 422 `LICENSE_NOT_ALLOWED`."""
    short = _meta(info, "LicenseShortName")
    machine = _meta(info, "License")
    candidates = [v.lower() for v in (machine, short) if v]
    if not candidates or not any(_FREE.match(v) for v in candidates):
        raise AppError(
            "LICENSE_NOT_ALLOWED",
            "Only public domain, CC0, CC BY and CC BY-SA files can be imported",
            status_code=422,
            details={"license": short or machine or None},
        )
    return short or machine


def attribution(info: dict[str, Any], license_short: str) -> str:
    artist = _meta(info, "Artist")
    if len(artist) > MAX_ARTIST_CHARS:
        artist = artist[: MAX_ARTIST_CHARS - 1].rstrip() + "…"
    parts = [f"Автор: {artist}"] if artist else []
    return " · ".join([*parts, license_short, "Wikimedia Commons"])


def _client(settings: Settings, transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.commons_http_timeout_s,
        transport=transport,
        follow_redirects=False,
        headers={"User-Agent": settings.commons_user_agent},
    )


@asynccontextmanager
async def _get(
    client: httpx.AsyncClient, url: str | httpx.URL, params: dict[str, str] | None = None
) -> AsyncIterator[httpx.Response]:
    """GET потоком із ручними редиректами: кожен крок перевіряється `check_fetch_url`."""
    target = check_fetch_url(url)
    for _ in range(MAX_REDIRECTS + 1):
        request = client.build_request("GET", target, params=params)
        response = await client.send(request, stream=True)
        if response.is_redirect:
            location = response.headers.get("location", "")
            await response.aclose()
            target = check_fetch_url(response.url.join(location))
            params = None
            continue
        try:
            if response.status_code == 404:
                raise _not_found()
            if response.status_code != 200:
                raise _unavailable()
            yield response
        finally:
            await response.aclose()
        return
    raise _unavailable()


async def fetch_info(client: httpx.AsyncClient, settings: Settings, title: str) -> dict[str, Any]:
    """imageinfo файла з API Commons."""
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
        "prop": "imageinfo",
        "titles": title,
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": str(THUMB_WIDTH),
        "iiextmetadatafilter": "Artist|LicenseShortName|License|UsageTerms",
    }
    async with _get(client, settings.commons_api_url, params) as response:
        body = b""
        async for chunk in response.aiter_bytes():
            body += chunk
            if len(body) > settings.commons_max_api_bytes:
                raise _unavailable()
    try:
        data = httpx.Response(200, content=body).json()
        pages = data["query"]["pages"]
    except (ValueError, KeyError, TypeError) as exc:
        raise _not_found() if isinstance(exc, KeyError) else _unavailable() from exc
    if not pages or pages[0].get("missing") or pages[0].get("invalid"):
        raise _not_found()
    infos = pages[0].get("imageinfo") or []
    if not infos or not isinstance(infos[0], dict):
        raise _not_found()
    return infos[0]


async def import_file(
    session: AsyncSession,
    storage: MediaStorage,
    user: User,
    *,
    media_id: uuid.UUID,
    url: str,
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[MediaAsset, bool]:
    """(медіа, створено). Відео — у стані `processing` (стиснення ставить викликач)."""
    title = parse_title(url)
    page = source_url(title)
    existing = await session.get(MediaAsset, media_id)
    if existing is not None:
        diff = [
            name
            for name, ours, theirs in (
                ("uploaded_by", user.id, existing.uploaded_by),
                ("source_url", page, existing.source_url),
            )
            if ours != theirs
        ]
        if diff:
            raise id_conflict(diff)
        return existing, False
    await session.commit()  # мережа поза транзакцією

    try:
        async with _client(settings, transport) as client:
            info = await fetch_info(client, settings, title)
            mime = str(info.get("mime", "")).lower()
            license_short = license_name(info)
            credit = attribution(info, license_short)
            if mime in IMAGE_MIMES:
                kind = "image"
                file_url = info.get("thumburl") or info.get("url")
            elif mime in VIDEO_MIMES:
                kind = "video_source"
                file_url = info.get("url")
            else:
                raise AppError(
                    "UNSUPPORTED_MEDIA_TYPE",
                    "Only images and videos can be imported",
                    status_code=415,
                    details={"mime_type": mime or None},
                )
            if not isinstance(file_url, str):
                raise _not_found()
            async with _get(client, file_url) as response:
                # Тип мініатюри (SVG → PNG, TIFF → JPEG) — із відповіді; відео — з API.
                content_type = response.headers.get("content-type") if kind == "image" else mime
                length = response.headers.get("content-length")
                return await media_service.upload(
                    session,
                    storage,
                    user,
                    media_id=media_id,
                    kind=kind,
                    content_type=content_type,
                    content_length=int(length) if length and length.isdigit() else None,
                    chunks=response.aiter_bytes(),
                    settings=settings,
                    attribution=credit,
                    source_url=page,
                )
    except httpx.HTTPError as exc:
        raise _unavailable() from exc
