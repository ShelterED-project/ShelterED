# ShelterED AI-сервіс

Stateless FastAPI-сервіс без бази даних. Ендпоінти: `POST /ai/v1/chat`, `GET /health`.

- Контракт: [`contracts/openapi.yaml`](../contracts/openapi.yaml)
- Інструкція для backend: [`docs/backend-quickstart.md`](../docs/backend-quickstart.md)

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
  -H "X-Internal-Key: <INTERNAL_KEY>" \
  -H "Content-Type: application/json" \
  -d @contracts/examples/explain.json
```

## Змінні оточення (усі обов'язкові)

| Змінна | Опис |
|---|---|
| `INTERNAL_KEY` | значення заголовка `X-Internal-Key`, яке надсилає бекенд |
| `AI_KEY` | ключ API LLM |
| `LLM_BASE_URL` | OpenAI-сумісна адреса LLM |
| `MODELS` | назва моделі |
| `MOCK_LLM` | `true` повертає заглушку без LLM і OCR |
| `MODEL_EXPLAIN`, `MODEL_FAST`, `MODEL_OCR` | необов'язкові, інакше `MODELS` (OCR — `rukopys-ocr`) |
| `LLM_TIMEOUT` | таймаут одного виклику LLM, с (12) |

## Запуск на своєму ПК і доступ для backend

Backend працює не на цьому ПК, тому `localhost:8000` йому не видно. Відкриваємо тунель:

```
docker compose up --build -d                      # сервіс на 127.0.0.1:8000
cloudflared tunnel --url http://localhost:8000    # видасть https://xxxx.trycloudflare.com
```

1. Адресу з тунелю передати backend-розробнику як `AI_SERVICE_URL`.
2. `INTERNAL_KEY` у `.env` — довгий випадковий рядок (`python -c "import secrets; print(secrets.token_urlsafe(32))"`),
   бо сервіс видно з інтернету. Те саме значення backend ставить у `AI_INTERNAL_KEY`.
3. Адреса `trycloudflare.com` змінюється після кожного перезапуску `cloudflared` — щоразу повідомляти backend.
   Постійна адреса: іменований тунель Cloudflare (потрібен домен) або статичний домен ngrok.
4. Вимкнений ПК чи сон = backend отримує помилку з'єднання й показує запасний текст. Це очікувано.

Перевірка ззовні:

```
curl https://xxxx.trycloudflare.com/health
```

## Для DevOps

- Образ: `sheltered/ai-service`, порт `8000`, healthcheck `GET /health`.
- Сервіс stateless: томів і БД немає, логи йдуть у stdout.
- У продакшені порт не публікується назовні. Бекенд звертається за адресою `http://ai-service:8000` у спільній мережі.
- Секрети (`INTERNAL_KEY`, `AI_KEY`) передаються змінними оточення або secret store, файл `.env` у репозиторій і в образ не потрапляє.
- Контейнер запускається від непривілейованого користувача.