"""Підписки Web Push (контракт B4, логіка — B8)."""

import datetime as dt
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

SUBSCRIPTION_ID = "0192f0a0-0000-7000-8000-000000000a01"
ENDPOINT = "https://fcm.googleapis.com/fcm/send/dXk2...abc"

Key = Annotated[str, StringConstraints(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_=-]+$")]


class PushKeys(BaseModel):
    p256dh: Key
    auth: Key


class PushSubscriptionCreate(BaseModel):
    """Як `PushSubscription.toJSON()` у браузері + `id` від клієнта.

    Ідемпотентно: повтор із тим самим `endpoint` повертає наявну підписку (переприв'язує
    її до поточного користувача). Кілька пристроїв на користувача — кілька підписок.
    """

    id: uuid.UUID
    endpoint: Annotated[str, StringConstraints(max_length=2048, pattern=r"^https://")]
    keys: PushKeys

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": SUBSCRIPTION_ID,
                    "endpoint": ENDPOINT,
                    "keys": {
                        "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQ",
                        "auth": "tBHI",
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
