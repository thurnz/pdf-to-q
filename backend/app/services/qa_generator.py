from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import lru_cache
import json
import logging
from pathlib import Path
import time

from pydantic import ValidationError

from app.llm.base import LLMError, LLMProvider
from app.schemas import GenerationOptions, QAGenerationResult, QAItem
from app.services.chunking import DEFAULT_CHUNK_MAX_CHARS, chunk_pages

logger = logging.getLogger(__name__)

DEFAULT_MAX_CHUNKS = 12
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class DocumentTooLongError(ValueError):
    """Raised when the document text exceeds the maximum chunk capacity."""

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
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
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


def distribute_questions(
    chunk_lengths: Sequence[int],
    total_questions: int,
) -> list[int]:
    """Split total_questions across chunks proportional to text length.

    Each chunk receives at least 1 question. Total distributed questions will
    not exceed total_questions * 1.10 (or len(chunk_lengths) if there are more
    chunks than questions).
    """
    num_chunks = len(chunk_lengths)
    if num_chunks == 0:
        return []
    if num_chunks == 1:
        return [total_questions]

    total_len = sum(chunk_lengths)
    if total_len == 0:
        base = max(1, total_questions // num_chunks)
        return [base] * num_chunks

    # Proportional targets
    allocations = [
        max(1, round((length / total_len) * total_questions))
        for length in chunk_lengths
    ]

    current_sum = sum(allocations)
    max_allowed = max(num_chunks, int(total_questions * 1.10))

    # Cap: if total exceeds max_allowed, trim from largest allocations > 1
    while current_sum > max_allowed:
        max_idx = -1
        max_val = 1
        for idx, val in enumerate(allocations):
            if val > max_val:
                max_val = val
                max_idx = idx
        if max_idx == -1:
            break
        allocations[max_idx] -= 1
        current_sum -= 1

    # Floor: if total < total_questions, add to chunks with largest deficit
    while current_sum < total_questions:
        best_idx = 0
        best_deficit = float("-inf")
        for idx, length in enumerate(chunk_lengths):
            target = (length / total_len) * total_questions
            deficit = target - allocations[idx]
            if deficit > best_deficit:
                best_deficit = deficit
                best_idx = idx
        allocations[best_idx] += 1
        current_sum += 1

    return allocations


def _generate_qa_single_chunk(
    doc_text: str,
    options: GenerationOptions,
    provider: LLMProvider,
    system_template: str,
    user_template: str,
    max_retries: int = 2,
) -> list[QAItem]:
    """Execute LLM call for a single chunk of text and validate JSON response."""
    user_prompt = (
        user_template.replace("{num_questions}", str(options.num_questions))
        .replace("{difficulty}", options.difficulty)
        .replace("{detail}", options.detail)
        .replace("{document}", doc_text)
    )

    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            raw_response = provider.generate_json(
                prompt=user_prompt, system=system_template
            )
            cleaned_json = _strip_code_fences(raw_response)
            parsed_data = json.loads(cleaned_json)
            result = QAGenerationResult.model_validate(parsed_data)

            cleaned_items: list[QAItem] = []
            for item in result.questions:
                q = item.question.strip()
                a = item.answer.strip()
                if q and a:
                    cleaned_items.append(QAItem(question=q, answer=a, page=item.page))

            logger.info(
                "Validated %d Q&A items for chunk (attempt %d).",
                len(cleaned_items),
                attempt + 1,
            )
            return cleaned_items

        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "Failed to parse or validate LLM response on attempt %d of %d: %s",
                attempt + 1,
                max_retries + 1,
                type(exc).__name__,
            )
            if attempt < max_retries:
                continue

    raise QAValidationError(
        f"Failed to generate valid Q&A items after {max_retries + 1} attempts: {last_error}"
    ) from last_error


def _page_sort_key(item: QAItem) -> tuple[int, int]:
    """Sort key for QAItems: known pages first (ascending), None pages last."""
    if item.page is None:
        return (1, 0)
    return (0, item.page)


def generate_qa(
    pages: Sequence[tuple[int, str]],
    options: GenerationOptions,
    provider: LLMProvider,
    chunk_max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    chunk_delay_seconds: float = 0.0,
    on_progress: Callable[[int, int], None] | None = None,
    max_chars: int | None = None,
) -> list[QAItem]:
    """Generate study-guide Q&A items from extracted PDF pages.

    Supports single-chunk and multi-chunk map-reduce generation.

    Args:
        pages: Sequence of (page_number, text) tuples.
        options: Generation parameters (num_questions, difficulty, detail).
        provider: An implementation of LLMProvider.
        chunk_max_chars: Character limit per chunk (default 30,000).
        max_chunks: Maximum number of chunks allowed before raising DocumentTooLongError.
        chunk_delay_seconds: Optional pause between sequential chunk LLM calls.
        on_progress: Optional callback invoked as on_progress(chunk_index, total_chunks).
        max_chars: Backward-compatible alias for chunk_max_chars.

    Returns:
        list[QAItem]: Deduplicated, sorted, trimmed question-and-answer items.

    Raises:
        DocumentTooLongError: If chunk count exceeds max_chunks.
        QAValidationError: If LLM output fails schema validation across retries.
    """
    effective_chunk_max_chars = max_chars if max_chars is not None else chunk_max_chars

    chunks = chunk_pages(pages, max_chars=effective_chunk_max_chars)
    if not chunks:
        return []

    if len(chunks) > max_chunks:
        raise DocumentTooLongError(
            f"Document is too long (requires {len(chunks)} chunks, maximum is {max_chunks}). "
            "Please upload a smaller section or chapter."
        )

    system_template, user_template = load_prompt_templates()

    # Single-chunk path: fits in one call
    if len(chunks) == 1:
        doc_text = build_document_text(chunks[0])
        items = _generate_qa_single_chunk(
            doc_text=doc_text,
            options=options,
            provider=provider,
            system_template=system_template,
            user_template=user_template,
        )

        seen_questions: set[str] = set()
        deduped: list[QAItem] = []
        for item in items:
            norm_q = " ".join(item.question.lower().split())
            if norm_q not in seen_questions:
                seen_questions.add(norm_q)
                deduped.append(item)

        if on_progress:
            on_progress(0, 1)

        deduped.sort(key=_page_sort_key)
        return deduped[: options.num_questions]

    # Multi-chunk path: map-reduce sequentially
    chunk_texts = [build_document_text(c) for c in chunks]
    chunk_lengths = [len(t) for t in chunk_texts]
    allocations = distribute_questions(chunk_lengths, options.num_questions)

    all_items: list[QAItem] = []
    seen_questions = set()
    total_chunks = len(chunks)

    for i, (chunk_text, chunk_q_count) in enumerate(zip(chunk_texts, allocations)):
        chunk_options = GenerationOptions(
            num_questions=chunk_q_count,
            difficulty=options.difficulty,
            detail=options.detail,
        )

        chunk_items = _generate_qa_single_chunk(
            doc_text=chunk_text,
            options=chunk_options,
            provider=provider,
            system_template=system_template,
            user_template=user_template,
        )

        for item in chunk_items:
            norm_q = " ".join(item.question.lower().split())
            if norm_q not in seen_questions:
                seen_questions.add(norm_q)
                all_items.append(item)

        if on_progress:
            on_progress(i, total_chunks)

        if chunk_delay_seconds > 0 and i < total_chunks - 1:
            time.sleep(chunk_delay_seconds)

    all_items.sort(key=_page_sort_key)
    return all_items[: options.num_questions]
