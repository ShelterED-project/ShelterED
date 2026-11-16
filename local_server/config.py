"""Налаштування локального сервера через змінні оточення."""

import os

# Хмарний API ShelterED (бекенд локально працює на 8000)
CLOUD_API_URL = os.getenv("CLOUD_API_URL", "http://localhost:8000").rstrip("/")

# Порт локального сервера (не 8000, щоб не конфліктувати з бекендом)
LOCAL_PORT = int(os.getenv("LOCAL_PORT", "8080"))

# Адреса ноутбука у Wi-Fi точці доступу Windows (для QR-коду)
HOTSPOT_HOST = os.getenv("HOTSPOT_HOST", "192.168.137.1")

# Як часто фоновий потік синхронізує дані з хмарою, секунд
SYNC_INTERVAL_S = float(os.getenv("SYNC_INTERVAL_S", "30"))

# Файл SQLite
LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", "./shelter.db")

# OAuth client_id, зареєстрований у хмарі
CLIENT_ID = "sheltered-pwa"

HTTP_TIMEOUT_S = 10.0

STUDENT_URL = f"http://{HOTSPOT_HOST}:{LOCAL_PORT}/"
