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
| `alerts` | тривоги: опитування API тривог, ручна тривога, журнал | B2.6, B7 |

Також `push` (Web Push, B8) і `tutor` (проксі до AI-сервісу, B13). Ендпоінти доменів `packs`, `sync`, `rollcall`, `alerts`, `push`, `tutor` поки заглушки контракту (B4, `app/api/stub.py`): перевіряють автентифікацію й роль і відповідають `501 NOT_IMPLEMENTED`; успішні відповіді описані в OpenAPI з прикладами.

Залежності між шарами йдуть в один бік: `api → services → models`. Роутер не звертається до БД напряму, а сервіс нічого не знає про HTTP.

## Авторизація

Потрібна змінна `JWT_SECRET` (без значення за замовчуванням, див. `.env.example`; без неї не стартують ні API, ні Alembic). Access-токен — JWT HS256, 15 хв; refresh — випадковий рядок (у БД лише хеш), 30 днів, з ротацією (`rotated_at`; вихід, скидання PIN і відкликання родини — окремо, `revoked_at`). Повторне використання вже ротованого токена відкликає всю родину, крім повтору протягом `REFRESH_REUSE_GRACE_SECONDS` (300 с), якщо найновіший виданий з нього токен ще не використано: це загублена відповідь або друга вкладка, тож видається нова пара в тій самій родині, а раніше видані токени лишаються робочими. Користувач має `token_version`: access-токен несе `ver`, скидання PIN збільшує версію й відсікає всі раніше видані токени.

- **Дорослі** (вчитель, батьки, адмін; акаунти створює лише адміністрація): OAuth 2.0 Authorization Code + PKCE (S256). `POST /auth/authorize` (email, пароль, `code_challenge`) → `code` (60 с, одноразовий); `POST /auth/token` (`grant_type=authorization_code` + `code_verifier`, або `refresh_token`; JSON чи form) → токени; `POST /auth/logout`; `GET /auth/me`.
- **Учень**: `POST /auth/student/join` — код класу, імʼя, прізвище, PIN (4–6 цифр). Нового учня створює, наявного (збіг імені й прізвища в класі без урахування регістру, зайвих пробілів і варіантів апострофа) пускає за PIN. Імена зберігаються з NFKC-нормалізацією, пошук іде за `app_user.name_key`. Код класу нормалізується (верхній регістр, лише A-Z і 0-9, кириличні двійники латиниці замінюються; у БД є CHECK); термін його дії обмежує лише створення нових учнів, наявні входять і після нього, а для невідомого імені при простроченому коді відповідь така сама, як при хибному PIN (401). Скидання PIN відкликає всі refresh-токени учня. Вчитель класу чи адмін скидає PIN: `POST /classes/{class_id}/students/{student_id}/pin-reset`.
- **Батьки**: вчитель чи адмін видає код `POST /students/{id}/parent-link-codes` (7 днів), батьки вводять його в `POST /parent/link`.
- Адмін створює вчителів, батьків, адмінів: `POST /admin/users`.
- Блокування акаунтів немає (діти могли б блокувати однокласників); захист від підбору паролів і PIN — rate limiting запитів в епіку безпеки.
- Залежності доступу: `app/api/deps.py` (`get_current_user`, `require_roles`, `get_accessible_class`, `get_accessible_student`).

Перший адмін школи (школа має вже існувати в БД):

```
python -m app.cli create-admin --email admin@school.ua --name Імʼя --school-id <uuid>
```

Пароль запитується в терміналі; для скриптів є `--password`.

## OpenAPI

Контракт лежить у `docs/openapi.json` (з нього генеруються TS-типи для фронтенду). Після зміни API оновіть файл і закомітьте його; тест у `tests/test_db.py` падає, якщо файл розійшовся з кодом:

```
python -m app.cli export-openapi
```

Приклади запитів і відповідей лежать у схемах (`json_schema_extra.examples`) і в описі відповідей ендпоінтів; Swagger UI — `/docs`.

### TS-типи для фронтенду

Запускати з кореня репозиторію (пакети тягне `npx`, у `package.json` нічого не додається):

```
npx openapi-typescript docs/openapi.json -o frontend/src/shared/api/schema.d.ts
npx @stoplight/prism-cli mock docs/openapi.json
```

Перша команда генерує типи (`components["schemas"]["SyncEventsRequest"]` тощо; шлях — пропозиція, остаточний обирає фронтенд). Друга піднімає мок-сервер на `http://127.0.0.1:4010`, який віддає приклади з контракту, зокрема для ендпоінтів-заглушок, що на справжньому API поки відповідають `501`.

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

Періодичні задачі запускає окремий процес Celery beat (у Docker — окремий сервіс, рівно один екземпляр):

```
celery -A app.workers.celery_app beat -l info
```

- `alerts.poll` — кожні `ALERTS_POLL_INTERVAL_S` (30 с) опитує API тривог alerts.in.ua. Без `ALERTS_API_TOKEN` нічого не робить (лишається ручна кнопка «Тривога»).

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
- Інша адреса БД (наприклад, сервіс у CI): змінна `TEST_DATABASE_URL`.
