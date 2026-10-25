# ShelterED AI-сервіс

Stateless FastAPI-сервіс без бази даних. Ендпоінти: `POST /ai/v1/chat`, `GET /health`.

## Запуск

```
cp .env.example .env      # заповнити значення
docker compose up --build -d
curl localhost:8000/health
docker compose logs -f ai-service
```

Перевірка чату на прикладі з контракту:

```
curl -X POST localhost:8000/ai/v1/chat \
  -H "X-Internal-Key: change-me" \
  -H "Content-Type: application/json" \
  -d @contracts/explain.json
```

## Змінні оточення (усі обов'язкові)

| Змінна | Опис |
|---|---|
| `INTERNAL_KEY` | значення заголовка `X-Internal-Key`, яке надсилає бекенд |
| `AI_KEY` | ключ API LLM |
| `LLM_BASE_URL` | OpenAI-сумісна адреса LLM |
| `MODELS` | назва моделі |
| `MOCK_LLM` | `true` повертає заглушку без LLM |

## Для DevOps

- Образ: `sheltered/ai-service`, порт `8000`, healthcheck `GET /health`.
- Сервіс stateless: томів і БД немає, логи йдуть у stdout.
- У продакшені порт не публікується назовні. Бекенд звертається за адресою `http://ai-service:8000` у спільній мережі.
- Секрети (`INTERNAL_KEY`, `AI_KEY`) передаються змінними оточення або secret store, файл `.env` у репозиторій і в образ не потрапляє.
- Контейнер запускається від непривілейованого користувача.