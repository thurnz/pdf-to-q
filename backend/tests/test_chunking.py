from __future__ import annotations

from app.services.chunking import chunk_pages


def test_chunking_empty_pages() -> None:
    """Empty list of pages or all-whitespace pages produces no chunks."""
    assert chunk_pages([]) == []
    assert chunk_pages([(1, "   "), (2, "\n\n")]) == []


def test_chunking_fits_in_single_chunk() -> None:
    """Pages whose combined length is within max_chars remain in one chunk."""
    pages = [
        (1, "Page 1 content here."),
        (2, "Page 2 content here."),
        (3, "Page 3 content here."),
    ]
    chunks = chunk_pages(pages, max_chars=1000)
    assert len(chunks) == 1
    assert len(chunks[0]) == 3
    assert chunks[0][0] == (1, "Page 1 content here.")
    assert chunks[0][1] == (2, "Page 2 content here.")
    assert chunks[0][2] == (3, "Page 3 content here.")


def test_chunking_splits_on_page_boundaries() -> None:
    """Pages are split across chunks cleanly at page boundaries without cutting pages in half."""
    # Each page is 60 chars. Limit is 100 chars.
    p1 = "A" * 60
    p2 = "B" * 60
    p3 = "C" * 60

    pages = [(1, p1), (2, p2), (3, p3)]
    chunks = chunk_pages(pages, max_chars=100)

    # p1 + p2 = 120 > 100, so each page must be its own chunk
    assert len(chunks) == 3
    assert chunks[0] == [(1, p1)]
    assert chunks[1] == [(2, p2)]
    assert chunks[2] == [(3, p3)]


def test_chunking_oversized_single_page_splits_at_paragraphs() -> None:
    """A page exceeding max_chars splits at paragraph breaks while keeping page number."""
    para1 = "First paragraph content."
    para2 = "Second paragraph content."
    para3 = "Third paragraph content."
    page_text = f"{para1}\n\n{para2}\n\n{para3}"

    # max_chars set so that 2 paragraphs fit in chunk 1, and 3rd goes to chunk 2
    max_chars = len(para1) + len(para2) + 10

    pages = [(5, page_text)]
    chunks = chunk_pages(pages, max_chars=max_chars)

    assert len(chunks) == 2
    # Verify both chunks retain page number 5
    for chunk in chunks:
        for page_num, text in chunk:
            assert page_num == 5

    # Check text contents
    chunk1_text = " ".join([t for _, t in chunks[0]])
    chunk2_text = " ".join([t for _, t in chunks[1]])
    assert para1 in chunk1_text
    assert para2 in chunk1_text
    assert para3 in chunk2_text


def test_chunking_oversized_single_paragraph_hard_splits() -> None:
    """A single paragraph longer than max_chars is split into chunks of max_chars length."""
    huge_para = "X" * 150
    pages = [(1, huge_para)]

    chunks = chunk_pages(pages, max_chars=50)

    assert len(chunks) == 3
    for chunk in chunks:
        assert chunk[0][0] == 1
        assert len(chunk[0][1]) <= 50

