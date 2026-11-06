from functools import lru_cache
from importlib.metadata import version
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Єдине джерело версії — pyproject.toml (пакет встановлено через pip install -e).
APP_VERSION = version("sheltered-backend")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ShelterED API"
    # Профіль розгортання з ТЗ. shelter (локальний сервер укриття) відкладено.
    profile: Literal["cloud"] = "cloud"
    environment: Literal["dev", "test", "prod"] = "dev"
    # SHA коміту, який підставляє CI під час збірки образу.
    git_sha: str | None = None

    log_level: str = "INFO"
    log_format: Literal["json", "text"] = "text"

    cors_origins: list[str] = ["http://localhost:5173"]

    # HSTS (B15.2): заголовок лише для запитів, що прийшли по HTTPS (схема від uvicorn
    # `--proxy-headers`). Увімкнено в prod завжди, деінде — через HSTS_ENABLED.
    hsts_enabled: bool = False
    hsts_max_age_s: int = 31536000

    # SecretStr: пароль не з'явиться в repr/логах, значення — через .get_secret_value().
    database_url: SecretStr | None = None
    # Міграції Alembic — завжди через direct endpoint Neon.
    database_url_direct: SecretStr | None = None
    # Neon вимагає TLS; для локальної БД у Docker вимикаємо.
    database_ssl: bool = True
    db_pool_size: int = 5
    db_max_overflow: int = 5

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
    # Інтервал опитування (ліміт alerts.in.ua — 8–10 запитів на хвилину з IP).
    alerts_poll_interval_s: int = 30
    # Без успішного опитування довше за це джерело вважається недоступним (B7.6).
    alerts_source_stale_s: int = 300

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
    # Ліміти на кількість запитів користувача (рахується кожен запит, не лише невдалий):
    # ШІ-репетитор — на учня; QR-ретрансляція подій (`POST /sync/events` від вчителя) — на вчителя.
    rate_limit_tutor: int = 20
    rate_limit_tutor_window_s: int = 600
    rate_limit_qr_relay: int = 120
    rate_limit_qr_relay_window_s: int = 600

    # Строки зберігання (B15.1, docs/data-inventory.md; щоденна задача `retention.purge`).
    # Журнал подій: payload стирається, відхилені події видаляються (рядки прийнятих лишаються
    # для ідемпотентності). Має бути значно більшим за горизонт офлайну пристрою.
    retention_sync_event_days: int = 180
    # Прострочені refresh-токени й коди авторизації — через N днів після закінчення строку.
    retention_auth_days: int = 7
    retention_parent_link_code_days: int = 30
    retention_wellbeing_view_log_days: int = 365

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
    def alerts_polling_enabled(self) -> bool:
        return bool(self.alerts_api_token and self.alerts_api_token.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
