"""Видалення даних учня на запит батьків або школи (B15.5)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import Admin, Session, get_accessible_student, require_roles
from app.api.stub import example_of
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.privacy import DeletionRequestCreate, DeletionRequestOut, DeletionStatus
from app.services import privacy as service
from app.workers.stats import enqueue_recompute_class

router = APIRouter(tags=["privacy"])

ParentOrAdmin = Annotated[User, Depends(require_roles("parent", "admin"))]

AUTH = {
    401: {"model": ErrorResponse, "description": "Не автентифіковано"},
    403: {"model": ErrorResponse, "description": "Недостатньо прав"},
}
DECIDE = {
    200: example_of(DeletionRequestOut),
    **AUTH,
    404: {"model": ErrorResponse, "description": "Запит не знайдено"},
    409: {
        "model": ErrorResponse,
        "description": "DELETION_REQUEST_DECIDED: запит уже має інше рішення",
    },
}


@router.post(
    "/students/{student_id}/deletion-requests",
    response_model=DeletionRequestOut,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: example_of(DeletionRequestOut, "Запит створено"),
        200: {"description": "Повтор із тим самим id: наявний запит"},
        **AUTH,
        404: {"model": ErrorResponse, "description": "Учня не знайдено"},
        409: {
            "model": ErrorResponse,
            "description": "DELETION_REQUEST_EXISTS: в учня вже є відкритий запит; "
            "ID_CONFLICT: id зайнятий іншим запитом; STUDENT_WITHOUT_SCHOOL: учень не "
            "прив'язаний до школи (нікому підтвердити запит)",
        },
    },
)
async def create_request(
    student_id: uuid.UUID,
    body: DeletionRequestCreate,
    user: ParentOrAdmin,
    session: Session,
    response: Response,
) -> DeletionRequestOut:
    """Запит на повне видалення даних учня. Створюють батьки цієї дитини або адміністрація
    її школи; виконує адміністрація школи (`/deletion-requests/{id}/confirm`). Відкритий
    запит — один на учня. Ідемпотентно за `id`: повтор — 200 з наявним запитом (і після
    видалення учня)."""
    req = await service.repeat_of(session, user, student_id, body)
    if req is None:
        student = await get_accessible_student(student_id, user, session)
        req, created = await service.create_request(session, user, student, body)
        if not created:
            response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_200_OK
    return await service.to_out(session, req)


@router.get(
    "/deletion-requests",
    response_model=list[DeletionRequestOut],
    responses={200: {"description": "Запити, новіші спершу (до 500)"}, **AUTH},
)
async def list_requests(
    user: ParentOrAdmin,
    session: Session,
    status_filter: Annotated[DeletionStatus | None, Query(alias="status")] = None,
) -> list[DeletionRequestOut]:
    """Адміністрація — запити своєї школи (`?status=pending` — черга на рішення); батьки —
    запити щодо своїх дітей (і створені школою чи другим із батьків) та власні. Автора
    видно лише за роллю (`requested_by_role`)."""
    reqs = await service.list_requests(session, user, status_filter)
    return await service.to_out_many(session, reqs)


@router.post(
    "/deletion-requests/{request_id}/confirm", response_model=DeletionRequestOut, responses=DECIDE
)
async def confirm(request_id: uuid.UUID, admin: Admin, session: Session) -> DeletionRequestOut:
    """Адміністрація школи учня видаляє його дані безповоротно: акаунт і все пов'язане
    (спроби, прогрес, журнал подій, перекличка, «Як ти зараз?», push-підписки, токени,
    прив'язки батьків, агрегати). Підтверджений запит без персональних даних лишається як
    запис журналу видалень.
    Повтор — той самий результат (200); відхилений запит — 409."""
    req, class_ids = await service.confirm(session, admin, request_id)
    for class_id in class_ids:
        await enqueue_recompute_class(class_id)
    return await service.to_out(session, req)


@router.post(
    "/deletion-requests/{request_id}/reject", response_model=DeletionRequestOut, responses=DECIDE
)
async def reject(request_id: uuid.UUID, admin: Admin, session: Session) -> DeletionRequestOut:
    """Адміністрація школи відхиляє запит. Повтор — той самий результат; виконаний — 409."""
    req = await service.reject(session, admin, request_id)
    return await service.to_out(session, req)
