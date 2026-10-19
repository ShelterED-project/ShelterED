import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import request_id_var

HEADER = "X-Request-ID"
# Приймаємо ID від клієнта лише в безпечному форматі, щоб у лог не потрапило сміття.
VALID_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

logger = logging.getLogger("app.request")


class RequestIdMiddleware:
    """Бере X-Request-ID з запиту (або генерує), кладе в контекст логів і у відповідь."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(HEADER.lower().encode(), b"").decode("latin-1")
        request_id = incoming if VALID_ID.match(incoming) else uuid.uuid4().hex
        request_id_var.set(request_id)

        status = 500
        started = time.perf_counter()

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message)[HEADER] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            # Шлях без query string: у параметрах можуть бути токени чи коди.
            logger.info(
                "request",
                extra={
                    "method": scope["method"],
                    "path": scope["path"],
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                },
            )
