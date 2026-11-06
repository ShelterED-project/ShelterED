"""Web Push: ключ VAPID і підписки (B8)."""

import base64
import binascii
import datetime as dt
import ipaddress
import uuid
from typing import Annotated
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.core.config import get_settings

SUBSCRIPTION_ID = "0192f0a0-0000-7000-8000-000000000a01"
ENDPOINT = "https://fcm.googleapis.com/fcm/send/dXk2...abc"

Key = Annotated[str, StringConstraints(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_=-]+$")]


def _b64url_decode(value: str) -> bytes | None:
    """base64url з `=` у кінці чи без нього; доповнення рахуємо від рядка без `=`."""
    stripped = value.rstrip("=")
    try:
        return base64.urlsafe_b64decode(stripped + "=" * (-len(stripped) % 4))
    except (binascii.Error, ValueError):
        return None


def _b64url_len(value: str) -> int:
    raw = _b64url_decode(value)
    return -1 if raw is None else len(raw)


class PushKeys(BaseModel):
    """Ключі підписки браузера, base64url: p256dh — точка P-256 (65 байт), auth — 16 байт."""

    p256dh: Key
    auth: Key

    @field_validator("p256dh")
    @classmethod
    def _p256dh(cls, value: str) -> str:
        raw = _b64url_decode(value)
        if raw is None or len(raw) != 65:
            raise ValueError("p256dh must be a base64url P-256 public key (65 bytes)")
        # Точка має лежати на кривій P-256: інакше шифрування payload падає на кожній відправці.
        try:
            ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), raw)
        except ValueError:
            raise ValueError("p256dh is not a valid P-256 public key") from None
        return value

    @field_validator("auth")
    @classmethod
    def _auth(cls, value: str) -> str:
        if _b64url_len(value) != 16:
            raise ValueError("auth must be a base64url 16-byte secret")
        return value


class PushSubscriptionCreate(BaseModel):
    """Як `PushSubscription.toJSON()` у браузері + `id` від клієнта.

    Ідемпотентно: повтор із тим самим `endpoint` повертає наявну підписку (переприв'язує
    її до поточного користувача). Кілька пристроїв на користувача — кілька підписок.
    """

    id: uuid.UUID
    endpoint: Annotated[str, StringConstraints(max_length=2048, pattern=r"^https://")]
    keys: PushKeys

    @field_validator("endpoint")
    @classmethod
    def _endpoint(cls, value: str) -> str:
        """Лише HTTPS-адреса push-сервісу за доменним ім'ям: воркер робить на неї POST, тож
        IP-адреси, localhost і адреси з обліковими даними відхиляємо, а хост має належати
        відомому push-сервісу з `PUSH_ALLOWED_HOST_SUFFIXES` (захист від SSRF)."""
        parts = urlsplit(value)
        host = (parts.hostname or "").rstrip(".")
        if (
            parts.scheme != "https"
            or not host
            or parts.username is not None
            or "." not in host
            or host == "localhost"
            or host.endswith(".localhost")
            or any(ch.isspace() for ch in value)
        ):
            raise ValueError("endpoint must be an https URL of a push service")
        try:
            ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            pass
        else:
            raise ValueError("endpoint must be an https URL of a push service")
        host = host.lower()
        suffixes = [s.lower().strip(".") for s in get_settings().push_allowed_host_suffixes]
        if not any(host == s or host.endswith("." + s) for s in suffixes if s):
            raise ValueError("endpoint host is not a known Web Push service")
        return value

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": SUBSCRIPTION_ID,
                    "endpoint": ENDPOINT,
                    "keys": {
                        "p256dh": "BBJFmkZC5F0jfP24cPgJUCB45eRrVp1-DWnDyMYoxVXhkPqlJDq98HcVnf0x"
                        "elE_ZbzOfuy3yave_sTvQf3qH8M",
                        "auth": "dGKjugWk0qMwRUW6A0jvNQ",
                    },
                }
            ]
        }
    )


class PushSubscriptionOut(BaseModel):
    id: uuid.UUID
    endpoint: str
    created_at: dt.datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": SUBSCRIPTION_ID,
                    "endpoint": ENDPOINT,
                    "created_at": "2026-11-05T08:00:00Z",
                }
            ]
        },
    )


class VapidKeyOut(BaseModel):
    """Публічний ключ VAPID, base64url (нестиснена точка P-256)."""

    public_key: str

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "public_key": "BCTzOAxHjAlTsdbtrMg4mKkcK8ka6j6EaNl5_QaSbAiJ4aPYalDUi8P6az5"
                    "Fw8eEKMonQcHs4c-1rf539PNyDVs"
                }
            ]
        }
    )
