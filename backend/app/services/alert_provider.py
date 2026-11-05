"""Провайдери API повітряних тривог (B7.1).

Бекенд сам опитує API тривог (без AI-сервісу). Інтерфейс `AlertProvider` дозволяє замінити
alerts.in.ua іншим API: провайдер віддає лише активні тривоги рівня області.
`region_code` школи = id області в провайдера (для alerts.in.ua — `location_uid`, напр. "31").
"""

import datetime as dt
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, ValidationError

from app.core.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderAlert:
    """Активна тривога області."""

    external_id: str
    region_code: str
    started_at: dt.datetime


class AlertProviderError(Exception):
    """Провайдер недоступний або змінив формат. `reason` — безпечний для логів код
    (без URL і тексту відповіді: там може бути токен)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AlertProvider(ABC):
    name: str

    @abstractmethod
    async def active_alerts(self) -> list[ProviderAlert]:
        """Усі активні тривоги рівня області. Помилка → AlertProviderError."""


class _InUaAlert(BaseModel):
    """Поля alerts.in.ua, які ми використовуємо (решта ігнорується)."""

    id: int | str
    location_type: str
    location_uid: int | str
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None

    model_config = ConfigDict(extra="ignore")


def parse_alerts_in_ua(data: Any) -> list[ProviderAlert]:
    """Розбір `GET /v1/alerts/active.json`. Беремо тривоги рівня області (`location_type ==
    "oblast"`) будь-якого типу (`air_raid`, `artillery_shelling`, ...): школа прив'язана до
    області. Тривоги районів і громад не вмикають тривогу для всієї області. Невалідні
    записи пропускаються (лічильник у лог), невалідна відповідь цілком — помилка."""
    if not isinstance(data, dict) or not isinstance(data.get("alerts"), list):
        raise AlertProviderError("invalid_response")
    result: list[ProviderAlert] = []
    skipped = 0
    for raw in data["alerts"]:
        try:
            item = _InUaAlert.model_validate(raw)
        except ValidationError:
            skipped += 1
            continue
        if item.location_type != "oblast" or item.finished_at is not None:
            continue
        result.append(
            ProviderAlert(
                external_id=str(item.id),
                region_code=str(item.location_uid),
                started_at=item.started_at.astimezone(dt.UTC),
            )
        )
    if skipped:
        logger.warning("alerts.in.ua: skipped %d invalid alert records", skipped)
    return result


class AlertsInUaProvider(AlertProvider):
    """https://devs.alerts.in.ua — `Authorization: Bearer <token>`."""

    name = "alerts.in.ua"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if not settings.alerts_polling_enabled:
            raise ValueError("ALERTS_API_TOKEN is not set")
        assert settings.alerts_api_token is not None
        self._token = settings.alerts_api_token
        self._url = settings.alerts_api_url
        self._timeout = settings.alerts_http_timeout_s
        self._transport = transport

    async def active_alerts(self) -> list[ProviderAlert]:
        headers = {"Authorization": f"Bearer {self._token.get_secret_value()}"}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(self._url, headers=headers)
        except httpx.TimeoutException as exc:
            raise AlertProviderError("timeout") from exc
        except httpx.HTTPError as exc:
            raise AlertProviderError("network_error") from exc
        if response.status_code != 200:
            raise AlertProviderError(f"http_{response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            raise AlertProviderError("invalid_response") from exc
        return parse_alerts_in_ua(data)
