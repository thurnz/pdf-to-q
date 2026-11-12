from __future__ import annotations

from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Sequence

from pydantic import ValidationError

from app.llm.base import LLMError, LLMProvider
from app.schemas import GenerationOptions, QAGenerationResult, QAItem

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHARS = 60000
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class DocumentTooLongError(ValueError):
    """Raised when the document text exceeds the maximum character budget for a single LLM call."""

    pass


class QAValidationError(LLMError):
    """Raised when the LLM repeatedly fails to return valid, schema-compliant JSON."""

    pass


@lru_cache(maxsize=1)
def load_prompt_templates() -> tuple[str, str]:
    """Load system and user prompt templates from text files."""
    system_path = PROMPTS_DIR / "qa_system.txt"
    user_path = PROMPTS_DIR / "qa_user.txt"

    if not system_path.exists():
        raise FileNotFoundError(f"Missing system prompt template: {system_path}")
    if not user_path.exists():
        raise FileNotFoundError(f"Missing user prompt template: {user_path}")

    return system_path.read_text(encoding="utf-8"), user_path.read_text(
        encoding="utf-8"
    )


def _strip_code_fences(raw_text: str) -> str:
    """Strip optional Markdown code fences (e.g. ```json ... ```) from model output."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop opening fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        # Drop closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def build_document_text(pages: Sequence[tuple[int, str]]) -> str:
    """Build grounded document text with [Page N] markers before each page's content."""
    sections: list[str] = []
    for page_num, text in pages:
        stripped = text.strip()
        if stripped:
            sections.append(f"[Page {page_num}]\n{stripped}")
    return "\n\n".join(sections)


def generate_qa(
    pages: Sequence[tuple[int, str]],
    options: GenerationOptions,
    provider: LLMProvider,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[QAItem]:
    """Generate study-guide Q&A items from extracted PDF pages using the configured LLMProvider.

    Args:
        pages: Sequence of (page_number, text) tuples.
        options: Generation parameters (num_questions, difficulty, detail).
        provider: An implementation of LLMProvider.
        max_chars: Maximum character limit for the combined document text.

    Returns:
        list[QAItem]: Deduplicated, non-empty question-and-answer items.

    Raises:
        DocumentTooLongError: If document text exceeds max_chars.
        QAValidationError: If LLM output fails schema validation across retries.
    """
    doc_text = build_document_text(pages)
    if not doc_text:
        return []

    if len(doc_text) > max_chars:
        raise DocumentTooLongError(
            f"Document text length ({len(doc_text)} chars) exceeds maximum allowed limit "
            f"of {max_chars} chars before chunking."
        )

    system_template, user_template = load_prompt_templates()

    # Fill template using strict str.replace to prevent issues with braces in document text
    user_prompt = (
        user_template.replace("{num_questions}", str(options.num_questions))
        .replace("{difficulty}", options.difficulty)
        .replace("{detail}", options.detail)
        .replace("{document}", doc_text)
    )

    max_retries = 2
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            raw_response = provider.generate_json(
                prompt=user_prompt, system=system_template
            )
            cleaned_json = _strip_code_fences(raw_response)
            parsed_data = json.loads(cleaned_json)
            result = QAGenerationResult.model_validate(parsed_data)

            # Deduplicate questions and discard empty entries
            seen_questions: set[str] = set()
            cleaned_items: list[QAItem] = []

            for item in result.questions:
                q = item.question.strip()
                a = item.answer.strip()
                if not q or not a:
                    continue

                # Case and whitespace-insensitive deduplication
                normalized_q = " ".join(q.lower().split())
                if normalized_q in seen_questions:
                    continue

                seen_questions.add(normalized_q)
                cleaned_items.append(QAItem(question=q, answer=a, page=item.page))

            logger.info(
                "Successfully generated and validated %d Q&A items (attempt %d).",
                len(cleaned_items),
                attempt + 1,
            )
            return cleaned_items

        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Failed to parse or validate LLM Q&A response on attempt %d of %d: %s",
                attempt + 1,
                max_retries + 1,
                type(exc).__name__,
            )
            if attempt < max_retries:
                continue

    raise QAValidationError(
        f"Failed to generate valid Q&A items after {max_retries + 1} attempts: {last_error}"
    ) from last_error
