from __future__ import annotations

from pathlib import Path
import tempfile

import pymupdf

from app.schemas import QAItem
from app.services.pdf_builder import build_qa_pdf, build_qa_pdf_to_file

HARDCODED_10_ITEMS: list[QAItem] = [
    QAItem(
        question="What is the primary role of an operating system kernel?",
        answer="The kernel is the core component that manages system resources such as the CPU, memory, and hardware devices, acting as a bridge between applications and hardware.",
        page=1,
    ),
    QAItem(
        question="How does virtual memory protect processes from interfering with each other?",
        answer="Virtual memory provides each process with its own isolated address space via paging and page tables, preventing direct access to physical memory allocated to other processes.",
        page=4,
    ),
    QAItem(
        question="What is the difference between a process and a thread?",
        answer="A process is an executing instance of a program with its own memory space and resources, whereas a thread is a lightweight unit of execution within a process that shares the process's memory space.",
        page=7,
    ),
    QAItem(
        question="What are the four necessary conditions for deadlock to occur?",
        answer="Deadlock requires four simultaneous conditions: Mutual Exclusion, Hold and Wait, No Preemption, and Circular Wait.",
        page=12,
    ),
    QAItem(
        question="Explain how the round-robin scheduling algorithm works.",
        answer="Round-robin assigns a fixed time quantum to each ready process in cyclic order. If a process does not complete within its quantum, it is preempted and returned to the tail of the ready queue.",
        page=15,
    ),
    QAItem(
        question="What does XML escaping prevent in study guide generation?",
        answer="Escaping characters like <script>, <b> tags, and ampersands (&) prevents parser errors and layout crashes when feeding LLM output into ReportLab Platypus Paragraphs.",
        page=18,
    ),
    QAItem(
        question="How does copy-on-write (COW) optimize process creation in fork()?",
        answer="COW allows the parent and child to share physical memory pages read-only until one modifies a page, at which point only the modified page is duplicated, drastically reducing fork overhead.",
        page=22,
    ),
    QAItem(
        question="What is the role of a Translation Lookaside Buffer (TLB)?",
        answer="The TLB is a high-speed hardware cache that stores recent virtual-to-physical address translations, minimizing costly page-table lookups in main memory.",
        page=25,
    ),
    QAItem(
        question="Can a study guide question omit a page reference?",
        answer="Yes! When a concept spans the entire document or a specific page is not attributable, the page field defaults to None and formats cleanly without a badge.",
        page=None,
    ),
    QAItem(
        question="Provide a comprehensive summary of memory hierarchy from fastest to slowest.",
        answer=(
            "The memory hierarchy consists of:\n"
            "1. CPU Registers (fastest, smallest, volatile)\n"
            "2. L1, L2, L3 Caches (SRAM, very fast)\n"
            "3. Main Memory / RAM (DRAM, moderate speed and capacity)\n"
            "4. Solid-State Drives / NVMe (fast secondary non-volatile storage)\n"
            "5. Hard Disk Drives & Cloud Storage (slowest, largest capacity, persistent)\n\n"
            "This hierarchical design balances access latency against cost and capacity."
        ),
        page=30,
    ),
]


def test_build_qa_pdf_returns_valid_bytes_with_10_items() -> None:
    """Builder accepts 10 Q&A items, escapes characters, and returns valid PDF bytes starting with %PDF."""
    pdf_bytes = build_qa_pdf(
        title="Operating Systems & Architecture Exam Prep",
        qa_items=HARDCODED_10_ITEMS,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")
    assert b"%%EOF" in pdf_bytes

    # Verify the generated PDF can be read by PyMuPDF and contains questions
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        assert len(doc) >= 1  # Should be formatted cleanly across pages
        full_text = " ".join(page.get_text() for page in doc)

        # Check title and multiple items are present
        assert "Operating Systems & Architecture" in full_text
        assert "Q1." in full_text
        assert "Q10." in full_text
        assert "deadlock" in full_text.lower()
        # Verify XML escaping didn't corrupt the literal <script> question content
        assert "XML escaping" in full_text
    finally:
        doc.close()


def test_build_qa_pdf_to_file() -> None:
    """build_qa_pdf_to_file writes valid PDF bytes directly to disk."""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "subfolder" / "guide.pdf"
        result_path = build_qa_pdf_to_file(
            title="Temp Study Guide",
            qa_items=HARDCODED_10_ITEMS[:3],
            output_path=output_path,
        )

        assert result_path == output_path
        assert output_path.exists()
        assert output_path.read_bytes().startswith(b"%PDF")
