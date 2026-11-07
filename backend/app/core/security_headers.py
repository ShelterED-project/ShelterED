"""Заголовки безпеки для всіх відповідей API (B15.2, бекенд-частина).

- `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` —
  завжди (API не вбудовується у фрейми й не має сторінок, крім `/docs`).
- `Cache-Control: no-store` за замовчуванням на всі відповіді: токени, одноразові коди
  (прив'язка батьків, код класу), дані дітей не мають лягати в кеш браузера чи проксі.
  Ендпоінти, які кешуються навмисно (пакети `GET /packs/{id}`, перекличка з ETag), ставлять
  власний `Cache-Control` — його middleware не чіпає. Від шляху (і `root_path`) не залежить.
- `Strict-Transport-Security` — лише коли HSTS увімкнено (`HSTS_ENABLED` або `ENVIRONMENT=prod`)
  і запит справді прийшов по HTTPS. Схему ставить uvicorn з `--proxy-headers` за
  `X-Forwarded-Proto` від довіреного Nginx (`FORWARDED_ALLOW_IPS`); сирий заголовок тут не
  читаємо, бо його може підробити клієнт. Основний HSTS і редирект HTTP→HTTPS — у Nginx.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts_max_age_s: int | None = None) -> None:
        """`hsts_max_age_s` None — HSTS вимкнено."""
        self.app = app
        self.hsts = None if hsts_max_age_s is None else f"max-age={hsts_max_age_s}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        hsts = self.hsts if scope.get("scheme") == "https" else None

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in STATIC_HEADERS.items():
                    headers.setdefault(name, value)
                headers.setdefault("Cache-Control", "no-store")
                if hsts is not None:
                    headers["Strict-Transport-Security"] = hsts
            await send(message)

        await self.app(scope, receive, send_with_headers)
