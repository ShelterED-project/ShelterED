"""Видалення даних учня на запит батьків або школи (B15.5).

Підтвердження видаляє рядок `app_user` учня; решту прибирають FK `ON DELETE CASCADE`:
членство в класах, прив'язки батьків і коди прив'язки, refresh-токени й коди авторизації,
push-підписки, журнал подій `sync_event` (з ним спроби тестів), прогрес модулів, статуси
переклички, «Як ти зараз?» (відповіді й журнал переглядів), агрегати учня. Агрегати класів
після цього перераховуються задачею (`stats.recompute_class`). Підтверджений запит
(без персональних даних) лишається назавжди як запис журналу видалень.
"""

import datetime as dt
import hashlib
import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.privacy import DataDeletionRequest
from app.models.school import ClassMembership, ParentChild, User
from app.schemas.privacy import DeletionRequestCreate, DeletionRequestOut
from app.services.idempotency import id_conflict, integrity_errors

logger = logging.getLogger(__name__)


def student_hash(student_id: uuid.UUID) -> str:
    """Псевдонім учня в запиті й журналі після видалення."""
    return hashlib.sha256(f"student:{student_id}".encode()).hexdigest()


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


async def to_out_many(
    session: AsyncSession, reqs: list[DataDeletionRequest]
) -> list[DeletionRequestOut]:
    """Імена учнів — одним запитом. Інших користувачів (автор, хто вирішив) не розкриваємо:
    лише роль автора."""
    ids = {r.student_id for r in reqs if r.student_id is not None}
    names: dict[uuid.UUID, str] = {}
    if ids:
        rows = await session.execute(
            select(User.id, User.display_name, User.last_name).where(User.id.in_(ids))
        )
        names = {uid: " ".join(p for p in (first, last) if p) for uid, first, last in rows}
    return [
        DeletionRequestOut(
            id=req.id,
            student_id=req.student_id,
            student_name=names.get(req.student_id) if req.student_id else None,
            status=req.status,  # type: ignore[arg-type]
            reason=req.reason,  # type: ignore[arg-type]
            requested_by_role=req.requested_by_role,  # type: ignore[arg-type]
            created_at=req.created_at,
            decided_at=req.decided_at,
        )
        for req in reqs
    ]


async def to_out(session: AsyncSession, req: DataDeletionRequest) -> DeletionRequestOut:
    return (await to_out_many(session, [req]))[0]


def _check_repeat(req: DataDeletionRequest, user: User, hashed: str, reason: str | None) -> None:
    diff = [
        name
        for name, ok in (
            ("student_id", req.student_hash == hashed),
            ("requested_by", req.requested_by == user.id),
            ("reason", req.reason == reason),
        )
        if not ok
    ]
    if diff:
        raise id_conflict(diff)


async def repeat_of(
    session: AsyncSession, user: User, student_id: uuid.UUID, body: DeletionRequestCreate
) -> DataDeletionRequest | None:
    """Повтор уже створеного запиту з тим самим id (зокрема після видалення учня, коли його
    рядка вже немає) — наявний запит; той самий id з іншими даними — 409 ID_CONFLICT."""
    req = await session.get(DataDeletionRequest, body.id)
    if req is not None:
        _check_repeat(req, user, student_hash(student_id), body.reason)
    return req


async def create_request(
    session: AsyncSession, user: User, student: User, body: DeletionRequestCreate
) -> tuple[DataDeletionRequest, bool]:
    """Новий запит (True) або повтор того самого (False). Доступ перевіряє викликач."""
    if student.school_id is None:
        raise AppError("STUDENT_WITHOUT_SCHOOL", "Student has no school", status_code=409)
    hashed = student_hash(student.id)
    stmt = (
        pg_insert(DataDeletionRequest)
        .values(
            id=body.id,
            student_id=student.id,
            student_hash=hashed,
            school_id=student.school_id,
            requested_by=user.id,
            requested_by_role=user.role,
            reason=body.reason,
        )
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(DataDeletionRequest.id)
    )
    exists_error = AppError(
        "DELETION_REQUEST_EXISTS",
        "Student already has a pending deletion request",
        status_code=409,
    )
    async with integrity_errors(
        session, {"uq_data_deletion_request_student_id_pending": exists_error}
    ):
        inserted = await session.scalar(stmt)
    req = await session.get(DataDeletionRequest, body.id, populate_existing=True)
    assert req is not None
    if inserted is None:
        _check_repeat(req, user, hashed, body.reason)
        return req, False
    await session.commit()
    return req, True


async def get_for_admin(
    session: AsyncSession, admin: User, request_id: uuid.UUID
) -> DataDeletionRequest:
    """Запит для рішення адміністрації: рядок блокується до кінця транзакції."""
    req = await session.scalar(
        select(DataDeletionRequest)
        .where(DataDeletionRequest.id == request_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if req is None:
        raise AppError("NOT_FOUND", "Deletion request not found", status_code=404)
    if admin.school_id is None or req.school_id != admin.school_id:
        raise AppError("FORBIDDEN", "No access to this deletion request", status_code=403)
    return req


def _already_decided(req: DataDeletionRequest) -> AppError:
    return AppError(
        "DELETION_REQUEST_DECIDED",
        f"Deletion request is already {req.status}",
        status_code=409,
        details={"status": req.status},
    )


async def confirm(
    session: AsyncSession, admin: User, request_id: uuid.UUID
) -> tuple[DataDeletionRequest, list[uuid.UUID]]:
    """Видаляє дані учня. Повтор підтвердженого — той самий результат без змін.
    Повертає запит і класи, агрегати яких треба перерахувати (після commit)."""
    req = await get_for_admin(session, admin, request_id)
    if req.status == "confirmed":
        return req, []
    if req.status != "pending":
        raise _already_decided(req)
    class_ids: list[uuid.UUID] = []
    student_id = req.student_id
    if student_id is not None:
        class_ids = list(
            await session.scalars(
                select(ClassMembership.class_id).where(
                    ClassMembership.user_id == student_id,
                    ClassMembership.member_role == "student",
                )
            )
        )
        student = await session.get(User, student_id)
        if student is not None and student.role == "student":
            req.student_id = None
            await session.flush()
            # Решту даних учня прибирає ON DELETE CASCADE у БД.
            await session.delete(student)
    req.status = "confirmed"
    req.decided_at = _now()
    req.decided_by = admin.id
    await session.commit()
    # Без id учня й імен: лише id запиту.
    logger.info("Student data deleted", extra={"deletion_request_id": str(req.id)})
    return req, class_ids


async def reject(session: AsyncSession, admin: User, request_id: uuid.UUID) -> DataDeletionRequest:
    req = await get_for_admin(session, admin, request_id)
    if req.status == "rejected":
        return req
    if req.status != "pending":
        raise _already_decided(req)
    req.status = "rejected"
    req.decided_at = _now()
    req.decided_by = admin.id
    await session.commit()
    return req


async def list_requests(
    session: AsyncSession, user: User, status: str | None
) -> list[DataDeletionRequest]:
    """Адміністрація — запити своєї школи; батьки — запити щодо своїх дітей (зокрема створені
    другим із батьків чи школою) і власні (після видалення дитини прив'язки вже немає)."""
    stmt = select(DataDeletionRequest).order_by(DataDeletionRequest.created_at.desc())
    if user.role == "admin":
        stmt = stmt.where(DataDeletionRequest.school_id == user.school_id)
    else:
        children = select(ParentChild.child_id).where(ParentChild.parent_id == user.id)
        stmt = stmt.where(
            or_(
                DataDeletionRequest.requested_by == user.id,
                DataDeletionRequest.student_id.in_(children),
            )
        )
    if status is not None:
        stmt = stmt.where(DataDeletionRequest.status == status)
    return list(await session.scalars(stmt.limit(500)))
