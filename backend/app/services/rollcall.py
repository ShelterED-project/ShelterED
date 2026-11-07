"""Перекличка (B12). Статуси учні надсилають подіями `rollcall_status` (B9, services/sync.py);
тут — сесії (ручний старт і закриття вчителем) і перегляд для вчителя, учня й батьків.

«Немає відповіді» = рядка `rollcall_status` немає (у відповідях API — `no_response`).
Сесію при тривозі відкриває й закриває services/alerts.py.
"""

import datetime as dt
import uuid

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.alerts import AlertEvent
from app.models.rollcall import RollCallSession, RollCallStatus
from app.models.school import ClassMembership, SchoolClass, User
from app.schemas.rollcall import (
    RollCallCurrentOut,
    RollCallSessionOut,
    RollCallStart,
    RollCallStudentStatus,
    RollCallSummary,
    StudentRollCallOut,
)
from app.services.idempotency import insert_or_get


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _already_open(session_id: uuid.UUID | None = None) -> AppError:
    return AppError(
        "ROLLCALL_ALREADY_OPEN",
        "Another roll call is already open for this class",
        status_code=409,
        details={"session_id": str(session_id)} if session_id else None,
    )


async def _open_session(session: AsyncSession, class_id: uuid.UUID) -> RollCallSession | None:
    return await session.scalar(
        select(RollCallSession).where(
            RollCallSession.class_id == class_id, RollCallSession.closed_at.is_(None)
        )
    )


async def session_view(
    session: AsyncSession, rc: RollCallSession, viewer: User
) -> RollCallSessionOut:
    """Сесія зі статусами: вчитель і адмін бачать увесь клас, учень — лише себе."""
    query = (
        select(User, RollCallStatus)
        .join(
            ClassMembership,
            and_(
                ClassMembership.user_id == User.id,
                ClassMembership.class_id == rc.class_id,
                ClassMembership.member_role == "student",
            ),
        )
        .outerjoin(
            RollCallStatus,
            and_(RollCallStatus.session_id == rc.id, RollCallStatus.student_id == User.id),
        )
        .order_by(User.last_name, User.display_name, User.id)
    )
    if viewer.role == "student":
        query = query.where(User.id == viewer.id)
    students = [
        RollCallStudentStatus(
            student_id=user.id,
            display_name=user.display_name,
            last_name=user.last_name,
            status=status.status if status else "no_response",  # type: ignore[arg-type]
            occurred_at=status.occurred_at if status else None,
            received_at=status.received_at if status else None,
        )
        for user, status in (await session.execute(query)).all()
    ]
    summary = RollCallSummary(
        safe=sum(s.status == "safe" for s in students),
        in_shelter=sum(s.status == "in_shelter" for s in students),
        no_response=sum(s.status == "no_response" for s in students),
    )
    return RollCallSessionOut(
        id=rc.id,
        class_id=rc.class_id,
        alert_event_id=rc.alert_event_id,
        is_drill=rc.is_drill,
        opened_at=rc.opened_at,
        closed_at=rc.closed_at,
        summary=summary,
        students=students,
    )


async def current(session: AsyncSession, viewer: User, klass: SchoolClass) -> RollCallCurrentOut:
    rc = await _open_session(session, klass.id)
    return RollCallCurrentOut(
        class_id=klass.id, session=await session_view(session, rc, viewer) if rc else None
    )


async def _covering_alert_id(
    session: AsyncSession, klass: SchoolClass, is_drill: bool
) -> uuid.UUID | None:
    """Активна тривога того ж типу (справжня / навчальна), що покриває клас: ручна цього класу
    або з API його школи. FOR SHARE: паралельний відбій дочекається commit сесії й закриє її."""
    return await session.scalar(
        select(AlertEvent.id)
        .where(
            AlertEvent.ended_at.is_(None),
            AlertEvent.is_drill == is_drill,
            or_(
                AlertEvent.class_id == klass.id,
                and_(AlertEvent.class_id.is_(None), AlertEvent.school_id == klass.school_id),
            ),
        )
        .order_by(AlertEvent.started_at, AlertEvent.id)
        .limit(1)
        .with_for_update(read=True)
    )


async def start(
    session: AsyncSession, teacher: User, klass: SchoolClass, body: RollCallStart
) -> tuple[RollCallSessionOut, bool]:
    """Ручний старт. Ідемпотентно за `id`: повтор повертає наявну сесію (навіть уже закриту).
    Інша відкрита сесія класу (зокрема від тривоги) — 409 ROLLCALL_ALREADY_OPEN з її id.
    Під час тривоги того ж типу (урок почався, коли тривога вже йшла) сесія належить їй:
    відбій закриває перекличку й шле `all_clear`, як для сесії, відкритої тривогою."""
    existing = await session.get(RollCallSession, body.id)
    alert_id = None
    if existing is None:
        other = await _open_session(session, klass.id)
        if other is not None:
            raise _already_open(other.id)
        alert_id = await _covering_alert_id(session, klass, body.is_drill)
    rc, created = await insert_or_get(
        session,
        RollCallSession,
        {
            "id": body.id,
            "class_id": klass.id,
            "alert_event_id": alert_id,
            "opened_by": teacher.id,
            "is_drill": body.is_drill,
            "opened_at": _now(),
        },
        # Гонка двох різних стартів: друга вставка впирається в «одна відкрита на клас».
        constraint_errors={"uq_rollcall_session_class_id_open": _already_open()},
        compare=["class_id", "is_drill"],
    )
    if created:
        await session.commit()
    return await session_view(session, rc, teacher), created


async def close(
    session: AsyncSession, teacher: User, klass: SchoolClass, session_id: uuid.UUID
) -> RollCallSessionOut:
    """Закриття вчителем. Ідемпотентно: закрита сесія повертається як є. Статуси з
    `occurred_at` до закриття, що прийдуть пізніше, ще приймаються (B9, `session_closed`)."""
    rc = await session.get(RollCallSession, session_id)
    if rc is None or rc.class_id != klass.id:
        raise AppError("NOT_FOUND", "Roll call not found", status_code=404)
    await session.execute(
        update(RollCallSession)
        .where(RollCallSession.id == session_id, RollCallSession.closed_at.is_(None))
        .values(closed_at=_now())
    )
    await session.commit()
    await session.refresh(rc)
    return await session_view(session, rc, teacher)


async def student_current(session: AsyncSession, student: User) -> StudentRollCallOut:
    """Статус учня в відкритій перекличці його класу (найновіша, якщо класів кілька)."""
    classes = select(ClassMembership.class_id).where(
        ClassMembership.user_id == student.id, ClassMembership.member_role == "student"
    )
    rc = await session.scalar(
        select(RollCallSession)
        .where(RollCallSession.class_id.in_(classes), RollCallSession.closed_at.is_(None))
        .order_by(RollCallSession.opened_at.desc(), RollCallSession.id)
        .limit(1)
    )
    if rc is None:
        return StudentRollCallOut(
            student_id=student.id,
            session_id=None,
            is_drill=None,
            opened_at=None,
            status=None,
            occurred_at=None,
            received_at=None,
        )
    status = await session.get(RollCallStatus, (rc.id, student.id))
    return StudentRollCallOut(
        student_id=student.id,
        session_id=rc.id,
        is_drill=rc.is_drill,
        opened_at=rc.opened_at,
        status=status.status if status else "no_response",  # type: ignore[arg-type]
        occurred_at=status.occurred_at if status else None,
        received_at=status.received_at if status else None,
    )
