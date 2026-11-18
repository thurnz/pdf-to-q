from __future__ import annotations

import logging
import random
import time

from google import genai
from google.genai import types

from app.config import Settings, get_settings
from app.llm.base import (
    LLMError,
    LLMProvider,
    ProviderUnavailableError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 404}
RETRYABLE_STATUS_CODES = {429, 500, 503}


def _extract_status_code(exc: Exception) -> int | None:
    """Extract HTTP status code from exc.code or exc.status_code."""
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    return None


def _extract_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After duration in seconds if provided by the API error."""
    retry_after = getattr(exc, "retry_after", None)
    if isinstance(retry_after, (int, float)):
        return float(retry_after)
    if isinstance(retry_after, str):
        try:
            return float(retry_after)
        except ValueError:
            pass

    response = getattr(exc, "response", None)
    if response is not None and hasattr(response, "headers"):
        headers = response.headers
        raw_val = None
        if hasattr(headers, "get"):
            raw_val = headers.get("retry-after") or headers.get("Retry-After")
        if raw_val is not None:
            try:
                return float(raw_val)
            except ValueError:
                pass

    return None


def _handle_call_error(
    exc: Exception,
    model: str,
    attempt: int,
    max_attempts: int,
) -> None:
    """Evaluate an exception, raising specific LLMError or returning for retry."""
    status_code = _extract_status_code(exc)

    # 404: specific informative error, never retry
    if status_code == 404:
        raise LLMError(
            f"Model '{model}' not found or retired. "
            "Run scripts/list_models.py and update GEMINI_MODEL."
        ) from exc

    # 400, 401, 403: client errors, never retry
    if status_code in NON_RETRYABLE_STATUS_CODES:
        raise LLMError(
            f"Gemini API error ({status_code}): {getattr(exc, 'message', None) or exc}"
        ) from exc

    # 429, 500, 503: retry with backoff
    if status_code in RETRYABLE_STATUS_CODES:
        if attempt >= max_attempts:
            if status_code == 429:
                raise RateLimitError(
                    f"Gemini rate limit exceeded after {attempt} attempts: "
                    f"{getattr(exc, 'message', None) or exc}"
                ) from exc
            raise ProviderUnavailableError(
                f"Gemini API error ({status_code}) after {attempt} attempts: "
                f"{getattr(exc, 'message', None) or exc}"
            ) from exc
        return

    raise LLMError(f"Unexpected error communicating with Gemini: {exc}") from exc


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation using the official google-genai SDK."""

    def __init__(
        self,
        settings: Settings | None = None,
        base_delay: float | None = None,
        max_attempts: int | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        if not self.settings.gemini_api_key:
            raise LLMError(
                "GEMINI_API_KEY is not configured in settings or environment."
            )
        if not self.settings.gemini_model:
            raise LLMError("GEMINI_MODEL is not configured in settings or environment.")

        self.model_name = self.settings.gemini_model
        self.fallback_model = (self.settings.gemini_fallback_model or "").strip()
        self.base_delay = (
            base_delay
            if base_delay is not None
            else self.settings.llm_retry_base_seconds
        )
        self.max_attempts = (
            max_attempts if max_attempts is not None else self.settings.llm_max_attempts
        )
        self.client = genai.Client(api_key=self.settings.gemini_api_key)

    def _call_model(
        self,
        model: str,
        prompt: str,
        config: types.GenerateContentConfig,
        max_attempts: int,
    ) -> str:
        for attempt in range(1, max_attempts + 1):
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )
                if not response.text:
                    raise LLMError("Gemini returned an empty response.")
                return response.text

            except Exception as exc:
                if isinstance(
                    exc, (RateLimitError, ProviderUnavailableError, LLMError)
                ):
                    raise

                _handle_call_error(exc, model, attempt, max_attempts)

                retry_after = _extract_retry_after(exc)
                if self.base_delay <= 0:
                    delay = 0.0
                elif retry_after is not None and retry_after >= 0:
                    delay = retry_after
                else:
                    backoff = self.base_delay * (2 ** (attempt - 1))
                    jitter = random.uniform(0.0, 0.5 * backoff)
                    delay = backoff + jitter

                status_code = _extract_status_code(exc)
                logger.warning(
                    "Gemini transient error (%s) on attempt %d of %d for model '%s'. Retrying in %.2fs...",
                    status_code,
                    attempt,
                    max_attempts,
                    model,
                    delay,
                )
                if delay > 0:
                    time.sleep(delay)

        raise LLMError("Failed to generate response after retry attempts.")

    def generate_json(self, prompt: str, system: str | None = None) -> str:
        """Call Gemini model requesting JSON output, with retries and optional fallback."""
        config_kwargs: dict[str, object] = {
            "response_mime_type": "application/json",
        }
        if system:
            config_kwargs["system_instruction"] = system

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            return self._call_model(
                self.model_name,
                prompt,
                config,
                max_attempts=self.max_attempts,
            )
        except (RateLimitError, ProviderUnavailableError) as primary_exc:
            if self.fallback_model and self.fallback_model != self.model_name:
                logger.info("Using fallback model %s", self.fallback_model)
                return self._call_model(
                    self.fallback_model,
                    prompt,
                    config,
                    max_attempts=1,
                )
            raise primary_exc
