from pydantic_settings import BaseSettings,SettingsConfigDict

class Settings(BaseSettings):
    AI_KEY: str 
    LLM_BASE_URL: str
    MODELS: str 

    INTERNAL_KEY: str

    MOCK_LLM: bool

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()