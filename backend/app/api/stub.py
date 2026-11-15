"""Заглушки контракту API (B4): ендпоінт описаний і захищений, логіка — у своєму епіку.

Заглушка відповідає 501 `NOT_IMPLEMENTED` у єдиному форматі помилок, а успішна відповідь
описана в OpenAPI з прикладом, щоб фронтенд міг працювати на моках (Prism).
Коли епік реалізує ендпоінт, він прибирає `not_implemented()` і `R501`.
"""

from typing import Any

from pydantic import BaseModel

from app.core.errors import AppError
from app.schemas.errors import ErrorResponse

R501 = {501: {"model": ErrorResponse, "description": "NOT_IMPLEMENTED: заглушка контракту"}}


def not_implemented() -> AppError:
    return AppError("NOT_IMPLEMENTED", "Endpoint is not implemented yet", status_code=501)


def example(value: Any, description: str = "Успішна відповідь") -> dict[str, Any]:
    """Опис успішної відповіді з прикладом (для моків)."""
    return {"description": description, "content": {"application/json": {"example": value}}}


def example_of(model: type[BaseModel], description: str = "Успішна відповідь") -> dict[str, Any]:
    """Те саме, приклад береться з `json_schema_extra.examples` моделі."""
    return example(model.model_config["json_schema_extra"]["examples"][0], description)
