"""Клієнт AI-сервісу (контракт: docs/ai-contract.md → `contracts/openapi.yaml` AI-сервісу).

Виклики — `POST {AI_SERVICE_URL}/ai/v1/chat` (репетитор) і `POST /ai/v1/test-analysis`
(аналіз тесту класу, services/test_analysis.py) із заголовком `X-Internal-Key`. Сервіс
stateless: завдання, підказки, історію й аналізи зберігає backend.

Помилки для учня:
- адреса не задана, з'єднання/таймаут, 5xx, 401, 404 тунелю, непридатна відповідь →
  503 `AI_UNAVAILABLE` (клієнт показує пояснення з пакета);
- 422 `invalid_image` → 422 `INVALID_IMAGE` (фото не прочиталось — учень може переробити);
- інші 422 (запит не за схемою — помилка backend, повтор без змін не допоможе) →
  502 `AI_BAD_REQUEST`.

Повтор — лише один і лише на помилку з'єднання (запит до сервісу не дійшов). Таймаут
читання не повторюється: LLM уже працювала, повтор подвоїв би час очікування учня.
У лог — лише статус і машинний код помилки, без тексту запиту/відповіді й без ключа.
"""

import logging
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from app.core.config import Settings
from app.core.errors import AppError
from app.core.logging import request_id_var

logger = logging.getLogger(__name__)

CHAT_PATH = "/ai/v1/chat"
TEST_ANALYSIS_PATH = "/ai/v1/test-analysis"
INTENTS = ("explain", "practice", "check", "safety")


class AIChatResponse(BaseModel):
    """Відповідь `/ai/v1/chat`. Невідомі поля ігноруються, невідомий `intent` = `explain`
    (правила сумісності v1 контракту AI)."""

    model_config = ConfigDict(extra="ignore")

    reply: str
    intent: str
    topic_id: str | None = None
    task: dict[str, Any] | None = None
    hints_used: int | None = None
    check_result: dict[str, Any] | None = None
    suggestions: list[str] = []

    def normalized_intent(self) -> str:
        return self.intent if self.intent in INTENTS else "explain"


def ai_unavailable() -> AppError:
    return AppError(
        "AI_UNAVAILABLE",
        "AI tutor is temporarily unavailable; use cached explanations from the pack",
        status_code=503,
    )


class AIClient:
    def __init__(
        self,
        base_url: str,
        internal_key: str,
        *,
        timeout_s: float = 30.0,
        image_timeout_s: float = 45.0,
        analysis_timeout_s: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._key = internal_key
        self.timeout_s = timeout_s
        self.image_timeout_s = image_timeout_s
        self.analysis_timeout_s = analysis_timeout_s
        self._transport = transport

    @classmethod
    def from_settings(
        cls, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> "AIClient":
        return cls(
            settings.ai_service_url,
            settings.ai_internal_key.get_secret_value(),
            timeout_s=settings.ai_timeout_s,
            image_timeout_s=settings.ai_image_timeout_s,
            analysis_timeout_s=settings.ai_analysis_timeout_s,
            transport=transport,
        )

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    async def chat(self, payload: dict[str, Any]) -> AIChatResponse:
        if not self.enabled:
            raise ai_unavailable()
        timeout = self.image_timeout_s if payload.get("image_base64") else self.timeout_s
        response = await self._post(CHAT_PATH, payload, self._headers(), timeout)
        if response.status_code == 200:
            try:
                return AIChatResponse.model_validate(response.json())
            except (ValueError, ValidationError):
                logger.warning("AI service returned an unusable response body")
                raise ai_unavailable() from None
        code = _error_code(response)
        if response.status_code == 401:
            logger.error("AI service rejected the internal key (check AI_INTERNAL_KEY)")
        elif response.status_code == 422:
            logger.warning("AI service rejected the request: status=422 code=%s", code)
            if code == "invalid_image":
                raise AppError("INVALID_IMAGE", "The photo could not be read", status_code=422)
            raise AppError("AI_BAD_REQUEST", "AI service rejected the request", status_code=502)
        else:
            logger.warning("AI service error: status=%d code=%s", response.status_code, code)
        raise ai_unavailable()

    async def test_analysis(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Аналіз тесту класу. Відповідь повертається як є (dict): backend лише підміняє
        псевдоніми учнів і зберігає її в `test_analysis.result`.

        Помилки: вимкнено/недоступно/5xx/непридатна відповідь → `AI_UNAVAILABLE`;
        422 (запит не за схемою, напр. `invalid_test`) → `AI_BAD_REQUEST`."""
        if not self.enabled:
            raise ai_unavailable()
        response = await self._post(
            TEST_ANALYSIS_PATH, payload, self._headers(), self.analysis_timeout_s
        )
        if response.status_code == 200:
            try:
                body = response.json()
            except ValueError:
                body = None
            if isinstance(body, dict) and isinstance(body.get("students"), list):
                return body
            logger.warning("AI service returned an unusable test-analysis body")
            raise ai_unavailable()
        code = _error_code(response)
        if response.status_code == 401:
            logger.error("AI service rejected the internal key (check AI_INTERNAL_KEY)")
        elif response.status_code == 422:
            logger.warning("AI service rejected test-analysis: status=422 code=%s", code)
            raise AppError("AI_BAD_REQUEST", "AI service rejected the request", status_code=502)
        else:
            logger.warning("AI service error: status=%d code=%s", response.status_code, code)
        raise ai_unavailable()

    def _headers(self) -> dict[str, str]:
        headers = {"X-Internal-Key": self._key}
        # Наскрізний id запиту для логів обох сервісів (у Celery-задачі — свій або немає).
        request_id = request_id_var.get()
        if request_id:
            headers["X-Request-ID"] = request_id
        return headers

    async def _post(
        self, path: str, payload: dict[str, Any], headers: dict[str, str], timeout: float
    ) -> httpx.Response:
        url = f"{self.base_url}{path}"
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=timeout, transport=self._transport) as http:
                    return await http.post(url, json=payload, headers=headers)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                logger.warning(
                    "AI service unreachable (attempt %d): %s", attempt, type(exc).__name__
                )
                if attempt == 2:
                    break
            except httpx.HTTPError as exc:
                logger.warning("AI service request failed: %s", type(exc).__name__)
                break
        raise ai_unavailable()


def _error_code(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    code = body.get("code") if isinstance(body, dict) else None
    return code if isinstance(code, str) else None
