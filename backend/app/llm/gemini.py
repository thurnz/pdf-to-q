from __future__ import annotations

import logging
import random
import time

from google import genai
from google.genai import errors, types

from app.config import Settings, get_settings
from app.llm.base import LLMError, LLMProvider, RateLimitError

logger = logging.getLogger(__name__)

NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}
RETRYABLE_STATUS_CODES = {429, 500, 503}


def _extract_status_code(exc: Exception) -> int | None:
    """Extract HTTP status code from APIError or exception message."""
    if isinstance(exc, errors.APIError) and isinstance(exc.code, int):
        return exc.code

    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code

    err_str = str(exc)
    for candidate in (404, 400, 401, 403, 429, 500, 503):
        if str(candidate) in err_str:
            return candidate

    if "NOT_FOUND" in err_str:
        return 404
    if "RESOURCE_EXHAUSTED" in err_str:
        return 429
    if "UNAVAILABLE" in err_str:
        return 503
    if "INTERNAL" in err_str:
        return 500

    return None


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation using the official google-genai SDK."""

    def __init__(
        self,
        settings: Settings | None = None,
        base_delay: float = 2.0,
    ) -> None:
        self.settings = settings or get_settings()
        if not self.settings.gemini_api_key:
            raise LLMError(
                "GEMINI_API_KEY is not configured in settings or environment."
            )
        if not self.settings.gemini_model:
            raise LLMError("GEMINI_MODEL is not configured in settings or environment.")

        self.model_name = self.settings.gemini_model
        self.base_delay = base_delay
        self.client = genai.Client(api_key=self.settings.gemini_api_key)

    def generate_json(self, prompt: str, system: str | None = None) -> str:
        """Call Gemini model requesting JSON output, with exponential backoff and jitter."""
        config_kwargs: dict[str, object] = {
            "response_mime_type": "application/json",
        }
        if system:
            config_kwargs["system_instruction"] = system

        config = types.GenerateContentConfig(**config_kwargs)

        max_attempts = 4

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

            except Exception as exc:
                if isinstance(exc, (RateLimitError, LLMError)):
                    raise

                status_code = _extract_status_code(exc)

                # 404: specific informative error, never retry
                if status_code == 404:
                    raise LLMError(
                        f"Model '{self.model_name}' not found or retired. "
                        "Run scripts/list_models.py and update GEMINI_MODEL."
                    ) from exc

                # 400, 401, 403: client errors, never retry
                if status_code in NON_RETRYABLE_STATUS_CODES:
                    raise LLMError(
                        f"Gemini API error ({status_code}): {getattr(exc, 'message', None) or exc}"
                    ) from exc

                # 429, 500, 503: retry with exponential backoff and jitter
                if status_code in RETRYABLE_STATUS_CODES:
                    if attempt == max_attempts:
                        if status_code == 429:
                            raise RateLimitError(
                                f"Gemini rate limit exceeded after {max_attempts} attempts: "
                                f"{getattr(exc, 'message', None) or exc}"
                            ) from exc
                        raise LLMError(
                            f"Gemini API error ({status_code}) after {max_attempts} attempts: "
                            f"{getattr(exc, 'message', None) or exc}"
                        ) from exc

                    if self.base_delay <= 0:
                        delay = 0.0
                    else:
                        backoff = self.base_delay * (2 ** (attempt - 1))
                        jitter = random.uniform(0.0, 0.5 * backoff)
                        delay = backoff + jitter

                    logger.warning(
                        "Gemini transient error (%s) on attempt %d of %d. Retrying in %.2fs...",
                        status_code,
                        attempt,
                        max_attempts,
                        delay,
                    )
                    if delay > 0:
                        time.sleep(delay)
                    continue

                raise LLMError(
                    f"Unexpected error communicating with Gemini: {exc}"
                ) from exc

        raise LLMError("Failed to generate response after retry attempts.")
