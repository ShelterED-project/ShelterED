#!/bin/sh
# Старт API: спершу міграції (Alembic бере блокування в БД — паралельний старт безпечний),
# потім сервер. RUN_MIGRATIONS=false — пропустити (міграції запускає хтось інший).
set -e
if [ "${RUN_MIGRATIONS:-true}" != "false" ]; then
    alembic upgrade head
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
