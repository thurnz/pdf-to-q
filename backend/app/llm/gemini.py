from __future__ import annotations

import logging
import time

from google import genai
from google.genai import errors, types

from app.config import Settings, get_settings
from app.llm.base import LLMError, LLMProvider, RateLimitError

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation using the official google-genai SDK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        if not self.settings.gemini_api_key:
            raise LLMError(
                "GEMINI_API_KEY is not configured in settings or environment."
            )
        if not self.settings.gemini_model:
            raise LLMError("GEMINI_MODEL is not configured in settings or environment.")

        self.model_name = self.settings.gemini_model
        self.client = genai.Client(api_key=self.settings.gemini_api_key)

    def generate_json(self, prompt: str, system: str | None = None) -> str:
        """Call Gemini model requesting JSON output, with exponential backoff on HTTP 429."""
        config_kwargs: dict[str, object] = {
            "response_mime_type": "application/json",
        }
        if system:
            config_kwargs["system_instruction"] = system

        config = types.GenerateContentConfig(**config_kwargs)

        max_attempts = 3
        backoff_seconds = 1.0

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )
                if not response.text:
                    raise LLMError("Gemini returned an empty response.")
                return response.text
            except errors.APIError as exc:
                is_not_found = (
                    exc.code == 404
                    or (exc.status and "NOT_FOUND" in exc.status)
                    or "404" in str(exc)
                    or "NOT_FOUND" in str(exc)
                )
                if is_not_found:
                    raise LLMError(
                        f"Model '{self.model_name}' not found or retired. Run scripts/list_models.py and update GEMINI_MODEL."
                    ) from exc

                is_rate_limit = (
                    exc.code == 429
                    or "429" in str(exc)
                    or (exc.status and "RESOURCE_EXHAUSTED" in exc.status)
                )
                if is_rate_limit:
                    if attempt == max_attempts:
                        raise RateLimitError(
                            f"Gemini rate limit exceeded after {max_attempts} attempts: {exc.message or exc}"
                        ) from exc
                    logger.warning(
                        "Gemini rate limit (429) hit on attempt %d of %d. Retrying in %.1fs...",
                        attempt,
                        max_attempts,
                        backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                raise LLMError(
                    f"Gemini API error ({exc.code}): {exc.message or exc}"
                ) from exc
            except Exception as exc:
                if isinstance(exc, (RateLimitError, LLMError)):
                    raise
                if "404" in str(exc) or "NOT_FOUND" in str(exc):
                    raise LLMError(
                        f"Model '{self.model_name}' not found or retired. Run scripts/list_models.py and update GEMINI_MODEL."
                    ) from exc
                if "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc):
                    if attempt == max_attempts:
                        raise RateLimitError(
                            f"Gemini rate limit exceeded after {max_attempts} attempts: {exc}"
                        ) from exc
                    logger.warning(
                        "Rate limit on attempt %d of %d. Retrying in %.1fs...",
                        attempt,
                        max_attempts,
                        backoff_seconds,
                    )
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                raise LLMError(
                    f"Unexpected error communicating with Gemini: {exc}"
                ) from exc

        raise LLMError("Failed to generate response after retry attempts.")
