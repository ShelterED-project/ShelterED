# Один образ для API, Celery-воркера й beat; команду для воркера/beat задає compose.
FROM python:3.13-slim AS build

WORKDIR /src
COPY pyproject.toml ./
COPY app ./app
# Лише runtime-залежності з pyproject.toml (без pytest/ruff/flake8 з requirements.txt).
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=prod \
    MEDIA_ROOT=/app/media

RUN useradd --create-home --uid 1000 app

WORKDIR /app
COPY --from=build /install /usr/local
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
# Том для медіа монтується сюди; власник — непривілейований користувач.
RUN mkdir -p /app/media && chown app:app /app/media

USER app

EXPOSE 8000

# Real client IP behind Nginx (rate limiting keys on it): uvicorn trusts X-Forwarded-For only
# from FORWARDED_ALLOW_IPS (comma-separated IPs/networks). The default trusts nobody but
# localhost; set it to the Nginx container IP or its Docker network subnet in compose.
# Never "*" while the API port is reachable bypassing Nginx: clients could spoof their IP.
ENV FORWARDED_ALLOW_IPS=127.0.0.1,::1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
