"""Ліміт розміру тіла запиту (B15): JSON-ендпоінти не мають приймати мегабайти.

Без ліміту pydantic розбирає будь-яке тіло цілком у пам'ять (довільний `payload` події
синхронізації, довгі рядки без `max_length`), тож один запит може з'їсти пам'ять воркера.
Тіло більше за `MAX_REQUEST_BODY_BYTES` — 413 `PAYLOAD_TOO_LARGE`:

- є `Content-Length` — перевіряємо його одразу, не читаючи тіло (uvicorn не віддасть більше
  байтів, ніж заявлено);
- немає (`Transfer-Encoding: chunked`) — читаємо тіло до ліміту в пам'ять і віддаємо застосунку
  з буфера; на перевищенні читання зупиняється.

Завантаження медіа (`PUT /media/{id}`) іде потоком і має власні ліміти за типом файла
(`MEDIA_MAX_*_BYTES`), тож тут пропускається. Основний ліміт на краю — `client_max_body_size`
у Nginx; цей — захист самого застосунку.
"""

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import error_response

# Шляхи з власним лімітом (потокове завантаження медіа). `root_path` може стояти попереду.
_EXEMPT = re.compile(r"(^|/)media/[^/]+$")


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    def _too_large(self) -> JSONResponse:
        return error_response(
            413,
            "PAYLOAD_TOO_LARGE",
            "Request body is too large",
            details={"max_bytes": self.max_bytes},
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or (scope["method"] == "PUT" and _EXEMPT.search(scope["path"])):
            await self.app(scope, receive, send)
            return
        length = None
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    length = int(value)
                except ValueError:
                    length = None
                break
        if length is not None:
            if length > self.max_bytes:
                await self._too_large()(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        # Без Content-Length: буферизуємо тіло до ліміту.
        messages: list[Message] = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                await self._too_large()(scope, receive, send)
                return
            if not message.get("more_body", False):
                break

        async def replay() -> Message:
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay, send)
