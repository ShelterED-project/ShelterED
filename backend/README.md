# ShelterED Backend

Хмарний API ShelterED: FastAPI, PostgreSQL, Celery + Redis.

## Структура

```
app/
  api/       роутери FastAPI (HTTP-шар): приймають запит, віддають відповідь
  models/    SQLAlchemy-моделі (таблиці БД)
  schemas/   Pydantic-схеми (форма JSON на вході й виході)
  services/  бізнес-логіка; викликається і з роутерів, і з Celery-задач
  workers/   Celery-застосунок і фонові задачі
  core/      конфіг, БД, безпека, логування, помилки
```

## Домени

Код кожного домену лежить в однойменному файлі в потрібному шарі: `api/<домен>.py`, `services/<домен>.py`, `schemas/<домен>.py`, `models/<домен>.py`, `workers/<домен>.py`. Файл створюється тоді, коли до нього доходить задача, а не наперед.

| Домен | Відповідає за | Епіки плану |
|---|---|---|
| `auth` | вхід, JWT (access + refresh), OAuth 2.0 PKCE, ролі й перевірка доступу | B3, B15.3 |
| `school` | школи, класи, користувачі, членство, розклад | B2.1, B2.3, B5.1, B5.2 |
| `lessons` | предмети, уроки, модулі, картки, тести, медіа, тест із вікном | B2.2, B5.3, B5.4, B11 |
| `packs` | пакети знань «Рюкзак»: збірка, маніфест, завантаження | B2.4, B6 |
| `sync` | прийом подій `POST /sync/events`, `GET /sync/changes`, агрегати | B2.5, B9, B10 |
| `rollcall` | сесії й статуси переклички | B2.6, B12 |
| `alerts` | тривоги: вебхук від AI-сервісу, ручна тривога, журнал | B2.6, B7 |

Пізніше додаються `push` (Web Push, B8) і `tutor` (проксі до AI-сервісу, B13).

Залежності між шарами йдуть в один бік: `api → services → models`. Роутер не звертається до БД напряму, а сервіс нічого не знає про HTTP.

## Міграції (Alembic)

Усі зміни схеми — лише через міграції. Alembic підключається через `DATABASE_URL_DIRECT` (для Neon — direct endpoint, не `-pooler`).

```
alembic upgrade head                              # застосувати всі міграції
alembic revision --autogenerate -m "<опис>"        # нова міграція з різниці моделей і БД
alembic downgrade -1                              # відкотити останню
alembic current                                   # на якій ревізії зараз БД
```

Нові файли міграцій автоматично проходять `ruff check --fix` і `ruff format`.

Для CI (запускати з `backend/` після підняття тестової БД):

```
alembic upgrade head      # міграції застосовуються на чистій БД
alembic check             # моделі не мають змін без міграції
alembic downgrade base    # міграції відкочуються
```

## Фонові задачі (Celery + Redis)

Redis для розробки піднімається в Docker на порту **6380** (6379 часто зайнятий локальним Redis):

```
docker compose -f docker-compose.dev.yml up -d redis
celery -A app.workers.celery_app worker -Q default,push,sync -l info --pool=solo
```

`--pool=solo` потрібен лише на Windows (там Celery не підтримує стандартний prefork-пул); у Docker і на Linux цей прапорець не потрібен.

Черги: `default` — загальні, `push` — Web Push, `sync` — обробка подій синхронізації. Задачі підтверджуються після виконання (`acks_late`), тому кожна задача має бути ідемпотентною. Перевірка: `python -c "from app.workers.system import ping; print(ping.delay().get(timeout=10))"` → `pong`.

## Тести

Тести з БД ходять у окрему PostgreSQL 17 у Docker (порт 5433, дані в tmpfs), **ніколи не в Neon**: `tests/conftest.py` підміняє `DATABASE_URL` до імпорту застосунку.

```
docker compose -f docker-compose.dev.yml up -d --wait test-db
pytest
ruff check . && ruff format --check .
```

- Міграції накочуються один раз за запуск (`migrated_db`).
- Фікстура `db_session` відкриває транзакцію й відкочує її після тесту — навіть `commit()` у коді, що тестується, не залишає слідів.
- Async-тести позначаються `pytestmark = pytest.mark.anyio`.
- Інший адрес БД (наприклад, сервіс у CI): змінна `TEST_DATABASE_URL`.
