from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_ALLOWED_ORIGINS: list[str] = ["http://localhost:5173"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""

    # Upload limits
    max_file_size_mb: int = 20
    max_page_count: int = 200

    # File retention (seconds)
    file_retention_seconds: int = 3600

    # CORS
    allowed_origins: Annotated[list[str], NoDecode] = DEFAULT_ALLOWED_ORIGINS

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError(
                "Set GEMINI_MODEL in .env (see Google AI Studio for current model names)"
            )
        return value.strip()

    @model_validator(mode="wrap")
    @classmethod
    def check_gemini_model_provided(cls, values: object, handler: object) -> Settings:
        try:
            return handler(values)  # type: ignore[no-any-return]
        except ValidationError as exc:
            for error in exc.errors():
                if error["loc"] == ("gemini_model",) and error["type"] == "missing":
                    raise ValueError(
                        "Set GEMINI_MODEL in .env (see Google AI Studio for current model names)"
                    ) from None
            raise

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: object) -> list[str]:
        if value is None:
            return DEFAULT_ALLOWED_ORIGINS
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return DEFAULT_ALLOWED_ORIGINS
            origins = [item.strip() for item in stripped.split(",") if item.strip()]
            return origins if origins else DEFAULT_ALLOWED_ORIGINS
        if isinstance(value, (list, tuple, set)):
            origins = [str(item).strip() for item in value if str(item).strip()]
            return origins if origins else DEFAULT_ALLOWED_ORIGINS
        return DEFAULT_ALLOWED_ORIGINS


@lru_cache
def get_settings() -> Settings:
    return Settings()
