#!/usr/bin/env python3
"""Throwaway script to generate a sample study guide PDF in backend/storage/demo.pdf."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

import pymupdf  # noqa: E402
from app.schemas import QAItem  # noqa: E402
from app.services.pdf_builder import build_qa_pdf_to_file  # noqa: E402

SAMPLE_ITEMS: list[QAItem] = [
    QAItem(
        question="What is the primary role of an operating system kernel?",
        answer="The kernel is the foundational software running with privileged CPU access (kernel mode). It manages hardware resources including the CPU scheduler, memory allocator, virtual file system, and device drivers, exposing these capabilities safely to user processes via system calls.",
        page=1,
    ),
    QAItem(
        question="How does virtual memory protect processes from interfering with each other?",
        answer="Virtual memory abstracts physical DRAM into contiguous per-process address spaces using page tables managed by the Memory Management Unit (MMU). A process can only reference virtual addresses mapped in its own page table, preventing illegal reads or writes to memory allocated to other programs or the kernel.",
        page=4,
    ),
    QAItem(
        question="What is the fundamental difference between a process and a thread?",
        answer="A process is an isolated execution environment with dedicated virtual address space, file descriptors, and security tokens. A thread is an execution context (program counter, stack, registers) within a process; all threads in a process share the same heap, global variables, and open files.",
        page=7,
    ),
    QAItem(
        question="What are Coffman's four necessary conditions for deadlock to occur?",
        answer="Deadlock can occur if and only if all four conditions hold simultaneously:\n1. Mutual Exclusion: At least one resource is held non-shareably.\n2. Hold and Wait: A process holds resources while requesting others.\n3. No Preemption: Resources cannot be forcibly taken from a holding process.\n4. Circular Wait: A closed chain of processes exists where each waits for a resource held by the next.",
        page=12,
    ),
    QAItem(
        question="How does the Round-Robin (RR) CPU scheduling algorithm prevent starvation?",
        answer="Round-Robin assigns a uniform time slice (quantum) to every ready process in a FIFO queue. If a running process does not finish or block before its quantum expires, the scheduler preempts it and moves it to the back of the queue, guaranteeing every runnable process CPU time within a bounded interval.",
        page=15,
    ),
    QAItem(
        question="Why is XML-character escaping critical when generating PDFs from LLM output?",
        answer="ReportLab Platypus Paragraphs parse input strings using an XML-like grammar for styling tags like <b>, <i>, and <font>. If unescaped LLM text contains raw characters like '<', '>', or '&' (for instance in code snippets or mathematical expressions), the XML parser will fail and crash the generation job.",
        page=18,
    ),
    QAItem(
        question="How does Copy-on-Write (COW) optimize fork() system calls?",
        answer="Rather than copying the entire address space upon fork(), Copy-on-Write marks the parent's memory pages as read-only and shares them with the child. Only when either process attempts to write to a page does an MMU fault trigger the kernel to duplicate that specific 4KB page.",
        page=22,
    ),
    QAItem(
        question="What is a Translation Lookaside Buffer (TLB) and why is its hit rate crucial?",
        answer="A TLB is a small, associative hardware cache on the CPU that stores recent virtual-to-physical address mappings. With a high hit rate (often >98%), address translations resolve in a single clock cycle. A TLB miss requires a multi-level page table walk in DRAM, degrading execution speed by 10x-50x.",
        page=25,
    ),
    QAItem(
        question="Can study guide questions cover overarching concepts without a specific page tag?",
        answer="Yes. When a question synthesizes themes spanning the entire text or chapter introductions, the page reference is optional and gracefully omitted from the study guide entry without clutter.",
        page=None,
    ),
    QAItem(
        question="Describe the computer memory hierarchy and the architectural trade-offs at each tier.",
        answer=(
            "The memory hierarchy balances speed, cost, and physical capacity across tiers:\n"
            "• Registers & L1/L2/L3 Caches: Sub-nanosecond to few-nanosecond access using SRAM, but limited in capacity due to high heat and silicon area cost.\n"
            "• Main Memory (DRAM): Tens of nanoseconds latency, offering gigabytes of storage at reasonable cost, refreshed periodically.\n"
            "• NVMe / Solid-State Storage: Microsecond latency using NAND flash, offering persistent non-volatile storage.\n"
            "• Secondary / Cloud Storage: Millisecond access using magnetic HDDs or object stores, providing petabyte-scale durability.\n\n"
            "Caching mechanisms and temporal/spatial locality allow modern systems to deliver near-SRAM performance on average workloads."
        ),
        page=30,
    ),
]


def main() -> None:
    storage_dir = backend_root / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    output_path = storage_dir / "demo.pdf"

    print(f"Building sample study guide with {len(SAMPLE_ITEMS)} Q&A items...")
    build_qa_pdf_to_file(
        title="Operating Systems & System Architecture",
        qa_items=SAMPLE_ITEMS,
        output_path=output_path,
    )

    doc = pymupdf.open(output_path)
    page_count = len(doc)
    doc.close()

    file_size_kb = output_path.stat().st_size / 1024
    print("Done!")
    print(f"  Output path: {output_path}")
    print(f"  Pages: {page_count}")
    print(f"  Size: {file_size_kb:.1f} KB")


if __name__ == "__main__":
    main()
