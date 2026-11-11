from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.0-flash"
    gemini_api_key: str = ""
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""

    # Upload limits
    max_file_size_mb: int = 20
    max_page_count: int = 200

    # File retention (seconds)
    file_retention_seconds: int = 3600

    # CORS
    allowed_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
