from __future__ import annotations

from typing import Sequence

DEFAULT_CHUNK_MAX_CHARS = 30000


def _split_page_text(page_num: int, text: str, max_chars: int) -> list[tuple[int, str]]:
    """Split a page's text into paragraph-bounded sections not exceeding max_chars.

    Preserves the original page number for each resulting subsection.
    """
    stripped = text.strip()
    if len(stripped) <= max_chars:
        return [(page_num, stripped)] if stripped else []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if not paragraphs:
        return [(page_num, stripped[:max_chars])]

    pieces: list[str] = []
    current_piece: list[str] = []
    current_len = 0

    for para in paragraphs:
        # If a single paragraph is longer than max_chars, hard split it
        if len(para) > max_chars:
            if current_piece:
                pieces.append("\n\n".join(current_piece))
                current_piece = []
                current_len = 0
            for i in range(0, len(para), max_chars):
                sub = para[i : i + max_chars].strip()
                if sub:
                    pieces.append(sub)
            continue

        para_len = len(para) + (2 if current_piece else 0)
        if current_len + para_len > max_chars and current_piece:
            pieces.append("\n\n".join(current_piece))
            current_piece = [para]
            current_len = len(para)
        else:
            current_piece.append(para)
            current_len += para_len

    if current_piece:
        pieces.append("\n\n".join(current_piece))

    return [(page_num, p) for p in pieces if p]


def chunk_pages(
    pages: Sequence[tuple[int, str]],
    max_chars: int = DEFAULT_CHUNK_MAX_CHARS,
) -> list[list[tuple[int, str]]]:
    """Split (page_number, text) pairs into chunks on page boundaries, up to max_chars.

    If a single page exceeds max_chars, it is split at paragraph breaks while
    preserving its page number.

    Args:
        pages: Sequence of (page_number, text) pairs.
        max_chars: Maximum character budget per chunk (default 30,000).

    Returns:
        list[list[tuple[int, str]]]: List of chunks, where each chunk is a list
        of (page_number, text) pairs.
    """
    if not pages:
        return []

    # First expand any oversized pages into paragraph-level sub-pages
    normalized_pages: list[tuple[int, str]] = []
    for page_num, text in pages:
        stripped = text.strip()
        if not stripped:
            continue
        if len(stripped) > max_chars:
            normalized_pages.extend(_split_page_text(page_num, stripped, max_chars))
        else:
            normalized_pages.append((page_num, stripped))

    if not normalized_pages:
        return []

    chunks: list[list[tuple[int, str]]] = []
    current_chunk: list[tuple[int, str]] = []
    current_chunk_chars = 0

    for page_num, text in normalized_pages:
        page_chars = len(text)
        if current_chunk and (current_chunk_chars + page_chars > max_chars):
            chunks.append(current_chunk)
            current_chunk = [(page_num, text)]
            current_chunk_chars = page_chars
        else:
            current_chunk.append((page_num, text))
            current_chunk_chars += page_chars

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

