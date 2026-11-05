"""ШІ-репетитор: проксі до AI-сервісу (заглушка B4; логіка — B13)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_roles
from app.api.stub import R501, example_of, not_implemented
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.tutor import TutorAnswerOut, TutorAskRequest

router = APIRouter(tags=["tutor"])

Student = Annotated[User, Depends(require_roles("student"))]


@router.post(
    "/tutor/ask",
    response_model=TutorAnswerOut,
    responses={
        200: example_of(TutorAnswerOut),
        401: {"model": ErrorResponse, "description": "Не автентифіковано"},
        403: {"model": ErrorResponse, "description": "Недостатньо прав"},
        429: {"model": ErrorResponse, "description": "RATE_LIMITED: ліміт запитів учня"},
        503: {
            "model": ErrorResponse,
            "description": "AI_UNAVAILABLE: використайте закешовані пояснення з пакета",
        },
        **R501,
    },
)
async def ask(body: TutorAskRequest, student: Student) -> TutorAnswerOut:
    """Пояснити іншими словами або розібрати помилки в спробі тесту. Лише учень, з лімітом
    запитів. Падіння AI-сервісу не ламає уроки: клієнт показує пояснення з пакета."""
    raise not_implemented()
