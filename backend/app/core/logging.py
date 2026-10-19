import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

# ID поточного запиту. Кожен запит у uvicorn виконується в окремій asyncio-задачі
# зі своєю копією контексту, тому значення не перетікає між запитами.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# Додаткові поля, які можна передати через logger.info(..., extra={...}).
EXTRA_FIELDS = ("method", "path", "status", "duration_ms")


_base_factory = logging.getLogRecordFactory()


def _record_factory(*args, **kwargs) -> logging.LogRecord:
    # request_id додається під час створення запису, тобто в контексті запиту,
    # тому його бачать усі handler-и, а не лише наш.
    record = _base_factory(*args, **kwargs)
    record.request_id = request_id_var.get()
    return record


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for field in EXTRA_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


TEXT_FORMAT = "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"


def setup_logging(level: str, fmt: str) -> None:
    logging.setLogRecordFactory(_record_factory)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if fmt == "json" else logging.Formatter(TEXT_FORMAT))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Логи uvicorn ідуть через наш handler; його access-лог вимикаємо,
    # бо кожен запит логує RequestIdMiddleware (з request ID і тривалістю).
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    # httpx на INFO логує повний URL з query string (там можуть бути токени).
    logging.getLogger("httpx").setLevel(logging.WARNING)
