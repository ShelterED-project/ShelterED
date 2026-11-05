"""Класи (адміністрація), вчителі класу, код класу, розклад і прив'язка уроків."""

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import (
    AccessibleClass,
    Admin,
    AdminClass,
    Session,
    SettingsDep,
    Staff,
    StaffClass,
    TeacherClass,
)
from app.core.errors import AppError
from app.schemas.errors import ErrorResponse
from app.schemas.school import (
    AssignmentOut,
    AssignmentRequest,
    ClassCreate,
    ClassOut,
    ClassUpdate,
    CurrentLessonOut,
    JoinCodeRequest,
    OverrideCreate,
    OverrideOut,
    ScheduleDay,
    ScheduleItem,
    ScheduleOut,
    SlotCreate,
    SlotOut,
    SlotUpdate,
)
from app.services import school as service
from app.workers.packs import enqueue_rebuild_class

router = APIRouter(tags=["school"])

R401 = {401: {"model": ErrorResponse, "description": "Не автентифіковано"}}
R403 = {403: {"model": ErrorResponse, "description": "Недостатньо прав"}}
R404 = {404: {"model": ErrorResponse, "description": "Не знайдено"}}
R409 = {409: {"model": ErrorResponse, "description": "Конфлікт (ID_CONFLICT та ін.)"}}
R422 = {422: {"model": ErrorResponse, "description": "Невалідні дані"}}
REPEAT = {200: {"description": "Повтор із тим самим id і даними: наявний ресурс"}}
ACCESS = {**R401, **R403, **R404}


def _created(response: Response, created: bool) -> None:
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK


# ---------- класи ----------


@router.get("/classes", response_model=list[ClassOut], responses={**R401, **R403})
async def list_classes(user: Staff, session: Session) -> list[ClassOut]:
    """Адмін — усі класи своєї школи, вчитель — класи, де він веде."""
    return [await service.class_out(session, k) for k in await service.list_classes(session, user)]


@router.post(
    "/classes",
    response_model=ClassOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **R401, **R403, **R409},
)
async def create_class(
    body: ClassCreate, admin: Admin, session: Session, response: Response
) -> ClassOut:
    """Адмін створює клас у своїй школі; код класу генерує сервер. Ідемпотентно за `id`."""
    if admin.school_id is None:
        raise AppError("FORBIDDEN", "Admin is not attached to a school", status_code=403)
    klass, created = await service.create_class(session, admin, body)
    _created(response, created)
    return await service.class_out(session, klass)


@router.get("/classes/{class_id}", response_model=ClassOut, responses=ACCESS)
async def get_class(klass: StaffClass, session: Session) -> ClassOut:
    return await service.class_out(session, klass)


@router.patch("/classes/{class_id}", response_model=ClassOut, responses={**ACCESS, **R409})
async def update_class(body: ClassUpdate, klass: AdminClass, session: Session) -> ClassOut:
    return await service.class_out(session, await service.update_class(session, klass, body))


@router.delete(
    "/classes/{class_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**ACCESS, 409: {"model": ErrorResponse, "description": "CLASS_NOT_EMPTY"}},
)
async def delete_class(klass: AdminClass, session: Session) -> Response:
    """Видаляє клас без учнів (разом із розкладом)."""
    await service.delete_class(session, klass)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/classes/{class_id}/join-code", response_model=ClassOut, responses=ACCESS)
async def regenerate_join_code(
    klass: AdminClass, session: Session, body: JoinCodeRequest | None = None
) -> ClassOut:
    """Новий код класу для входу учнів; старий одразу перестає діяти.
    Наявні учні входять і далі (код потрібен лише для першого входу)."""
    days = body.expires_in_days if body else None
    return await service.class_out(
        session, await service.regenerate_join_code(session, klass, days)
    )


@router.put(
    "/classes/{class_id}/teachers/{teacher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ACCESS,
)
async def assign_teacher(klass: AdminClass, teacher_id: uuid.UUID, session: Session) -> Response:
    """Призначає вчителя своєї школи на клас. Ідемпотентно."""
    await service.assign_teacher(session, klass, teacher_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/classes/{class_id}/teachers/{teacher_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ACCESS,
)
async def unassign_teacher(klass: AdminClass, teacher_id: uuid.UUID, session: Session) -> Response:
    """Знімає вчителя з класу. Ідемпотентно."""
    await service.unassign_teacher(session, klass, teacher_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- розклад: слоти й перевизначення (пише адміністрація) ----------


@router.get("/classes/{class_id}/schedule/slots", response_model=list[SlotOut], responses=ACCESS)
async def list_slots(klass: AccessibleClass, session: Session) -> list[SlotOut]:
    return [SlotOut.model_validate(s) for s in await service.list_slots(session, klass.id)]


@router.post(
    "/classes/{class_id}/schedule/slots",
    response_model=SlotOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **ACCESS, **R409},
)
async def create_slot(
    body: SlotCreate, klass: AdminClass, session: Session, response: Response
) -> SlotOut:
    """Тижневий слот (час — місцевий час школи). Ідемпотентно за `id`."""
    slot, created = await service.create_slot(session, klass, body)
    await enqueue_rebuild_class(klass.id)
    _created(response, created)
    return SlotOut.model_validate(slot)


@router.patch(
    "/classes/{class_id}/schedule/slots/{slot_id}",
    response_model=SlotOut,
    responses={**ACCESS, **R422},
)
async def update_slot(
    body: SlotUpdate, klass: AdminClass, slot_id: uuid.UUID, session: Session
) -> SlotOut:
    slot = await service.get_slot(session, klass, slot_id)
    slot = await service.update_slot(session, slot, body)
    await enqueue_rebuild_class(klass.id)
    return SlotOut.model_validate(slot)


@router.delete(
    "/classes/{class_id}/schedule/slots/{slot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ACCESS,
)
async def delete_slot(klass: AdminClass, slot_id: uuid.UUID, session: Session) -> Response:
    """Видаляє слот разом із його перевизначеннями й прив'язками уроків.
    Щоб завершити слот без втрати історії, задайте `valid_to`."""
    await service.delete_slot(session, await service.get_slot(session, klass, slot_id))
    await enqueue_rebuild_class(klass.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/classes/{class_id}/schedule/overrides",
    response_model=list[OverrideOut],
    responses=ACCESS,
)
async def list_overrides(
    klass: AccessibleClass,
    session: Session,
    date_from: Annotated[dt.date, Query(alias="from")],
    date_to: Annotated[dt.date, Query(alias="to")],
) -> list[OverrideOut]:
    rows = await service.list_overrides(session, klass.id, date_from, date_to)
    return [OverrideOut.model_validate(o) for o in rows]


@router.post(
    "/classes/{class_id}/schedule/overrides",
    response_model=OverrideOut,
    status_code=status.HTTP_201_CREATED,
    responses={**REPEAT, **ACCESS, **R409, **R422},
)
async def create_override(
    body: OverrideCreate, klass: AdminClass, session: Session, response: Response
) -> OverrideOut:
    """Скасування, заміна чи додатковий урок на дату. Ідемпотентно за `id`;
    на один слот у дату — одне перевизначення (409 OVERRIDE_EXISTS)."""
    override, created = await service.create_override(session, klass, body)
    await enqueue_rebuild_class(klass.id)
    _created(response, created)
    return OverrideOut.model_validate(override)


@router.delete(
    "/classes/{class_id}/schedule/overrides/{override_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ACCESS,
)
async def delete_override(klass: AdminClass, override_id: uuid.UUID, session: Session) -> Response:
    await service.delete_override(session, klass, override_id)
    await enqueue_rebuild_class(klass.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- розклад на дати ----------


def _item(i) -> ScheduleItem:
    return ScheduleItem.model_validate(i, from_attributes=True)


@router.get("/classes/{class_id}/schedule", response_model=ScheduleOut, responses=ACCESS)
async def class_schedule(
    klass: AccessibleClass,
    session: Session,
    date_from: Annotated[
        dt.date | None, Query(alias="from", description="Перший день; за замовчуванням сьогодні")
    ] = None,
    days: Annotated[int, Query(ge=1, le=14)] = 7,
) -> ScheduleOut:
    """Розклад класу на `days` днів (за замовчуванням 7, для «Рюкзака»): слоти з урахуванням
    перевизначень і призначені уроки. Час — місцевий і UTC."""
    tz, result = await service.class_schedule(session, klass, date_from, days)
    return ScheduleOut(
        class_id=klass.id,
        timezone=tz.key,
        days=[ScheduleDay(date=d, items=[_item(i) for i in items]) for d, items in result],
    )


@router.get(
    "/classes/{class_id}/schedule/current", response_model=CurrentLessonOut, responses=ACCESS
)
async def current_lesson(
    klass: AccessibleClass,
    session: Session,
    at: Annotated[
        dt.datetime | None, Query(description="Момент (з часовим поясом); за замовчуванням зараз")
    ] = None,
) -> CurrentLessonOut:
    """Який урок іде в класі зараз (або в момент `at`), за часом школи (Europe/Kyiv)."""
    if at is not None and at.tzinfo is None:
        raise AppError("VALIDATION_ERROR", "at must include a timezone", status_code=422)
    at, day, item = await service.current_lesson(session, klass, at)
    return CurrentLessonOut(class_id=klass.id, at=at, date=day, item=_item(item) if item else None)


# ---------- прив'язка уроку до слота на дату (вчитель класу) ----------


@router.put(
    "/classes/{class_id}/schedule/slots/{slot_id}/lessons/{date}",
    response_model=AssignmentOut,
    responses={
        **ACCESS,
        409: {"model": ErrorResponse, "description": "LESSON_NOT_PUBLISHED / SLOT_CANCELLED"},
        422: {
            "model": ErrorResponse,
            "description": "PACK_DAY_LIMIT_EXCEEDED / INVALID_SCHEDULE",
        },
    },
)
async def assign_lesson(
    body: AssignmentRequest,
    klass: TeacherClass,
    slot_id: uuid.UUID,
    date: dt.date,
    session: Session,
    settings: SettingsDep,
    user: Staff,
) -> AssignmentOut:
    """Ставить опублікований урок у слот на дату (заміна — тим самим PUT). Ідемпотентно.
    Пакет класу на цю дату не може перевищити `PACK_MAX_DAY_BYTES` (50 МБ)."""
    size = await service.assign_lesson(
        session, user, klass, slot_id, date, body.lesson_id, settings
    )
    await enqueue_rebuild_class(klass.id)
    return AssignmentOut(slot_id=slot_id, date=date, lesson_id=body.lesson_id, pack_day_bytes=size)


@router.delete(
    "/classes/{class_id}/schedule/slots/{slot_id}/lessons/{date}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=ACCESS,
)
async def unassign_lesson(
    klass: TeacherClass, slot_id: uuid.UUID, date: dt.date, session: Session
) -> Response:
    await service.unassign_lesson(session, klass, slot_id, date)
    await enqueue_rebuild_class(klass.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
