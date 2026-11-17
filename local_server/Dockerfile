FROM python:3.12-slim


WORKDIR /app


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Хмарний бекенд локально займає 8000, тому локальний сервер — 8080
ENV LOCAL_PORT=8080 \
    LOCAL_DB_PATH=/app/data/shelter.db
RUN mkdir -p /app/data
EXPOSE 8080

# Запускаємо сервер (фонова синхронізація стартує разом із ним)
CMD ["python", "run.py"]
