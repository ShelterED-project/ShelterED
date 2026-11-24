from functools import lru_cache
from importlib.metadata import version
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Єдине джерело версії — pyproject.toml (пакет встановлено через pip install -e).
APP_VERSION = version("sheltered-backend")

# Мінімальна довжина секрету підпису JWT (HS256): 32 символи ≈ 256 біт для випадкового рядка.
JWT_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ShelterED API"
    # Профіль розгортання з ТЗ. shelter (локальний сервер укриття) відкладено.
    profile: Literal["cloud"] = "cloud"
    environment: Literal["dev", "test", "prod"] = "dev"
    # SHA коміту, який підставляє CI під час збірки образу.
    git_sha: str | None = None

    # Swagger UI (`/docs`), ReDoc (`/redoc`) і `/openapi.json`. За замовчуванням вимкнені в
    # prod (карта всіх ендпоінтів і схем — зайва інформація для атакувальника; контракт для
    # фронтенду — `docs/openapi.json` у репозиторії), увімкнені деінде. API_DOCS_ENABLED
    # перевизначає.
    api_docs_enabled: bool | None = None

    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    # Origin-и PWA. Авторизація лише Bearer-токеном (без cookie), тож CORS без credentials.
    # У prod — лише явні https-origin-и (без `*`).
    cors_origins: list[str] = ["http://localhost:5173"]

    # Найбільше тіло запиту (крім потокового завантаження медіа з власними лімітами), байти.
    # Пакет синхронізації зі 100 подій і урок з довгими текстами — сотні КБ.
    max_request_body_bytes: int = 1024 * 1024

    # HSTS (B15.2): заголовок лише для запитів, що прийшли по HTTPS (схема від uvicorn
    # `--proxy-headers`). Увімкнено в prod завжди, деінде — через HSTS_ENABLED.
    hsts_enabled: bool = False
    hsts_max_age_s: int = 31536000

    # SecretStr: пароль не з'явиться в repr/логах, значення — через .get_secret_value().
    database_url: SecretStr | None = None
    # Міграції Alembic — завжди через direct endpoint Neon.
    database_url_direct: SecretStr | None = None
    # TLS до БД. Не задано — авто: увімкнено для зовнішніх хостів (Neon), вимкнено для БД у
    # сусідньому контейнері чи локально (`db`, `localhost`, ім'я без крапки). Див. `use_db_ssl`.
    database_ssl: bool | None = None
    # Пул з'єднань на процес API: pool_size + max_overflow, помножене на кількість воркерів
    # uvicorn (і задач Celery, що працюють одночасно), має лишатися нижче за ліміт з'єднань Neon.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # Скільки секунд запит чекає на вільне з'єднання пулу, доки не отримає помилку (замість
    # того, щоб висіти до таймауту клієнта).
    db_pool_timeout_s: float = Field(default=10.0, gt=0)
    # Postgres рве з'єднання застосунку, що простоює у відкритій транзакції довше за цей час
    # (забутий commit не тримає блокувань і не будить Neon). 0 — вимкнено. Міграції (Alembic)
    # мають власне з'єднання без цього обмеження. З pooled endpoint Neon (`-pooler`, PgBouncer)
    # параметр не надсилається (він відкидає server_settings) — лише попередження в лозі.
    db_idle_in_transaction_timeout_s: int = Field(default=60, ge=0)

    # Секрет підпису JWT: обов'язковий, значення за замовчуванням немає.
    jwt_secret: SecretStr
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 30
    # Вікно, у якому повторне пред'явлення ротованого refresh-токена вважається повтором
    # через втрачену відповідь (обрив мережі, дві вкладки), а не крадіжкою.
    refresh_reuse_grace_seconds: int = 300
    auth_code_ttl_s: int = 60
    parent_link_code_ttl_days: int = 7
    # Дозволені client_id для OAuth 2.0 PKCE (PWA).
    oauth_client_ids: list[str] = ["sheltered-pwa"]
    # Дозволені `redirect_uri` (точний збіг). Код повертається в тілі відповіді, а не
    # редиректом, тож `redirect_uri` необов'язковий; якщо клієнт його надсилає — лише зі списку
    # (інакше 400 INVALID_REDIRECT_URI ще до перевірки пароля).
    oauth_redirect_uris: list[str] = []

    # Redis у Docker на 6380: 6379 на машині розробника займає нативний Redis.
    # БД 0 — брокер черг Celery, БД 1 — результати задач.
    redis_url: str = "redis://localhost:6380/0"
    redis_result_url: str = "redis://localhost:6380/1"

    # Медіа: локальний том (у Docker — volume, роздає Nginx за MEDIA_URL_PREFIX).
    media_root: str = "media"
    media_url_prefix: str = "/media"
    media_max_video_bytes: int = 30 * 1024 * 1024
    media_max_image_bytes: int = 2 * 1024 * 1024
    media_max_subtitles_bytes: int = 200 * 1024
    # Оригінал відео, яке стискає сервер (`PUT /media/{id}?kind=video_source`, імпорт з
    # Wikimedia Commons): браузер без WebCodecs не стисне сам. Результат стиснення має
    # вкластися в MEDIA_MAX_VIDEO_BYTES, інакше — `failed`.
    media_max_video_source_bytes: int = 300 * 1024 * 1024
    # ffmpeg для стиснення (у Docker-образі backend встановлено); час на одне відео.
    ffmpeg_path: str = "ffmpeg"
    media_video_process_timeout_s: int = 1500
    # Зображення перекодовуються у WebP: довша сторона ≤ max_side, без EXIF/GPS.
    # Більше пікселів — відмова ще до декодування (захист від «декомпресійних бомб»).
    media_image_max_side: int = 1280
    media_image_webp_quality: int = 80
    media_image_max_pixels: int = 40_000_000
    # Нижча межа для форматів, які декодуються в повному розмірі (PNG, WebP, прогресивний JPEG):
    # 24 Мп RGBA — ~96 МБ на запит. Звичайний JPEG декодується зменшеним (draft), йому — 40 Мп.
    media_image_max_pixels_full_decode: int = 24_000_000
    # Ліміт пакета класу на день; той самий ліміт діє на один урок.
    pack_max_day_bytes: int = 50 * 1024 * 1024
    # Ліміт «Рюкзака» класу на 7 днів (пакети + унікальні медіа). Перевищення лише логується:
    # блокує ліміт дня при прив'язці уроку (B5), а пакет із опублікованих уроків збирається завжди.
    pack_max_week_bytes: int = 200 * 1024 * 1024
    # Як часто Celery beat перезбирає пакети всіх класів на 7 днів наперед (новий день,
    # зміни розкладу, які не поставили перезбірку).
    packs_refresh_interval_s: int = 3600

    # API тривог (alerts.in.ua). Порожній токен — опитування вимкнене, лишається ручна кнопка.
    alerts_api_token: SecretStr | None = None
    alerts_api_url: str = "https://api.alerts.in.ua/v1/alerts/active.json"
    alerts_http_timeout_s: float = 10.0
    # Найбільша (розпакована) відповідь API тривог, байти; більша — збій джерела, не відбій.
    alerts_max_response_bytes: int = 2 * 1024 * 1024
    # Інтервал опитування (ліміт alerts.in.ua — 8–10 запитів на хвилину з IP).
    alerts_poll_interval_s: int = 30
    # Без успішного опитування довше за це джерело вважається недоступним (B7.6).
    alerts_source_stale_s: int = 300
    # Забуті ручні тривоги (зокрема навчальні) і ручні переклички без тривоги закриваються
    # автоматично через N год, якщо клас не покриває тривога з API (beat `alerts.auto_close`).
    alerts_manual_max_hours: int = 6
    alerts_auto_close_interval_s: int = 300

    # Синхронізація (docs/sync-protocol.md, розділ 6): подія «підозріла», якщо `occurred_at`
    # пізніше часу сервера або |зсув годинника пакета| більше за цей поріг. Позначка, не блокування.
    sync_suspicious_skew_s: int = 300
    # Допуск для `session_closed`: відмітка відхиляється, лише якщо і час пристрою, і час,
    # виправлений на зсув годинника пакета, пізніші за закриття переклички більш ніж на N с.
    sync_rollcall_close_grace_s: int = 120

    # Кабінети й агрегати (B14): тест «складено», якщо оцінка зарахованої спроби ≥ порогу (%);
    # «вікно закривається», якщо до дедлайну менше за N год; періодичний перерахунок (beat).
    stats_pass_score: int = 60
    stats_closing_soon_h: int = 6
    stats_refresh_interval_s: int = 3600
    # Перерахунок класу після синхронізації відкладається на N с і не дублюється: коли клас
    # синхронізується разом, задачі учнів ставлять один перерахунок класу.
    stats_class_debounce_s: int = 30
    # Навчання під час тривог (дашборд адміністрації): перераховуються тривоги за N днів.
    stats_alert_lookback_days: int = 14

    # Rate limiting входу (B15.3): рахуються лише невдалі спроби, фіксоване вікно, без
    # блокування акаунта. Redis БД 2 (0 і 1 — Celery); недоступний Redis — вхід дозволено.
    rate_limit_redis_url: str = "redis://localhost:6380/2"
    # Ліміт «на акаунт» рахується на пару (IP клієнта + акаунт): хто вводить хибні PIN чи паролі,
    # блокує лише себе, а не справжнього власника на іншому пристрої/IP (діти не можуть заблокувати
    # однокласника). Ліміт на IP високий: увесь клас чи школа часто за одним NAT.
    # Вхід учня: IP + код класу + ім'я (перебір PIN) і окремо IP.
    rate_limit_join_account: int = 10
    rate_limit_join_ip: int = 300
    # Вхід дорослих (POST /auth/authorize): IP + email і окремо IP.
    rate_limit_login_account: int = 10
    rate_limit_login_ip: int = 300
    # Загальний ліміт на акаунт (з усіх IP разом) проти перебору зі зміною IP. Високий: однокласник
    # руками стільки не набере; тимчасове обмеження на вікно, а не блокування акаунта.
    rate_limit_join_account_all_ips: int = 100
    rate_limit_login_account_all_ips: int = 100
    rate_limit_window_s: int = 900
    # Прив'язка батьків до дитини (`POST /parent/link`): невдалі коди на акаунт батьків і на IP
    # за RATE_LIMIT_WINDOW_S (перебір кодів прив'язки чужих дітей).
    rate_limit_parent_link: int = 10
    rate_limit_parent_link_ip: int = 100
    # Добовий ліміт невдалих входів учня на акаунт з усіх IP. PIN — 4–6 цифр (від 10 000
    # варіантів): лише 15-хвилинне вікно (100 спроб) дає перебір 4-значного PIN зі зміною IP
    # в середньому за ~12 год, з добовим лімітом — за ~17 днів. Компроміс: настирливий
    # однокласник із багатьох IP може заблокувати вхід учня до кінця доби (вчитель бачить це
    # й може скинути PIN; refresh-токен учня на його пристрої продовжує працювати).
    rate_limit_join_account_daily: int = 300
    rate_limit_daily_window_s: int = 86400
    # Створення нових учнів (`POST /auth/student/join` з новим ім'ям) на пару IP + клас: рахується
    # кожне створення. Код класу знають усі учні — без ліміту клас можна засипати вигаданими
    # іменами. Ліміт вищий за розмір класу: увесь клас може вперше входити з одного шкільного NAT.
    rate_limit_join_new_students: int = 40
    rate_limit_join_new_students_window_s: int = 900
    # Ліміти на кількість запитів користувача (рахується кожен запит, не лише невдалий):
    # ШІ-репетитор — на учня; QR-ретрансляція подій (`POST /sync/events` від вчителя) — на вчителя.
    rate_limit_tutor: int = 20
    rate_limit_tutor_window_s: int = 600
    rate_limit_qr_relay: int = 120
    rate_limit_qr_relay_window_s: int = 600
    # Імпорт медіа з Wikimedia Commons (`POST /media/import/commons`) — на вчителя.
    rate_limit_commons_import: int = 30
    rate_limit_commons_import_window_s: int = 600

    # AI-сервіс (ШІ-репетитор, docs/ai-contract.md): `POST {AI_SERVICE_URL}/ai/v1/chat` із
    # заголовком `X-Internal-Key`. Порожня адреса — репетитор вимкнений (503 AI_UNAVAILABLE,
    # клієнт показує пояснення з пакета). Ключ не логується.
    ai_service_url: str = ""
    ai_internal_key: SecretStr = SecretStr("")
    # Таймаут одного виклику, с; перевірка фото довша (спершу OCR, потім LLM).
    ai_timeout_s: float = Field(default=30.0, gt=0)
    ai_image_timeout_s: float = Field(default=45.0, gt=0)
    # Фото зошита в `POST /tutor/ask` (JPEG/PNG), байти після декодування base64.
    tutor_max_image_bytes: int = 4 * 1024 * 1024
    # Як часто beat шукає опубліковані уроки без закешованих пояснень (AI був недоступний).
    tutor_explanations_interval_s: int = 3600
    # Версія промпту пояснень: входить у ключ кешу пояснень (`tutor_explanation.cache_key`),
    # тож зміна генерує пояснення заново, а старі ключі стають невикористаними й прибираються.
    tutor_prompt_version: str = "1"

    # Wikimedia Commons: API і файли лише з https://*.wikimedia.org. User-Agent — назва
    # проєкту без контактів людей (політика Wikimedia вимагає описовий UA).
    commons_api_url: str = "https://commons.wikimedia.org/w/api.php"
    commons_user_agent: str = "ShelterED/1.0 (https://github.com/ShelterED-project/ShelterED)"
    commons_http_timeout_s: float = 20.0
    # Найбільша відповідь API (JSON метаданих), байти.
    commons_max_api_bytes: int = 1024 * 1024

    # Строки зберігання (B15.1, docs/data-inventory.md; щоденна задача `retention.purge`).
    # Журнал подій: payload стирається, відхилені події видаляються (рядки прийнятих лишаються
    # для ідемпотентності). Має бути значно більшим за горизонт офлайну пристрою.
    retention_sync_event_days: int = 180
    # Прострочені refresh-токени й коди авторизації — через N днів після закінчення строку.
    retention_auth_days: int = 7
    retention_parent_link_code_days: int = 30
    retention_wellbeing_view_log_days: int = 365
    # Розмови з ШІ-репетитором (завдання, підказки, останні 8 реплік) — від останньої активності.
    retention_tutor_conversation_days: int = 30
    # Закешовані пояснення ШІ, яких ніхто не брав N днів і на які не посилається жоден модуль
    # опублікованого уроку (за поточним ключем).
    retention_tutor_explanation_days: int = 90

    # Web Push (B8): пара ключів VAPID (`python -m app.cli gen-vapid`) і контакт `mailto:` для
    # push-сервісів. Не задано — відправка пропускається з попередженням у лог.
    vapid_public_key: str | None = None
    vapid_private_key: SecretStr | None = None
    vapid_subject: str | None = None
    # Пристроїв на користувача: понад ліміт найдавніші підписки видаляються.
    push_max_subscriptions_per_user: int = 10
    # Дозволені push-сервіси: хост endpoint підписки має збігатися із суфіксом або бути його
    # піддоменом. Chrome — FCM, Firefox — Mozilla autopush, Safari — Apple, Edge — WNS.
    push_allowed_host_suffixes: list[str] = [
        "fcm.googleapis.com",
        "push.services.mozilla.com",
        "push.apple.com",
        "notify.windows.com",
    ]

    # Демо-дані (`python -m app.cli seed`): спільний пароль дорослих (≥ 8 символів). Не задано —
    # генерується й друкується один раз при створенні акаунтів.
    seed_password: SecretStr | None = None

    @field_validator("database_url", "database_url_direct", mode="before")
    @classmethod
    def _async_driver(cls, value: object) -> object:
        # Застосунок асинхронний: `postgresql://` (як у docker-compose) → драйвер asyncpg.
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str):
            for prefix in ("postgresql://", "postgres://"):
                if raw.startswith(prefix):
                    raw = "postgresql+asyncpg://" + raw[len(prefix) :]
            # Рядок з Neon Console містить ?sslmode=…&channel_binding=… — asyncpg їх не знає
            # (TLS вмикаємо через connect_args), тож прибираємо.
            parts = urlsplit(raw)
            if parts.query:
                query = [
                    (k, v)
                    for k, v in parse_qsl(parts.query)
                    if k not in {"sslmode", "channel_binding"}
                ]
                raw = urlunsplit(parts._replace(query=urlencode(query)))
            return raw
        return value

    @field_validator("database_ssl", mode="before")
    @classmethod
    def _empty_ssl_is_auto(cls, value: object) -> object:
        # `DATABASE_SSL=` (як у .env.example) — авто, а не помилка розбору bool.
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def use_db_ssl(self) -> bool:
        """TLS до БД: явний DATABASE_SSL або авто за хостом."""
        if self.database_ssl is not None:
            return self.database_ssl
        url = self.database_url_direct or self.database_url
        if url is None:
            return False
        host = urlsplit(url.get_secret_value()).hostname or ""
        return host not in {"localhost", "127.0.0.1", "::1"} and "." in host

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_strong(cls, value: SecretStr) -> SecretStr:
        # `JWT_SECRET=` з `.env.example` дало б порожній ключ HS256: будь-хто підробив би токен.
        if len(value.get_secret_value()) < JWT_SECRET_MIN_LENGTH:
            raise ValueError(f"JWT_SECRET must be at least {JWT_SECRET_MIN_LENGTH} characters")
        return value

    @model_validator(mode="after")
    def _prod_requires_database(self) -> "Settings":
        # У prod без БД API не має стартувати «успішно» й падати 500 на кожному запиті.
        if self.environment == "prod" and not (
            self.database_url and self.database_url.get_secret_value()
        ):
            raise ValueError("DATABASE_URL is required when ENVIRONMENT=prod")
        return self

    @model_validator(mode="after")
    def _prod_cors_origins_https(self) -> "Settings":
        # У prod `*` відкрив би API будь-якому сайту, а http-origin — сторінці без TLS.
        if self.environment == "prod":
            bad = [o for o in self.cors_origins if o == "*" or not o.startswith("https://")]
            if bad:
                raise ValueError(
                    f"CORS_ORIGINS must list explicit https:// origins when ENVIRONMENT=prod: {bad}"
                )
        return self

    @property
    def api_docs_active(self) -> bool:
        if self.api_docs_enabled is not None:
            return self.api_docs_enabled
        return self.environment != "prod"

    @property
    def hsts_active(self) -> bool:
        return self.hsts_enabled or self.environment == "prod"

    @property
    def push_enabled(self) -> bool:
        return bool(
            self.vapid_public_key
            and self.vapid_private_key
            and self.vapid_private_key.get_secret_value()
            and self.vapid_subject
        )

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_service_url)

    @property
    def tutor_max_body_bytes(self) -> int:
        """Ліміт тіла `POST /tutor/ask`: фото в base64 (+1/3) і запас на решту полів."""
        return self.tutor_max_image_bytes * 4 // 3 + 64 * 1024

    @property
    def alerts_polling_enabled(self) -> bool:
        return bool(self.alerts_api_token and self.alerts_api_token.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
