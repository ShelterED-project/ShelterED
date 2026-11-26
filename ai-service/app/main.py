"""HTTP-шар AI-сервісу. Контракт: contracts/openapi.yaml."""

import hmac
import logging

from app.analysis import InvalidTestError, analyze
from app.config import settings
from app.graph import app_graph
from app.llm import LLMError
from app.ocr import InvalidImageError
from app.schemas import (
    ChatRequest,
    ChatResponse,
    IntentEnum,
    TestAnalysisRequest,
    TestAnalysisResponse,
)
from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("ai-service")

app = FastAPI(title="ShelterED AI", version="1.0.0")

# Граф може повернути класи, яких немає в IntentEnum (support, chat)
INTENT_MAP = {
    "explain": IntentEnum.explain,
    "practice": IntentEnum.practice,
    "check": IntentEnum.check,
    "safety": IntentEnum.safety,
}


class ApiError(Exception):
    """Помилка з єдиним форматом тіла: {code, message, details}."""

    def __init__(self, status: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def _error(status: int, code: str, message: str, details=None, request: Request | None = None):
    headers = {}
    if request is not None and request.headers.get("x-request-id"):
        headers["X-Request-ID"] = request.headers["x-request-id"]
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "details": details},
        headers=headers,
    )


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return _error(exc.status, exc.code, exc.message, exc.details, request)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # Без "input": там може бути текст дитини або фото
    details = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
    return _error(422, "validation_error", "Request validation failed", details, request)


@app.exception_handler(InvalidImageError)
async def invalid_image_handler(request: Request, exc: InvalidImageError):
    return _error(422, "invalid_image", "image_base64 is not a valid image", None, request)


@app.exception_handler(InvalidTestError)
async def invalid_test_handler(request: Request, exc: InvalidTestError):
    return _error(422, "invalid_test", str(exc), None, request)


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    logger.warning("LLM error: %s", exc)
    return _error(503, "model_unavailable", str(exc), None, request)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")
    return _error(500, "internal_error", "Internal server error", None, request)


def auth(key: str | None) -> None:
    if not key or not hmac.compare_digest(key.encode(), settings.INTERNAL_KEY.encode()):
        raise ApiError(401, "unauthorized", "Invalid or missing X-Internal-Key")


def validate_action(req: ChatRequest) -> None:
    if req.action == "check" and not req.task:
        raise ApiError(422, "task_required", "action=check requires task")
    if req.action == "practice" and not req.task and not (req.topic or "").strip():
        raise ApiError(422, "topic_required", "action=practice without task requires topic")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ai/v1/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    x_internal_key: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    auth(x_internal_key)
    validate_action(req)

    state = {
        "user_id": req.user_id,
        "action": req.action,
        "grade": req.grade,
        "subject": req.subject,
        "topic": req.topic,
        "topic_id": req.topic_id,
        "user_input": req.message or "",
        "image_base64": req.image_base64,
        "history": [h.model_dump() for h in (req.history or [])],
        "profile": req.profile,
        "current_task": req.task,
        "hints_used": req.hints_used,
    }

    result = await app_graph.ainvoke(state)
    if not isinstance(result, dict):
        result = result.model_dump()

    intent = result.get("current_action", "explain")
    response = ChatResponse(
        reply=result.get("output_text", ""),
        intent=INTENT_MAP.get(intent, IntentEnum.explain),
        topic_id=req.topic_id,
        task=result.get("current_task"),
        hints_used=result.get("hints_used"),
        check_result=result.get("check_result"),
        suggestions=result.get("suggestions") or [],
    )
    headers = {"X-Request-ID": x_request_id} if x_request_id else {}
    return JSONResponse(content=response.model_dump(mode="json"), headers=headers)


@app.post("/ai/v1/test-analysis", response_model=TestAnalysisResponse)
async def test_analysis(
    req: TestAnalysisRequest,
    x_internal_key: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    """Аналіз тесту всього класу. Підрахунки — код, формулювання — LLM (без даних учнів)."""
    auth(x_internal_key)
    result = await analyze(req)
    headers = {"X-Request-ID": x_request_id} if x_request_id else {}
    return JSONResponse(content=result.model_dump(mode="json"), headers=headers)
