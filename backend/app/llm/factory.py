from __future__ import annotations

from app.config import get_settings
from app.llm.base import LLMError, LLMProvider
from app.llm.gemini import GeminiProvider


def get_provider() -> LLMProvider:
    """Instantiate and return the configured LLMProvider based on LLM_PROVIDER setting."""
    settings = get_settings()
    provider_name = settings.llm_provider.lower().strip()

    if provider_name == "gemini":
        return GeminiProvider(settings)

    raise LLMError(
        f"Unsupported LLM provider: '{settings.llm_provider}'. Supported providers: 'gemini'."
    )
