"""Класи, вчителі класу, код класу, розклад і прив'язка уроків до слотів."""

import datetime as dt
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import new_link_code
from app.models.lessons import Lesson
from app.models.school import (
    ClassMembership,
    LessonAssignment,
    ScheduleOverride,
    ScheduleSlot,
    School,
    SchoolClass,
    User,
)
from app.schemas.school import (
    ClassCreate,
    ClassOut,
    ClassUpdate,
    OverrideCreate,
    SlotCreate,
    SlotUpdate,
)
from app.services import lessons as lessons_service
from app.services import schedule
from app.services.idempotency import insert_or_get, integrity_errors


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _not_found(what: str) -> AppError:
    return AppError("NOT_FOUND", f"{what} not found", status_code=404)


def _invalid_schedule(message: str) -> AppError:
    return AppError("INVALID_SCHEDULE", message, status_code=422)


_CLASS_NAME_TAKEN = AppError(
    "CLASS_NAME_TAKEN", "Class with this name already exists this year", status_code=409
)


# ---------- класи ----------


async def teacher_ids(session: AsyncSession, class_id: uuid.UUID) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(ClassMembership.user_id)
        .where(ClassMembership.class_id == class_id, ClassMembership.member_role == "teacher")
        .order_by(ClassMembership.joined_at, ClassMembership.user_id)
    )
    return list(rows)


async def class_out(session: AsyncSession, klass: SchoolClass) -> ClassOut:
    out = ClassOut.model_validate(klass)
    out.teacher_ids = await teacher_ids(session, klass.id)
    return out


async def list_classes(session: AsyncSession, user: User) -> list[SchoolClass]:
    """Адмін — усі класи своєї школи, вчитель — ті, де він веде."""
    query = select(SchoolClass).order_by(SchoolClass.academic_year, SchoolClass.name)
    if user.role == "admin":
        query = query.where(SchoolClass.school_id == user.school_id)
    else:
        query = query.join(ClassMembership, ClassMembership.class_id == SchoolClass.id).where(
            ClassMembership.user_id == user.id, ClassMembership.member_role == "teacher"
        )
    return list(await session.scalars(query))


async def _unique_join_code(session: AsyncSession) -> str:
    # 31^8 комбінацій: збіг майже неможливий, але перевіряємо.
    for _ in range(5):
        code = new_link_code()
        if (
            await session.scalar(select(SchoolClass.id).where(SchoolClass.join_code == code))
            is None
        ):
            return code
    raise AppError("INTERNAL_ERROR", "Could not generate a unique class code", status_code=500)


async def create_class(
    session: AsyncSession, admin: User, body: ClassCreate
) -> tuple[SchoolClass, bool]:
    values = {
        "id": body.id,
        "school_id": admin.school_id,
        "name": body.name,
        "grade": body.grade,
        "academic_year": body.academic_year,
        "join_code": await _unique_join_code(session),
    }
    klass, created = await insert_or_get(
        session,
        SchoolClass,
        values,
        compare=["school_id", "name", "grade", "academic_year"],
        constraint_errors={"uq_school_class_school_year_name": _CLASS_NAME_TAKEN},
    )
    await session.commit()
    return klass, created


async def update_class(session: AsyncSession, klass: SchoolClass, body: ClassUpdate) -> SchoolClass:
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        if value is None:
            raise AppError("VALIDATION_ERROR", f"{field} cannot be null", status_code=422)
    async with integrity_errors(session, {"uq_school_class_school_year_name": _CLASS_NAME_TAKEN}):
        for field, value in data.items():
            setattr(klass, field, value)
    await session.commit()
    return klass


async def delete_class(session: AsyncSession, klass: SchoolClass) -> None:
    """Видаляє лише клас без учнів: інакше CASCADE зніс би перекличку й пакети класу."""
    has_students = await session.scalar(
        select(ClassMembership.user_id)
        .where(ClassMembership.class_id == klass.id, ClassMembership.member_role == "student")
        .limit(1)
    )
    if has_students is not None:
        raise AppError("CLASS_NOT_EMPTY", "Class has students", status_code=409)
    await session.delete(klass)
    await session.commit()


async def regenerate_join_code(
    session: AsyncSession, klass: SchoolClass, expires_in_days: int | None
) -> SchoolClass:
    code = await _unique_join_code(session)
    collision = AppError("CONFLICT", "Class code collision, retry", status_code=409)
    async with integrity_errors(session, {"uq_school_class_join_code": collision}):
        klass.join_code = code
        klass.join_code_expires_at = (
            _now() + dt.timedelta(days=expires_in_days) if expires_in_days else None
        )
    await session.commit()
    return klass


async def list_school_users(
    session: AsyncSession, school_id: uuid.UUID, role: str | None, limit: int, offset: int
) -> list[User]:
    """Активні користувачі школи (для вибору вчителя на клас), за прізвищем та ім'ям."""
    query = (
        select(User)
        .where(User.school_id == school_id, User.is_active.is_(True))
        .order_by(User.last_name.nulls_last(), User.display_name, User.id)
        .limit(limit)
        .offset(offset)
    )
    if role is not None:
        query = query.where(User.role == role)
    return list(await session.scalars(query))


async def assign_teacher(session: AsyncSession, klass: SchoolClass, teacher_id: uuid.UUID) -> None:
    """Ідемпотентно: повторне призначення нічого не змінює."""
    teacher = await session.get(User, teacher_id)
    if (
        teacher is None
        or teacher.role != "teacher"
        or teacher.school_id != klass.school_id
        or not teacher.is_active
    ):
        raise _not_found("Teacher")
    if await session.get(ClassMembership, (klass.id, teacher.id)) is None:
        session.add(ClassMembership(class_id=klass.id, user_id=teacher.id, member_role="teacher"))
    await session.commit()


async def unassign_teacher(
    session: AsyncSession, klass: SchoolClass, teacher_id: uuid.UUID
) -> None:
    await session.execute(
        delete(ClassMembership).where(
            ClassMembership.class_id == klass.id,
            ClassMembership.user_id == teacher_id,
            ClassMembership.member_role == "teacher",
        )
    )
    await session.commit()


# ---------- розклад: слоти й перевизначення ----------


async def school_tz(session: AsyncSession, school_id: uuid.UUID | None) -> ZoneInfo:
    """Пояс школи; без школи чи з невідомою назвою поясу — Europe/Kyiv."""
    school = await session.get(School, school_id) if school_id is not None else None
    try:
        return ZoneInfo(school.timezone if school else schedule.DEFAULT_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(schedule.DEFAULT_TZ)


async def list_slots(session: AsyncSession, class_id: uuid.UUID) -> list[ScheduleSlot]:
    return list(
        await session.scalars(
            select(ScheduleSlot)
            .where(ScheduleSlot.class_id == class_id)
            .order_by(ScheduleSlot.weekday, ScheduleSlot.starts_at, ScheduleSlot.id)
        )
    )


async def get_slot(session: AsyncSession, klass: SchoolClass, slot_id: uuid.UUID) -> ScheduleSlot:
    slot = await session.get(ScheduleSlot, slot_id)
    if slot is None or slot.class_id != klass.id:
        raise _not_found("Slot")
    return slot


async def create_slot(
    session: AsyncSession, klass: SchoolClass, body: SlotCreate
) -> tuple[ScheduleSlot, bool]:
    await lessons_service.check_subject(session, body.subject_id, klass.school_id)
    slot, created = await insert_or_get(
        session, ScheduleSlot, {"class_id": klass.id, **body.model_dump()}
    )
    await session.commit()
    return slot, created


async def update_slot(session: AsyncSession, slot: ScheduleSlot, body: SlotUpdate) -> ScheduleSlot:
    data = body.model_dump(exclude_unset=True)
    for field in ("subject_id", "weekday", "starts_at", "ends_at", "valid_from"):
        if field in data and data[field] is None:
            raise _invalid_schedule(f"{field} cannot be null")
    merged = {
        c: data.get(c, getattr(slot, c))
        for c in ("subject_id", "weekday", "starts_at", "ends_at", "valid_from", "valid_to")
    }
    try:
        SlotCreate(id=slot.id, **merged)
    except ValueError as exc:
        raise _invalid_schedule(str(exc).splitlines()[-1].strip()) from exc
    if "subject_id" in data:
        klass = await session.get(SchoolClass, slot.class_id)
        await lessons_service.check_subject(session, data["subject_id"], klass.school_id)
    for field, value in data.items():
        setattr(slot, field, value)
    await session.commit()
    return slot


async def delete_slot(session: AsyncSession, slot: ScheduleSlot) -> None:
    # Перевизначення слота без самого слота не мають сенсу; прив'язки уроків — CASCADE.
    await session.execute(delete(ScheduleOverride).where(ScheduleOverride.slot_id == slot.id))
    await session.delete(slot)
    await session.commit()


async def list_overrides(
    session: AsyncSession, class_id: uuid.UUID, date_from: dt.date, date_to: dt.date
) -> list[ScheduleOverride]:
    return list(
        await session.scalars(
            select(ScheduleOverride)
            .where(
                ScheduleOverride.class_id == class_id,
                ScheduleOverride.date >= date_from,
                ScheduleOverride.date <= date_to,
            )
            .order_by(ScheduleOverride.date, ScheduleOverride.starts_at, ScheduleOverride.id)
        )
    )


async def create_override(
    session: AsyncSession, klass: SchoolClass, body: OverrideCreate
) -> tuple[ScheduleOverride, bool]:
    if body.slot_id is not None:
        slot = await get_slot(session, klass, body.slot_id)
        if not schedule.slot_active_on(_slot_data(slot), body.date):
            raise _invalid_schedule("Slot does not take place on this date")
    if body.subject_id is not None:
        await lessons_service.check_subject(session, body.subject_id, klass.school_id)
    override, created = await insert_or_get(
        session,
        ScheduleOverride,
        {"class_id": klass.id, **body.model_dump()},
        constraint_errors={
            "uq_schedule_override_slot_date": AppError(
                "OVERRIDE_EXISTS",
                "This slot already has an override on this date",
                status_code=409,
            )
        },
    )
    await session.commit()
    return override, created


async def delete_override(
    session: AsyncSession, klass: SchoolClass, override_id: uuid.UUID
) -> None:
    """Ідемпотентно: відсутнє перевизначення — теж 204."""
    await session.execute(
        delete(ScheduleOverride).where(
            ScheduleOverride.id == override_id, ScheduleOverride.class_id == klass.id
        )
    )
    await session.commit()


# ---------- розклад на дати й «який урок зараз» ----------


def _slot_data(s: ScheduleSlot) -> schedule.SlotData:
    return schedule.SlotData(
        id=s.id,
        subject_id=s.subject_id,
        weekday=s.weekday,
        starts_at=s.starts_at,
        ends_at=s.ends_at,
        valid_from=s.valid_from,
        valid_to=s.valid_to,
    )


def _override_data(o: ScheduleOverride) -> schedule.OverrideData:
    return schedule.OverrideData(
        id=o.id,
        date=o.date,
        kind=o.kind,  # type: ignore[arg-type]
        slot_id=o.slot_id,
        subject_id=o.subject_id,
        starts_at=o.starts_at,
        ends_at=o.ends_at,
    )


async def _schedule_inputs(
    session: AsyncSession, class_id: uuid.UUID, date_from: dt.date, date_to: dt.date
):
    slots = [_slot_data(s) for s in await list_slots(session, class_id)]
    overrides = [
        _override_data(o) for o in await list_overrides(session, class_id, date_from, date_to)
    ]
    rows = await session.execute(
        select(LessonAssignment.slot_id, LessonAssignment.date, LessonAssignment.lesson_id)
        .join(ScheduleSlot, ScheduleSlot.id == LessonAssignment.slot_id)
        .where(
            ScheduleSlot.class_id == class_id,
            LessonAssignment.date >= date_from,
            LessonAssignment.date <= date_to,
        )
    )
    assignments = {(r.slot_id, r.date): r.lesson_id for r in rows}
    return slots, overrides, assignments


async def class_schedule(
    session: AsyncSession, klass: SchoolClass, date_from: dt.date | None, days: int
) -> tuple[ZoneInfo, list[tuple[dt.date, list[schedule.ResolvedItem]]]]:
    tz = await school_tz(session, klass.school_id)
    start = date_from or schedule.local_date(_now(), tz)
    end = start + dt.timedelta(days=days - 1)
    slots, overrides, assignments = await _schedule_inputs(session, klass.id, start, end)
    result = []
    for n in range(days):
        day = start + dt.timedelta(days=n)
        result.append((day, schedule.resolve_day(day, slots, overrides, assignments, tz)))
    return tz, result


async def day_lesson_ids(
    session: AsyncSession,
    klass: SchoolClass,
    day: dt.date,
    *,
    exclude_slot_id: uuid.UUID | None = None,
) -> set[uuid.UUID]:
    """Уроки, що справді стоять у розкладі класу на дату: прив'язки до скасованих слотів і до
    слотів, які цього дня не діють (інший день тижня, поза дійсністю), не рахуються."""
    _, days = await class_schedule(session, klass, day, 1)
    return {
        i.lesson_id
        for i in days[0][1]
        if i.lesson_id is not None and (exclude_slot_id is None or i.slot_id != exclude_slot_id)
    }


async def current_lesson(
    session: AsyncSession, klass: SchoolClass, at: dt.datetime | None = None
) -> tuple[dt.datetime, dt.date, schedule.ResolvedItem | None]:
    """Який урок іде в класі в момент `at` (за замовчуванням зараз). Для B7 (тривоги)."""
    at = at or _now()
    tz = await school_tz(session, klass.school_id)
    day = schedule.local_date(at, tz)
    slots, overrides, assignments = await _schedule_inputs(session, klass.id, day, day)
    return at, day, schedule.current_item(at, slots, overrides, assignments, tz)


# ---------- прив'язка уроку до слота на дату ----------


async def assign_lesson(
    session: AsyncSession,
    teacher: User,
    klass: SchoolClass,
    slot_id: uuid.UUID,
    day: dt.date,
    lesson_id: uuid.UUID,
    settings: Settings,
) -> int:
    """PUT-семантика: ставить (або замінює) урок у слоті на дату. Повертає розмір пакета дня."""
    slot = await get_slot(session, klass, slot_id)
    if not schedule.slot_active_on(_slot_data(slot), day):
        raise _invalid_schedule("Slot does not take place on this date")
    cancelled = await session.scalar(
        select(ScheduleOverride.id).where(
            ScheduleOverride.slot_id == slot.id,
            ScheduleOverride.date == day,
            ScheduleOverride.kind == "cancel",
        )
    )
    if cancelled is not None:
        raise AppError("SLOT_CANCELLED", "Slot is cancelled on this date", status_code=409)
    lesson = await session.get(Lesson, lesson_id)
    author = await session.get(User, lesson.author_id) if lesson else None
    if lesson is None or author is None or author.school_id != teacher.school_id:
        raise _not_found("Lesson")
    if lesson.status != "published":
        raise AppError(
            "LESSON_NOT_PUBLISHED", "Only published lessons can be scheduled", status_code=409
        )

    # Серіалізуємо прив'язки класу, щоб дві паралельні не перевищили ліміт дня разом.
    await session.scalar(
        select(SchoolClass.id).where(SchoolClass.id == klass.id).with_for_update(key_share=True)
    )
    others = await day_lesson_ids(session, klass, day, exclude_slot_id=slot.id)
    size = await lessons_service.pack_size(session, {*others, lesson.id})
    if size > settings.pack_max_day_bytes:
        raise AppError(
            "PACK_DAY_LIMIT_EXCEEDED",
            "Class pack for this day would exceed the size limit",
            status_code=422,
            details={"size_bytes": size, "limit_bytes": settings.pack_max_day_bytes},
        )
    row = await session.get(LessonAssignment, (slot.id, day))
    if row is None:
        session.add(LessonAssignment(slot_id=slot.id, date=day, lesson_id=lesson.id))
    else:
        row.lesson_id = lesson.id
    await session.commit()
    return size


async def unassign_lesson(
    session: AsyncSession, klass: SchoolClass, slot_id: uuid.UUID, day: dt.date
) -> None:
    slot = await get_slot(session, klass, slot_id)
    await session.execute(
        delete(LessonAssignment).where(
            LessonAssignment.slot_id == slot.id, LessonAssignment.date == day
        )
    )
    await session.commit()
