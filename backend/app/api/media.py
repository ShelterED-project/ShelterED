"""Медіафайли уроків: відео, зображення, VTT-субтитри, імпорт з Wikimedia Commons."""

import uuid
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.api.deps import Limiter, Session, SettingsDep, Staff, Storage, Teacher
from app.core.rate_limit import enforce, rule
from app.schemas.errors import ErrorResponse
from app.schemas.lessons import CommonsImport, MediaOut, MediaUpdate
from app.services import commons as commons_service
from app.services import media as service
from app.workers.media import enqueue_process_video
from app.workers.packs import enqueue_rebuild_for_lesson

router = APIRouter(tags=["media"])

ACCESS = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
    404: {"model": ErrorResponse, "description": "Не знайдено"},
}

_BINARY = {"schema": {"type": "string", "format": "binary"}}


@router.put(
    "/media/{media_id}",
    response_model=MediaOut,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "required": True,
            "description": "Сирий вміст файла (не multipart); тип — у Content-Type",
            "content": {
                mime: _BINARY for kinds in service.MEDIA_TYPES.values() for mime in sorted(kinds)
            },
        }
    },
    responses={
        200: {"description": "Повтор того самого файла з тим самим id: наявний запис"},
        **ACCESS,
        409: {"model": ErrorResponse, "description": "ID_CONFLICT: інший файл під цим id"},
        413: {"model": ErrorResponse, "description": "MEDIA_TOO_LARGE"},
        415: {"model": ErrorResponse, "description": "UNSUPPORTED_MEDIA_TYPE"},
        422: {
            "model": ErrorResponse,
            "description": "INVALID_MEDIA (сигнатура, UTF-8, порожній), INVALID_IMAGE (пошкоджене "
            "зображення), IMAGE_TOO_LARGE (забагато пікселів)",
        },
    },
)
async def upload_media(
    media_id: uuid.UUID,
    kind: Annotated[Literal["video", "image", "subtitles", "video_source"], Query()],
    request: Request,
    teacher: Teacher,
    session: Session,
    storage: Storage,
    settings: SettingsDep,
    response: Response,
    content_type: Annotated[str | None, Header()] = None,
    content_length: Annotated[int | None, Header()] = None,
) -> MediaOut:
    """Вчитель завантажує файл потоком. `id` генерує клієнт; повтор ідемпотентний.

    Дозволено: відео `video/mp4`, `video/webm` (≤ 30 МБ); зображення `image/jpeg`, `image/png`,
    `image/webp` (≤ 2 МБ); субтитри `text/vtt` у UTF-8 (≤ 200 КБ). Вміст перевіряється за
    сигнатурою. Зображення зберігаються як WebP (довша сторона ≤ 1280 px, без EXIF/GPS), якщо
    так менше або в оригіналі є метадані: `mime_type`, `size_bytes`, `sha256` і `url` у відповіді
    описують збережений файл. Субтитри до відео прив'язуються через `PATCH /media/{id}`; без них
    урок публікується з попередженням `video_subtitles`.

    `kind=video_source` — оригінал відео, який стисне сервер (для браузерів без WebCodecs):
    `video/mp4`, `video/webm`, `video/quicktime`, `video/ogg`, `image/gif` (≤ 300 МБ). Запис
    створюється як `kind: "video"` з `processing_status: "processing"`; стан видно в
    `GET /media/{id}` і в картці уроку (`ready` — стиснуте MP4 ≤ 30 МБ, `failed` — причина в
    `processing_error`: `too_large`, `invalid_video`, `timeout`, `source_missing`). Картку з таким
    відео можна створити одразу, але урок не опублікується, доки відео не `ready`.
    """
    media, created = await service.upload(
        session,
        storage,
        teacher,
        media_id=media_id,
        kind=kind,
        content_type=content_type,
        content_length=content_length,
        chunks=request.stream(),
        settings=settings,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    if media.processing_status == "processing":
        # І на повторі: задача ідемпотентна, а загублена постановка так відновлюється.
        await enqueue_process_video(media.id)
    return service.media_out(media, storage)


def get_commons_transport() -> httpx.AsyncBaseTransport | None:
    """Транспорт HTTP-клієнта до Commons; у тестах підміняється (без справжньої мережі)."""
    return None


@router.post(
    "/media/import/commons",
    response_model=MediaOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Повтор із тим самим файлом під тим самим id: наявний запис"},
        401: ACCESS[401],
        403: ACCESS[403],
        404: {"model": ErrorResponse, "description": "COMMONS_FILE_NOT_FOUND"},
        409: {"model": ErrorResponse, "description": "ID_CONFLICT: інший файл під цим id"},
        413: {"model": ErrorResponse, "description": "MEDIA_TOO_LARGE"},
        415: {"model": ErrorResponse, "description": "UNSUPPORTED_MEDIA_TYPE (аудіо, PDF…)"},
        422: {
            "model": ErrorResponse,
            "description": "INVALID_COMMONS_URL; LICENSE_NOT_ALLOWED (`details.license`); "
            "INVALID_MEDIA, INVALID_IMAGE",
        },
        429: {"model": ErrorResponse, "description": "RATE_LIMITED (з `Retry-After`)"},
        502: {"model": ErrorResponse, "description": "COMMONS_UNAVAILABLE: Commons не відповів"},
    },
)
async def import_from_commons(
    body: CommonsImport,
    teacher: Teacher,
    session: Session,
    storage: Storage,
    settings: SettingsDep,
    limiter: Limiter,
    response: Response,
    transport: Annotated[httpx.AsyncBaseTransport | None, Depends(get_commons_transport)],
) -> MediaOut:
    """Вчитель додає зображення чи відео з Wikimedia Commons за посиланням (сторінка файла,
    `upload.wikimedia.org` або `File:Назва`). Лише суспільне надбання, CC0, CC BY, CC BY-SA;
    підпис автора й ліцензії — в `attribution` (показувати під медіа; він же в маніфесті пакета).

    Зображення (і SVG/TIFF як PNG/JPEG) — мініатюра 1280 px, далі як звичайне завантаження
    (WebP). Відео й GIF стискає сервер: відповідь із `processing_status: "processing"`, як у
    `PUT /media/{id}?kind=video_source`. Ідемпотентно за `id`. Ліміт —
    `RATE_LIMIT_COMMONS_IMPORT` запитів на вчителя за `RATE_LIMIT_COMMONS_IMPORT_WINDOW_S`.
    """
    await enforce(
        limiter,
        [
            rule(
                "commons",
                str(teacher.id),
                settings.rate_limit_commons_import,
                settings.rate_limit_commons_import_window_s,
            )
        ],
    )
    media, created = await commons_service.import_file(
        session,
        storage,
        teacher,
        media_id=body.id,
        url=body.url,
        settings=settings,
        transport=transport,
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    if media.processing_status == "processing":
        await enqueue_process_video(media.id)
    return service.media_out(media, storage)


@router.get("/media/{media_id}", response_model=MediaOut, responses=ACCESS)
async def get_media(
    media_id: uuid.UUID, user: Staff, session: Session, storage: Storage
) -> MediaOut:
    return service.media_out(await service.get_readable_media(session, user, media_id), storage)


@router.patch(
    "/media/{media_id}",
    response_model=MediaOut,
    responses={
        **ACCESS,
        409: {"model": ErrorResponse, "description": "LESSON_PUBLISHED"},
        422: {"model": ErrorResponse, "description": "INVALID_MEDIA"},
    },
)
async def update_media(
    media_id: uuid.UUID, body: MediaUpdate, teacher: Teacher, session: Session, storage: Storage
) -> MediaOut:
    """Прив'язує власні VTT-субтитри до власного відео. Ідемпотентно. Якщо відео вже в
    опублікованих уроках, їхні пакети перезбирає Celery."""
    media, lessons = await service.set_subtitles(session, teacher, media_id, body.subtitles_id)
    for lesson_id in lessons:
        await enqueue_rebuild_for_lesson(lesson_id)
    return service.media_out(media, storage)
