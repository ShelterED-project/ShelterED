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

Також `push` (Web Push, B8) і `tutor` (проксі до AI-сервісу, B13). Ендпоінти `tutor` поки заглушки контракту (B4, `app/api/stub.py`): перевіряють автентифікацію й роль і відповідають `501 NOT_IMPLEMENTED`; успішні відповіді описані в OpenAPI з прикладами.

Залежності між шарами йдуть в один бік: `api → services → models`. Роутер не звертається до БД напряму, а сервіс нічого не знає про HTTP.

## Авторизація

Потрібна змінна `JWT_SECRET` (без значення за замовчуванням, див. `.env.example`; без неї не стартують ні API, ні Alembic). Access-токен — JWT HS256, 15 хв; refresh — випадковий рядок (у БД лише хеш), 30 днів, з ротацією (`rotated_at`; вихід, скидання PIN і відкликання родини — окремо, `revoked_at`). Повторне використання вже ротованого токена відкликає всю родину, крім повтору протягом `REFRESH_REUSE_GRACE_SECONDS` (300 с), якщо найновіший виданий з нього токен ще не використано: це загублена відповідь або друга вкладка, тож видається нова пара в тій самій родині, а раніше видані токени лишаються робочими. Користувач має `token_version`: access-токен несе `ver`, скидання PIN збільшує версію й відсікає всі раніше видані токени.

- **Дорослі** (вчитель, батьки, адмін; акаунти створює лише адміністрація): OAuth 2.0 Authorization Code + PKCE (S256). `POST /auth/authorize` (email, пароль, `code_challenge`) → `code` (60 с, одноразовий); `POST /auth/token` (`grant_type=authorization_code` + `code_verifier`, або `refresh_token`; JSON чи form) → токени; `POST /auth/logout`; `GET /auth/me`.
- **Учень**: `POST /auth/student/join` — код класу, імʼя, прізвище, PIN (4–6 цифр). Нового учня створює, наявного (збіг імені й прізвища в класі без урахування регістру, зайвих пробілів і варіантів апострофа) пускає за PIN. Імена зберігаються з NFKC-нормалізацією, пошук іде за `app_user.name_key`. Код класу нормалізується (верхній регістр, лише A-Z і 0-9, кириличні двійники латиниці замінюються; у БД є CHECK); термін його дії обмежує лише створення нових учнів, наявні входять і після нього, а для невідомого імені при простроченому коді відповідь така сама, як при хибному PIN (401). Скидання PIN відкликає всі refresh-токени учня. Вчитель класу чи адмін скидає PIN: `POST /classes/{class_id}/students/{student_id}/pin-reset`.
- **Батьки**: вчитель чи адмін видає код `POST /students/{id}/parent-link-codes` (7 днів), батьки вводять його в `POST /parent/link`.
- Адмін створює вчителів, батьків, адмінів: `POST /admin/users`.
- Блокування акаунтів немає (діти могли б блокувати однокласників). Захист від підбору PIN і паролів — rate limiting невдалих спроб (`app/core/rate_limit.py`, Redis БД 2): `POST /auth/student/join` — на пару IP + (код класу + ім'я) (`RATE_LIMIT_JOIN_ACCOUNT`, 10) і на IP (`RATE_LIMIT_JOIN_IP`, 300), `POST /auth/authorize` — на пару IP + email і на IP (`RATE_LIMIT_LOGIN_*`, 10 / 300); для обох — ще загальний ліміт на акаунт з усіх IP (`RATE_LIMIT_*_ACCOUNT_ALL_IPS`, 100) проти перебору зі зміною IP. Ключ акаунта містить IP, тож однокласник, що перебирає чужий PIN, блокує лише себе, а власник входить з іншого IP; ліміт на IP високий, бо клас чи школа часто за одним NAT, фіксоване вікно `RATE_LIMIT_WINDOW_S` (900 с). Понад ліміт — 429 `RATE_LIMITED` з `Retry-After`; успішні входи не рахуються. Redis недоступний — вхід дозволено (fail-open) з попередженням у лог. `POST /auth/token` не обмежується: `code` і refresh-токен — випадкові рядки, які не підібрати. За Nginx справжній IP — через `uvicorn --proxy-headers` і `FORWARDED_ALLOW_IPS` (IP чи підмережа Nginx; у Dockerfile за замовчуванням лише localhost), інакше всі клієнти ділять лічильники IP Nginx.
- Ліміт запитів (рахується кожен, `enforce` у `app/core/rate_limit.py`): `POST /tutor/ask` — на учня (`RATE_LIMIT_TUTOR`, 20 за `RATE_LIMIT_TUTOR_WINDOW_S` 600 с), `POST /sync/events` від вчителя (QR-ретрансляція) — на вчителя (`RATE_LIMIT_QR_RELAY`, 120 за 600 с). Створення нових учнів у `POST /auth/student/join` — на пару IP + клас (`RATE_LIMIT_JOIN_NEW_STUDENTS`, 40 за `RATE_LIMIT_JOIN_NEW_STUDENTS_WINDOW_S` 900 с): хто знає код класу, не засипле клас вигаданими іменами, а весь клас за одним шкільним NAT входить; вхід наявних учнів не рахується. Ліміт перевіряється до відповіді 501 заглушок; синхронізація учня не обмежується. Понад ліміт — 429 `RATE_LIMITED` з `Retry-After`.
- Заголовки безпеки (`app/core/security_headers.py`): на всіх відповідях `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`; на `/auth/*` — `Cache-Control: no-store`. `Strict-Transport-Security: max-age=HSTS_MAX_AGE_S` — лише якщо `HSTS_ENABLED=true` або `ENVIRONMENT=prod` і запит прийшов по HTTPS (схему ставить `uvicorn --proxy-headers` за `X-Forwarded-Proto` від довіреного Nginx). Редирект HTTP→HTTPS і HSTS для фронтенду — у Nginx.
- Видалення даних учня (B15.5): батьки дитини або адміністрація школи створюють запит `POST /students/{id}/deletion-requests` (`id` від клієнта, причина — лише з переліку), адміністрація школи бачить `GET /deletion-requests?status=pending` і вирішує `POST /deletion-requests/{id}/confirm` (безповоротне видалення учня й усіх його даних каскадом, ідемпотентно) або `/reject`; батьки бачать статус своїх запитів у `GET /deletion-requests`. Журнал `data_deletion_log` — без персональних даних. Інвентаризація даних і строки зберігання — `docs/data-inventory.md`.
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
- `packs.refresh_all` — кожні `PACKS_REFRESH_INTERVAL_S` (1 год) перезбирає пакети «Рюкзака» всіх класів на 7 днів наперед. Перезбірку після публікації уроку чи зміни розкладу API ставить одразу (`packs.rebuild_for_lesson`, `packs.rebuild_class`); без змін вмісту нова версія не створюється.
- `stats.refresh_all` — кожні `STATS_REFRESH_INTERVAL_S` (1 год) перераховує агрегати кабінетів (B14) усіх учнів і класів і навчання під час тривог шкіл (за `STATS_ALERT_LOOKBACK_DAYS`): новий день у розкладі, зміни уроків, пропущені задачі. Після кожного пакета синхронізації з прийнятими подіями API одразу ставить `stats.recompute_student` (рядки учня), а та — відкладений на `STATS_CLASS_DEBOUNCE_S` `stats.recompute_class` (один в очікуванні на клас).
- `retention.purge` — щодня о 02:00 UTC: строки зберігання (`RETENTION_*`, `docs/data-inventory.md`) — payload `sync_event` старших за 180 днів стирається, відхилені події видаляються; прострочені refresh-токени й коди авторизації (через 7 днів), коди прив'язки батьків (через 30 днів), журнал переглядів «Як ти зараз?» (365 днів).

## Docker-образ

`Dockerfile` збирає один образ (Python 3.13, користувач без root, лише runtime-залежності з `pyproject.toml`, `ENVIRONMENT=prod` за замовчуванням, тож `/docs` вимкнено) для всіх процесів — команду задає compose:

- API: команда за замовчуванням (`uvicorn ... --proxy-headers`), порт 8000, перевірка `GET /health` (живий) і `GET /health/ready` (БД і Redis);
- міграції перед стартом API: `alembic upgrade head` (потрібен `DATABASE_URL_DIRECT`);
- воркер: `celery -A app.workers.celery_app worker -Q default,push,sync -l info`;
- beat (рівно один): `celery -A app.workers.celery_app beat -l info -s /tmp/celerybeat-schedule`.

Обов'язкові змінні: `DATABASE_URL`, `DATABASE_URL_DIRECT` (для міграцій), `JWT_SECRET`, `REDIS_URL`, `REDIS_RESULT_URL`, `RATE_LIMIT_REDIS_URL` (усі три Redis-URL за замовчуванням дивляться на `localhost:6380`, у контейнері їх треба задати), для push — `VAPID_*`. `FORWARDED_ALLOW_IPS` — IP чи підмережа Nginx. Медіа пишуться в `/app/media` — туди монтується том, який роздає Nginx. `.env` в образ не потрапляє (`.dockerignore`).

## Медіа

`PUT /media/{id}` пише файл у том (`MEDIA_ROOT`, у контейнері `/app/media`) під ключем `<kind>/<id>-<random>.<ext>`; URL — `MEDIA_URL_PREFIX` + ключ. Зображення зберігаються як WebP (≤ 1280 px, без EXIF/GPS), тож `mime_type` зображення зазвичай `image/webp`. Однаковий вміст зберігається один раз: кілька записів можуть посилатися на один файл.

**Для DevOps (Nginx).** URL медіа незмінні: кожен файл має унікальний ключ і ніколи не перезаписується (нова версія — новий ключ). Тому `location /media/` можна кешувати назавжди (`immutable`) і обов'язково лишити Range-запити (докачування після обриву мережі; у Nginx для статики вони ввімкнені за замовчуванням, `max_ranges` не обмежувати). Готовий блок (шлях `alias` — куди в контейнер Nginx змонтовано той самий том):

```nginx
location /media/ {
    alias /srv/media/;              # том, який у бекенді змонтовано в /app/media
    # Без `always`: 404 не має кешуватися на рік. Увага: add_header тут скасовує заголовки,
    # успадковані з server (HSTS тощо), — їх треба повторити в цьому блоці.
    add_header Cache-Control "public, max-age=31536000, immutable";
    add_header X-Content-Type-Options "nosniff" always;
    etag on;
    autoindex off;
}
```

## Web Push (VAPID)

Пуші (тривога, відбій, «Рюкзак оновився», статус дитини в перекличці для батьків) підписуються ключами VAPID. Нова пара ключів:

```
python -m app.cli gen-vapid
```

Команда лише друкує `VAPID_PUBLIC_KEY` і `VAPID_PRIVATE_KEY` (у файли не пише). Скопіюй їх у `.env` (локально) чи в секрети розгортання разом із `VAPID_SUBJECT=mailto:<контакт>`. Приватний ключ нікуди більше не потрапляє: не в репозиторій, не в логи. Без ключів `GET /push/vapid-key` відповідає `503 PUSH_NOT_CONFIGURED`, а задачі `push.*` пропускають відправку з попередженням.

Ротація: нова пара ключів робить недійсними всі наявні підписки браузерів (вони прив'язані до публічного ключа). Після заміни ключів клієнт має перепідписатися: отримати новий ключ з `GET /push/vapid-key`, викликати `pushManager.subscribe` і `POST /push/subscriptions`; старі підписки push-сервіси відхилять (403/410), а 404/410 бекенд видаляє сам. Ротувати лише за потреби (витік ключа).

Відправка: `push.send` (черга `push`) визначає одержувачів і ставить `push.deliver` на кожну підписку; повтори 429/5xx з відступом (до 5 разів), дедуплікація в Redis (див. `app/workers/push.py`).

## Демо-дані (seed)

```
python -m app.cli seed
```

Ідемпотентно: фіксовані id (uuid5), upsert лише змінених рядків — повторний запуск того самого дня нічого не змінює. У `ENVIRONMENT=prod` команда відмовляє. Пише в БД з `DATABASE_URL` — перевір, куди вона дивиться.

- Школа в Києві (`region_code` 31), класи **5-А** (код `KYIV5A26`) і **7-Б** (`KYIV7B26`), по 12 учнів, PIN усіх учнів `1234` (вхід: код класу + ім'я й прізвище з `app/seed/content.py`, наприклад «Марія Бондаренко» в 5-А).
- Дорослі: `demo.admin@example.com`, `demo.teacher5a@example.com`, `demo.teacher7b@example.com`, `demo.parent1..4@example.com` (батьки Марії Бондаренко, Івана Петренка — 5-А; Олександра Гончаренка, Михайла Бойка — 7-Б). Пароль спільний: зі змінної `SEED_PASSWORD` (≥ 8 символів, застосовується до всіх, у кого він інший, з відкликанням токенів) або згенерований і надрукований один раз при створенні акаунтів; у репозиторії його немає. Повторний запуск без `SEED_PASSWORD` паролі не змінює.
- Предмети, розклад Пн–Пт (5–6 уроків з 08:30), 15 опублікованих уроків за модельними програмами НУШ (8 для 5 класу, 7 для 7 класу; укриття + основна частина, 2–3 модулі, тест), із них 4 тести з вікном (24/48 год), решта тренувальні. Уроки призначені на поточний і наступний тиждень, пакети «Рюкзака» обох класів перезбираються на 7 днів.
- Закрита тренувальна тривога 5-А за попередній навчальний день і перекличка з 7 відмітками. Відповідей «Як ти зараз?» немає.

## Тести

Тести з БД ходять у окрему PostgreSQL 17 у Docker (порт 5433, дані в tmpfs), **ніколи не в Neon**: `tests/conftest.py` підміняє `DATABASE_URL` до імпорту застосунку.

```
docker compose -f docker-compose.dev.yml up -d --wait test-db
pytest
ruff check . && ruff format --check .
```

- Міграції накочуються один раз за запуск (`migrated_db`).
- Фікстура `db_session` відкриває транзакцію й відкочує її після тесту — навіть `commit()` у коді, що тестується, не залишає слідів.
- Фікстура `committed` — без обгортки-транзакції: справжні commit-и й окреме з'єднання на кожен запит (паралельні пакети синхронізації, збій посеред пакета, стрічка змін); після тесту всі таблиці очищуються `TRUNCATE`.
- Rate limiter у тестах — у пам'яті (`MemoryRateLimiter`); тест справжнього Redis (порт 6380) пропускається, якщо Redis не запущено.
- Async-тести позначаються `pytestmark = pytest.mark.anyio`.
- Інша адреса БД (наприклад, сервіс у CI): змінна `TEST_DATABASE_URL`.
