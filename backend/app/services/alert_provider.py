"""Провайдери API повітряних тривог (B7.1).

Бекенд сам опитує API тривог (без AI-сервісу). Інтерфейс `AlertProvider` дозволяє замінити
alerts.in.ua іншим API: провайдер віддає всі активні тривоги з типом і uid локації (область,
район, громада, місто). Яка тривога стосується школи, вирішує `app.services.alerts`:
`region_code` школи = id області в провайдера (для alerts.in.ua — `location_uid`, напр. "31"),
необов'язкові `alert_raion_uid` / `alert_hromada_uid` / `alert_city_uid` — точні локації.
"""

import datetime as dt
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from app.core.config import Settings

logger = logging.getLogger(__name__)


LocationType = Literal["oblast", "raion", "hromada", "city", "unknown"]

# Міста зі спеціальним статусом — окремі регіони alerts.in.ua (`location_type == "city"`):
# 30 — м. Севастополь, 31 — м. Київ. Інші міста — частини областей.
REGION_CITY_UIDS = frozenset({"30", "31"})

# Назва локації в журналі — довідкова; обрізаємо, щоб зламане API не роздувало рядки.
_TITLE_MAX = 200


@dataclass(frozen=True)
class ProviderAlert:
    """Активна тривога провайдера в одній локації."""

    external_id: str
    location_type: LocationType
    location_uid: str
    started_at: dt.datetime
    alert_type: str | None = None
    location_title: str | None = None

    @property
    def is_region(self) -> bool:
        """Тривога всього регіону (області чи міста зі спеціальним статусом)."""
        return self.location_type == "oblast" or (
            self.location_type == "city" and self.location_uid in REGION_CITY_UIDS
        )


@dataclass(frozen=True)
class ActiveAlerts:
    """Відповідь провайдера. `complete = False` — частину записів не вдалося розібрати:
    відсутність тривоги у списку тоді не означає відбою."""

    alerts: list[ProviderAlert]
    complete: bool = True


class AlertProviderError(Exception):
    """Провайдер недоступний або змінив формат. `reason` — безпечний для логів код
    (без URL і тексту відповіді: там може бути токен)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AlertProvider(ABC):
    name: str

    @abstractmethod
    async def active_alerts(self) -> ActiveAlerts:
        """Усі активні тривоги (будь-якого рівня й типу). Помилка → AlertProviderError."""


class _InUaAlert(BaseModel):
    """Поля alerts.in.ua, які ми використовуємо (решта ігнорується)."""

    id: int | str
    # Невідомий тип локації — невалідний запис (а не «немає тривоги»): якщо API перейменує
    # тип, відповідь стане неповною й хибного відбою не буде.
    location_type: LocationType
    location_uid: int | str
    location_title: str | None = None
    alert_type: str | None = Field(default=None, min_length=1, max_length=50)
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None

    model_config = ConfigDict(extra="ignore")


def parse_alerts_in_ua(data: Any) -> ActiveAlerts:
    """Розбір `GET /v1/alerts/active.json`: усі активні тривоги будь-якого рівня (область,
    район, громада, місто) і будь-якого типу (`air_raid`, `artillery_shelling`,
    `urban_fights`, ...). Невалідні записи пропускаються (лічильник у лог) і роблять
    відповідь неповною (`complete = False`), невалідна відповідь цілком — помилка."""
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
        if item.finished_at is not None:
            continue
        title = item.location_title.strip()[:_TITLE_MAX] if item.location_title else None
        result.append(
            ProviderAlert(
                external_id=str(item.id),
                location_type=item.location_type,
                location_uid=str(item.location_uid),
                started_at=item.started_at.astimezone(dt.UTC),
                alert_type=item.alert_type,
                location_title=title or None,
            )
        )
    if skipped:
        logger.warning("alerts.in.ua: skipped %d invalid alert records", skipped)
    return ActiveAlerts(result, complete=skipped == 0)


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
        self._max_bytes = settings.alerts_max_response_bytes
        self._transport = transport

    async def active_alerts(self) -> ActiveAlerts:
        headers = {"Authorization": f"Bearer {self._token.get_secret_value()}"}
        try:
            async with (
                httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client,
                client.stream("GET", self._url, headers=headers) as response,
            ):
                if response.status_code != 200:
                    raise AlertProviderError(f"http_{response.status_code}")
                body = await self._read_capped(response)
        except httpx.TimeoutException as exc:
            raise AlertProviderError("timeout") from exc
        except httpx.HTTPError as exc:
            raise AlertProviderError("network_error") from exc
        try:
            data = json.loads(body)
        except ValueError as exc:
            raise AlertProviderError("invalid_response") from exc
        return parse_alerts_in_ua(data)

    async def _read_capped(self, response: httpx.Response) -> bytes:
        """Тіло (вже розпаковане) не більше ALERTS_MAX_RESPONSE_BYTES: зламане чи підмінене API
        не з'їсть пам'ять воркера. Більше — помилка провайдера, як невалідна відповідь
        (тривоги лишаються активними, відбою немає)."""
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_bytes:
                raise AlertProviderError("response_too_large")
            chunks.append(chunk)
        return b"".join(chunks)
