from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for all LLM provider errors."""

    pass


class RateLimitError(LLMError):
    """Raised when an LLM provider encounters a 429 rate limit or quota exhaustion."""

    pass


class LLMProvider(ABC):
    """Abstract interface for LLM provider implementations."""

    @abstractmethod
    def generate_json(self, prompt: str, system: str | None = None) -> str:
        """Send prompt to the LLM and return the raw JSON text response.

        Args:
            prompt: User prompt content.
            system: Optional system instruction/prompt.

        Returns:
            str: Raw JSON string from the model.

        Raises:
            RateLimitError: If rate-limited (HTTP 429) or quota is exhausted.
            LLMError: If another provider failure occurs.
        """
        pass
