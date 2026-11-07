"""ШІ-репетитор: проксі до AI-сервісу (заглушка B4; логіка — B13)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import Limiter, SettingsDep, require_roles
from app.api.stub import R501, example_of, not_implemented
from app.core.rate_limit import enforce, rule
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
        429: {
            "model": ErrorResponse,
            "description": "RATE_LIMITED: ліміт запитів учня; повторити після `Retry-After` с",
            "headers": {"Retry-After": {"schema": {"type": "integer"}}},
        },
        503: {
            "model": ErrorResponse,
            "description": "AI_UNAVAILABLE: використайте закешовані пояснення з пакета",
        },
        **R501,
    },
)
async def ask(
    body: TutorAskRequest, student: Student, limiter: Limiter, settings: SettingsDep
) -> TutorAnswerOut:
    """Пояснити іншими словами або розібрати помилки в спробі тесту. Лише учень, з лімітом
    запитів (`RATE_LIMIT_TUTOR` за `RATE_LIMIT_TUTOR_WINDOW_S`, 429 з `Retry-After`).
    Падіння AI-сервісу не ламає уроки: клієнт показує пояснення з пакета."""
    await enforce(
        limiter,
        [
            rule(
                "tutor",
                str(student.id),
                settings.rate_limit_tutor,
                settings.rate_limit_tutor_window_s,
            )
        ],
    )
    raise not_implemented()
