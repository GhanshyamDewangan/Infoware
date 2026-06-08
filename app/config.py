from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Groq
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # Database (Supabase PostgreSQL)
    DATABASE_URL: str  # postgresql+asyncpg://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres

    # App
    APP_NAME: str = "Sales Assistant Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Memory
    MEMORY_CONTEXT_LIMIT: int = 20   # max past messages to inject as context
    EVAL_CONFIDENCE_THRESHOLD: float = 0.70  # below this → flag_for_human

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
