from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    AI_KEY: str = "ollama"
    LLM_BASE_URL: str = 'http://localhost:11434/v1'
    MODELS: str = "deepseek-r1"

    INTERNAL_KEY: str = "super-secret-internal-key"

    MOCK_LLM: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()