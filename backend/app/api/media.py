"""Медіафайли уроків: відео, зображення, VTT-субтитри."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query, Request, Response, status

from app.api.deps import Session, SettingsDep, Staff, Storage, Teacher
from app.schemas.errors import ErrorResponse
from app.schemas.lessons import MediaOut, MediaUpdate
from app.services import media as service
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
            "content": {mime: _BINARY for kinds in service.MEDIA_TYPES.values() for mime in kinds},
        }
    },
    responses={
        200: {"description": "Повтор того самого файла з тим самим id: наявний запис"},
        **ACCESS,
        409: {"model": ErrorResponse, "description": "ID_CONFLICT: інший файл під цим id"},
        413: {"model": ErrorResponse, "description": "MEDIA_TOO_LARGE"},
        415: {"model": ErrorResponse, "description": "UNSUPPORTED_MEDIA_TYPE"},
        422: {"model": ErrorResponse, "description": "INVALID_MEDIA (сигнатура, UTF-8, порожній)"},
    },
)
async def upload_media(
    media_id: uuid.UUID,
    kind: Annotated[Literal["video", "image", "subtitles"], Query()],
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
    сигнатурою. Відео без субтитрів не пройде публікацію уроку: прив'яжіть VTT через
    `PATCH /media/{id}`.
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
