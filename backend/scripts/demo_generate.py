#!/usr/bin/env python3
"""Manual demonstration script that runs the full extract -> generate_qa -> pdf_builder pipeline.

Usage:
    .venv/bin/python scripts/demo_generate.py [path_to_pdf]
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.llm.factory import get_provider  # noqa: E402
from app.schemas import GenerationOptions  # noqa: E402
from app.services.pdf_builder import build_qa_pdf_to_file  # noqa: E402
from app.services.pdf_extract import extract_pdf_pages  # noqa: E402
from app.services.qa_generator import generate_qa  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract PDF text, generate Q&A study guide using LLM, and build output PDF."
    )
    parser.add_argument(
        "pdf_path",
        nargs="?",
        default=str(backend_root / "tests" / "fixtures" / "multipage_text.pdf"),
        help="Path to source PDF file (defaults to test fixture)",
    )
    parser.add_argument(
        "--questions",
        type=int,
        default=5,
        help="Number of questions to generate (default: 5)",
    )
    parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="Target difficulty (default: medium)",
    )
    parser.add_argument(
        "--detail",
        choices=["short", "detailed"],
        default="short",
        help="Answer detail (default: short)",
    )
    args = parser.parse_args()

    input_pdf = Path(args.pdf_path)
    if not input_pdf.exists():
        print(f"Error: input file not found at {input_pdf}", file=sys.stderr)
        sys.exit(1)

    print(f"1. Extracting text from {input_pdf.name}...")
    extraction_result = extract_pdf_pages(input_pdf)
    extraction_result.require_extractable_text()
    print(f"   Extracted {extraction_result.total_pages} page(s).")

    print("2. Initializing LLM provider and generating study guide Q&A items...")
    provider = get_provider()
    options = GenerationOptions(
        num_questions=args.questions,
        difficulty=args.difficulty,
        detail=args.detail,
    )

    qa_items = generate_qa(extraction_result.pages, options, provider)
    print(f"   Generated {len(qa_items)} validated, deduplicated Q&A item(s).")

    storage_dir = backend_root / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    output_pdf = storage_dir / "demo_generated.pdf"

    print("3. Building output study guide PDF...")
    doc_title = f"Study Guide: {input_pdf.stem.replace('_', ' ').title()}"
    build_qa_pdf_to_file(title=doc_title, qa_items=qa_items, output_path=output_pdf)

    file_size_kb = output_pdf.stat().st_size / 1024
    print("Done!")
    print(f"   Output written to: {output_pdf}")
    print(f"   File size: {file_size_kb:.1f} KB")


if __name__ == "__main__":
    main()
