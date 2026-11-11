from __future__ import annotations

from pathlib import Path

import pytest

from app.services.pdf_extract import (
    PDFExtractionError,
    ScannedPDFError,
    extract_pdf_pages,
    extract_text_per_page,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MULTIPAGE_PDF_PATH = FIXTURES_DIR / "multipage_text.pdf"
SCANNED_EMPTY_PDF_PATH = FIXTURES_DIR / "scanned_empty.pdf"


def test_extract_text_multipage_path() -> None:
    """Extraction from a multi-page text PDF returns 1-indexed tuples and no low-text warnings."""
    result = extract_pdf_pages(MULTIPAGE_PDF_PATH)

    assert result.total_pages == 3
    assert len(result.pages) == 3
    assert result.low_text_pages == []
    assert result.has_usable_text is True
    assert result.is_mostly_scanned is False

    # Check page numbers and content
    for expected_page, (page_num, text) in enumerate(result.pages, start=1):
        assert page_num == expected_page
        assert f"page {expected_page}" in text.lower()
        assert "computer science" in text.lower()

    # Convenience wrapper returns identical page list
    tuples = extract_text_per_page(MULTIPAGE_PDF_PATH)
    assert tuples == result.pages


def test_extract_text_from_bytes() -> None:
    """Extraction works cleanly when given raw PDF bytes."""
    pdf_bytes = MULTIPAGE_PDF_PATH.read_bytes()
    result = extract_pdf_pages(pdf_bytes)

    assert result.total_pages == 3
    assert len(result.pages) == 3
    assert result.low_text_pages == []


def test_empty_scanned_pdf_detection() -> None:
    """Detects pages with no readable text and flags the document as scanned."""
    result = extract_pdf_pages(SCANNED_EMPTY_PDF_PATH)

    assert result.total_pages == 2
    assert result.low_text_pages == [1, 2]
    assert result.is_mostly_scanned is True
    assert result.has_usable_text is False

    with pytest.raises(ScannedPDFError, match="Scanned PDF not supported yet"):
        result.require_extractable_text()


def test_invalid_pdf_bytes_raises_error() -> None:
    """Corrupted or non-PDF bytes raise a clear PDFExtractionError."""
    corrupted_data = b"NOT_A_VALID_PDF_HEADER_DATA"
    with pytest.raises(PDFExtractionError, match="Failed to open PDF"):
        extract_pdf_pages(corrupted_data)

