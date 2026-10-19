import json
import sys
import os
import yaml

# Добавляем путь к папке ai-service, чтобы Python нашел FastAPI-приложение
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "ai-service")))

from app.main import app

# Получаем схему напрямую из FastAPI
openapi_schema = app.openapi()

# Создаем папку contracts в корне, если ее нет
os.makedirs("contracts", exist_ok=True)

# 1. Сохраняем как JSON
with open("contracts/openapi.json", "w", encoding="utf-8") as f:
    json.dump(openapi_schema, f, ensure_ascii=False, indent=2)

# 2. Сохраняем как YAML
with open("contracts/openapi.yaml", "w", encoding="utf-8") as f:
    yaml.dump(openapi_schema, f, allow_unicode=True, sort_keys=False)

print("Документация успешно сохранена в contracts/openapi.json та contracts/openapi.yaml!")