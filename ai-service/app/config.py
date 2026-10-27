from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    AI_KEY: str                 # ключ API LLM
    LLM_BASE_URL: str           # OpenAI-сумісна адреса
    MODELS: str                 # модель за замовчуванням
    INTERNAL_KEY: str           # значення заголовка X-Internal-Key

    MOCK_LLM: bool = False
    MODEL_EXPLAIN: str | None = None   # explain і check для text (інакше MODELS)
    MODEL_FAST: str | None = None      # practice: завдання й підказки (інакше MODELS)
    LLM_TIMEOUT: float = 12.0           # секунди
    MODEL_OCR: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()