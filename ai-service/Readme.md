# ShelterED AI-сервіс

Stateless FastAPI-сервіс без бази даних. Ендпоінти: `POST /ai/v1/chat` (репетитор),
`POST /ai/v1/test-analysis` (аналіз тесту класу), `GET /health`.

- Контракт: [`contracts/openapi.yaml`](../contracts/openapi.yaml)
- Інструкція для backend: [`docs/backend-quickstart.md`](../docs/backend-quickstart.md),
  аналіз тестів: [`docs/backend-test-analysis.md`](../docs/backend-test-analysis.md)
- Тести: `pip install pytest` і `pytest -q` з папки `ai-service` (LLM не викликається)

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
| `LLM_ANALYSIS_TIMEOUT` | таймаут одного виклику LLM в аналізі тесту, с (60) |

## Запуск на своєму ПК і доступ для backend

Backend працює не на цьому ПК, тому `localhost:8000` йому не видно. Сервіс відкривається в інтернет
через ngrok за **постійною** адресою (безкоштовний dev-домен акаунта ngrok: dashboard → Domains).

Один раз:

```
winget install ngrok.ngrok
ngrok config add-authtoken <токен з dashboard → Your Authtoken>
```

Щоразу:

```
# 1. Docker Desktop запущений
docker compose up -d                                   # сервіс на 127.0.0.1:8000
ngrok http --domain=<домен>.ngrok-free.dev 8000        # у ngrok ≥ 3.16 також --url=
```

Перевірка ззовні:

```
curl https://<домен>.ngrok-free.dev/health             # {"status":"ok"}
```

- Адресу `https://<домен>.ngrok-free.dev` backend ставить у `AI_SERVICE_URL` **один раз** — вона не змінюється.
- `INTERNAL_KEY` у `.env` — довгий випадковий рядок (`python -c "import secrets; print(secrets.token_urlsafe(32))"`),
  бо сервіс видно з інтернету. Те саме значення backend ставить у `AI_INTERNAL_KEY`.
- Authtoken ngrok, `AI_KEY` і `INTERNAL_KEY` не комітити й не показувати на скріншотах.
- Поки сервіс потрібен backend: ноут увімкнений і не спить, Docker і термінал з `ngrok` працюють.
  Інакше backend отримує помилку і показує запасний текст — це очікувано.
- Зупинка: `Ctrl+C` у терміналі ngrok, `docker compose down`.

## Для DevOps

- Образ: `sheltered/ai-service`, порт `8000`, healthcheck `GET /health`.
- Сервіс stateless: томів і БД немає, логи йдуть у stdout.
- У продакшені порт не публікується назовні. Бекенд звертається за адресою `http://ai-service:8000` у спільній мережі.
- Секрети (`INTERNAL_KEY`, `AI_KEY`) передаються змінними оточення або secret store, файл `.env` у репозиторій і в образ не потрапляє.
- Контейнер запускається від непривілейованого користувача.