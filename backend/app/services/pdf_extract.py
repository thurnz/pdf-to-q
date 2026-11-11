from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

import pymupdf

logger = logging.getLogger(__name__)

DEFAULT_MIN_CHARS_PER_PAGE = 40


class PDFExtractionError(Exception):
    """Base exception for PDF text extraction failures."""

    pass


class ScannedPDFError(PDFExtractionError):
    """Raised when a PDF contains little or no extractable text (e.g. scanned image-only)."""

    pass


@dataclass(frozen=True)
class ExtractionResult:
    """Result of extracting text from all pages in a PDF document."""

    pages: list[tuple[int, str]]
    low_text_pages: list[int]
    total_pages: int

    @property
    def has_usable_text(self) -> bool:
        """True if the document has meaningful text on at least one page."""
        return len(self.low_text_pages) < self.total_pages

    @property
    def is_mostly_scanned(self) -> bool:
        """True if more than half of the pages contain almost no text."""
        if self.total_pages == 0:
            return True
        return (len(self.low_text_pages) / self.total_pages) >= 0.5

    def require_extractable_text(self) -> None:
        """Validate that the document has extractable text; raise ScannedPDFError if not."""
        if self.total_pages == 0:
            raise PDFExtractionError("PDF document contains no pages.")
        if not self.has_usable_text or self.is_mostly_scanned:
            raise ScannedPDFError(
                "Scanned PDF not supported yet: document contains little or no extractable text. "
                f"({len(self.low_text_pages)} of {self.total_pages} page(s) have insufficient text)"
            )


def extract_pdf_pages(
    pdf_input: bytes | Path | str,
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> ExtractionResult:
    """Extract text per page and detect pages with little or no readable text.

    Args:
        pdf_input: PDF file as raw bytes, a Path object, or a path string.
        min_chars_per_page: Threshold of non-whitespace characters below which
            a page is flagged as low-text / empty.

    Returns:
        ExtractionResult containing page tuples (1-based page number, text),
        the list of low-text page numbers, and total page count.

    Raises:
        PDFExtractionError: If the document is invalid or cannot be opened.
    """
    try:
        if isinstance(pdf_input, bytes):
            doc = pymupdf.open(stream=pdf_input, filetype="pdf")
        else:
            doc = pymupdf.open(Path(pdf_input))
    except Exception as exc:
        raise PDFExtractionError(f"Failed to open PDF: {exc}") from exc

    pages: list[tuple[int, str]] = []
    low_text_pages: list[int] = []

    try:
        total_pages = len(doc)
        for page_index in range(total_pages):
            page_num = page_index + 1
            page = doc[page_index]
            text = page.get_text("text").strip()
            pages.append((page_num, text))

            # Character count of non-whitespace content
            non_ws_count = len("".join(text.split()))
            if non_ws_count < min_chars_per_page:
                low_text_pages.append(page_num)

        logger.info(
            "Extracted %d page(s). Low text pages: %s",
            total_pages,
            low_text_pages or "none",
        )
        return ExtractionResult(
            pages=pages,
            low_text_pages=low_text_pages,
            total_pages=total_pages,
        )
    finally:
        doc.close()


def extract_text_per_page(
    pdf_input: bytes | Path | str,
) -> list[tuple[int, str]]:
    """Convenience helper returning just the list of (page_number, text) tuples."""
    result = extract_pdf_pages(pdf_input)
    return result.pages
