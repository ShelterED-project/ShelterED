"""ШІ-репетитор (B13): проксі до AI-сервісу зі станом розмови на сервері."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import Limiter, Session, SettingsDep, require_roles
from app.api.stub import example_of
from app.core.rate_limit import enforce, rule
from app.models.school import User
from app.schemas.errors import ErrorResponse
from app.schemas.tutor import TutorAnswerOut, TutorAskRequest
from app.services import tutor as service
from app.services.ai import AIClient

router = APIRouter(tags=["tutor"])

Student = Annotated[User, Depends(require_roles("student"))]


def get_ai_client(settings: SettingsDep) -> AIClient:
    """Клієнт AI-сервісу (тести підміняють його клієнтом із фейковим транспортом)."""
    return AIClient.from_settings(settings)


AI = Annotated[AIClient, Depends(get_ai_client)]


@router.post(
    "/tutor/ask",
    response_model=TutorAnswerOut,
    responses={
        200: example_of(TutorAnswerOut),
        401: {"model": ErrorResponse, "description": "Не автентифіковано"},
        403: {
            "model": ErrorResponse,
            "description": "Не учень або урок не в розкладі/пакеті класу учня",
        },
        404: {
            "model": ErrorResponse,
            "description": "Урок/модуль/картку не знайдено або розмова належить іншому учню",
        },
        413: {"model": ErrorResponse, "description": "PAYLOAD_TOO_LARGE: тіло з фото завелике"},
        422: {
            "model": ErrorResponse,
            "description": "VALIDATION_ERROR; INVALID_IMAGE (не JPEG/PNG, завелике чи не "
            "прочиталось); TUTOR_TASK_REQUIRED (`check` без завдання); TUTOR_TOPIC_REQUIRED",
        },
        429: {
            "model": ErrorResponse,
            "description": "RATE_LIMITED: ліміт запитів учня; повторити після `Retry-After` с",
            "headers": {"Retry-After": {"schema": {"type": "integer"}}},
        },
        502: {
            "model": ErrorResponse,
            "description": "AI_BAD_REQUEST: AI-сервіс відхилив запит backend (помилка контракту)",
        },
        503: {
            "model": ErrorResponse,
            "description": "AI_UNAVAILABLE: використайте закешовані пояснення з пакета",
        },
    },
)
async def ask(
    body: TutorAskRequest,
    student: Student,
    session: Session,
    limiter: Limiter,
    settings: SettingsDep,
    client: AI,
) -> TutorAnswerOut:
    """Один крок розмови з репетитором: пояснення, завдання й підказки, перевірка відповіді
    (текстом або фото). Лише учень, з лімітом запитів (`RATE_LIMIT_TUTOR` за
    `RATE_LIMIT_TUTOR_WINDOW_S`, 429 з `Retry-After`). Стан розмови (завдання, підказки,
    8 останніх реплік) зберігає сервер; повтор `request_id` повертає ту саму відповідь без
    нового виклику AI і без витрати ліміту. Типове `explain` (без `message`) спершу бере
    спільне закешоване пояснення матеріалу (`cached: true`, без LLM); повторне в тій самій
    розмові — нове від LLM. Недоступний AI → 503 (для `explain` модуля з готовим поясненням —
    воно, `cached: true`): клієнт показує пояснення з пакета."""
    replay = await service.find_replay(session, student, body)
    if replay is not None:
        return replay
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
    return await service.ask(session, student, body, client, settings)
