from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from app.llm.base import LLMError, LLMProvider, RateLimitError
from app.schemas import GenerationOptions, JobStatus
from app.services.jobs import JobStore, process_job
from app.services.qa_generator import DocumentTooLongError

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MULTIPAGE_PDF = FIXTURES_DIR / "multipage_text.pdf"
SCANNED_PDF = FIXTURES_DIR / "scanned_empty.pdf"


class FakeProvider(LLMProvider):
    """Test LLM provider that returns a preset string or raises a preset exception."""

    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.call_count = 0

    def generate_json(self, prompt: str, system: str | None = None) -> str:
        self.call_count += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_process_job_success_path() -> None:
    """Full pipeline succeeds: extracts text, calls LLM, builds PDF, and marks done."""
    store = JobStore()
    options = GenerationOptions(num_questions=1)
    job = store.create_job(input_path=MULTIPAGE_PDF, options=options)

    valid_json = json.dumps(
        {
            "questions": [
                {
                    "question": "What is an OS?",
                    "answer": "Operating system.",
                    "page": 1,
                }
            ]
        }
    )
    provider = FakeProvider(valid_json)

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "done"
    assert updated.progress == 1.0
    assert updated.error is None
    assert updated.output_path is not None
    assert updated.output_path.exists()
    assert updated.output_path.read_bytes().startswith(b"%PDF")

    # Clean up output file
    if updated.output_path and updated.output_path.exists():
        updated.output_path.unlink()


def test_process_job_scanned_pdf_rejected() -> None:
    """Scanned or low-text PDFs fail at extraction stage with a clear message."""
    store = JobStore()
    options = GenerationOptions()
    job = store.create_job(input_path=SCANNED_PDF, options=options)
    provider = FakeProvider("{}")

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert "Scanned PDF not supported yet" in (updated.error or "")
    assert updated.output_path is None
    assert provider.call_count == 0


def test_process_job_too_long_document() -> None:
    """DocumentTooLongError maps to safe message 'Document is too long for now'."""
    store = JobStore()
    options = GenerationOptions()
    job = store.create_job(input_path=MULTIPAGE_PDF, options=options)
    provider = FakeProvider("{}")

    with patch(
        "app.services.jobs.generate_qa",
        side_effect=DocumentTooLongError("Too long"),
    ):
        process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error == "Document is too long for now"


def test_process_job_rate_limit_error() -> None:
    """RateLimitError maps to 'AI service is rate limited, try again later'."""
    store = JobStore()
    options = GenerationOptions()
    job = store.create_job(input_path=MULTIPAGE_PDF, options=options)
    provider = FakeProvider(RateLimitError("429 rate limit exceeded"))

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error == "AI service is rate limited, try again later"


def test_process_job_other_llm_error() -> None:
    """Generic LLMError maps to 'AI service error, try again later'."""
    store = JobStore()
    options = GenerationOptions()
    job = store.create_job(input_path=MULTIPAGE_PDF, options=options)
    provider = FakeProvider(LLMError("Model error"))

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error == "AI service error, try again later"


def test_process_job_unexpected_error() -> None:
    """Uncaught exceptions map safely to 'Something went wrong' without leaking details."""
    store = JobStore()
    options = GenerationOptions()
    job = store.create_job(input_path=MULTIPAGE_PDF, options=options)
    provider = FakeProvider("{}")

    with patch(
        "app.services.jobs.extract_pdf_pages",
        side_effect=RuntimeError("Secret database connection failure"),
    ):
        process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error == "Something went wrong"
    assert "Secret" not in (updated.error or "")


def test_cleanup_expired_deletes_files_and_records() -> None:
    """cleanup_expired removes expired job records and unlinks their files on disk."""
    store = JobStore()
    options = GenerationOptions()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 1. Expired job with existing files
        expired_in = tmp_path / "expired_input.pdf"
        expired_in.write_bytes(b"%PDF-expired-in")
        expired_out = tmp_path / "expired_output.pdf"
        expired_out.write_bytes(b"%PDF-expired-out")

        job_expired = store.create_job(input_path=expired_in, options=options)
        job_expired.output_path = expired_out
        job_expired.created_at = datetime.now(timezone.utc) - timedelta(seconds=7200)

        # 2. Active (recent) job with existing files
        active_in = tmp_path / "active_input.pdf"
        active_in.write_bytes(b"%PDF-active-in")
        active_out = tmp_path / "active_output.pdf"
        active_out.write_bytes(b"%PDF-active-out")

        job_active = store.create_job(input_path=active_in, options=options)
        job_active.output_path = active_out
        job_active.created_at = datetime.now(timezone.utc)

        # Run cleanup with 1 hour threshold (3600s)
        deleted_count = store.cleanup_expired(retention_seconds=3600)

        assert deleted_count == 1
        assert store.get_job(job_expired.id) is None
        assert not expired_in.exists()
        assert not expired_out.exists()

        # Active job and files are untouched
        assert store.get_job(job_active.id) is not None
        assert active_in.exists()
        assert active_out.exists()


def test_job_to_status_schema() -> None:
    """JobRecord.to_status produces a valid JobStatus model."""
    store = JobStore()
    job = store.create_job(input_path=MULTIPAGE_PDF, options=GenerationOptions())
    status = job.to_status()

    assert isinstance(status, JobStatus)
    assert status.id == job.id
    assert status.status == "queued"
    assert status.progress == 0.0
    assert status.error is None
