from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import threading
from unittest.mock import patch

from app.llm.base import (
    LLMError,
    LLMProvider,
    ProviderUnavailableError,
    RateLimitError,
)
from app.schemas import GenerationOptions, JobStatus, QAItem
from app.services.jobs import JobStore, process_job
from app.services.qa_generator import DocumentTooLongError

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MULTIPAGE_PDF = FIXTURES_DIR / "multipage_text.pdf"
SCANNED_PDF = FIXTURES_DIR / "scanned_empty.pdf"


def make_input_file(tmp_path: Path, source: Path = MULTIPAGE_PDF) -> Path:
    """Create a temporary copy of a fixture PDF so process_job can delete it safely."""
    dest = tmp_path / f"test_input_{source.name}"
    dest.write_bytes(source.read_bytes())
    return dest


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


def test_process_job_success_path(tmp_path: Path) -> None:
    """Full pipeline succeeds: extracts text, calls LLM, builds PDF, and marks done."""
    store = JobStore()
    options = GenerationOptions(num_questions=1)
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    job = store.create_job(input_path=input_file, options=options)

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


def test_process_job_scanned_pdf_rejected(tmp_path: Path) -> None:
    """Scanned or low-text PDFs fail at extraction stage with a clear message."""
    store = JobStore()
    options = GenerationOptions()
    input_file = make_input_file(tmp_path, SCANNED_PDF)
    job = store.create_job(input_path=input_file, options=options)
    provider = FakeProvider("{}")

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert "Scanned PDF not supported yet" in (updated.error or "")
    assert updated.output_path is None
    assert provider.call_count == 0


def test_process_job_too_long_document(tmp_path: Path) -> None:
    """DocumentTooLongError maps to safe message 'Document is too long for now'."""
    store = JobStore()
    options = GenerationOptions()
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    job = store.create_job(input_path=input_file, options=options)
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


def test_process_job_progress_across_chunks(tmp_path: Path) -> None:
    """Multi-chunk processing updates job progress from 0.2 across chunks up to 0.9 and 1.0."""
    store = JobStore()
    options = GenerationOptions()
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    job = store.create_job(input_path=input_file, options=options)

    progress_history: list[float] = []
    original_update_job = store.update_job

    def track_update(job_id: str, **kwargs: object) -> object:
        if "progress" in kwargs:
            progress_history.append(float(kwargs["progress"]))
        return original_update_job(job_id, **kwargs)

    store.update_job = track_update  # type: ignore[method-assign]

    def fake_generate_qa(*args: object, **kwargs: object) -> list[QAItem]:
        cb = kwargs.get("on_progress")
        if callable(cb):
            cb(0, 2)
            cb(1, 2)
        return [QAItem(question="Q?", answer="A.", page=1)]

    with patch("app.services.jobs.generate_qa", side_effect=fake_generate_qa):
        process_job(job.id, provider=FakeProvider("{}"), store=store)

    assert 0.2 in progress_history
    assert 0.55 in progress_history
    assert 0.9 in progress_history
    assert 1.0 in progress_history


def test_process_job_rate_limit_error(tmp_path: Path) -> None:
    """RateLimitError maps to 'AI service is rate limited, try again later'."""
    store = JobStore()
    options = GenerationOptions()
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    job = store.create_job(input_path=input_file, options=options)
    provider = FakeProvider(RateLimitError("429 rate limit exceeded"))

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error == "AI service is rate limited, try again later"


def test_process_job_provider_unavailable_error(tmp_path: Path) -> None:
    """ProviderUnavailableError maps to 'The AI service is busy right now, please try again in a few minutes.'."""
    store = JobStore()
    options = GenerationOptions()
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    job = store.create_job(input_path=input_file, options=options)
    provider = FakeProvider(ProviderUnavailableError("503 Service Unavailable"))

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert (
        updated.error
        == "The AI service is busy right now, please try again in a few minutes."
    )


def test_process_job_other_llm_error(tmp_path: Path) -> None:
    """Generic LLMError maps to 'AI service error, try again later'."""
    store = JobStore()
    options = GenerationOptions()
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    job = store.create_job(input_path=input_file, options=options)
    provider = FakeProvider(LLMError("Model error"))

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error == "AI service error, try again later"


def test_process_job_unexpected_error(tmp_path: Path) -> None:
    """Uncaught exceptions map safely to 'Something went wrong' without leaking details."""
    store = JobStore()
    options = GenerationOptions()
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    job = store.create_job(input_path=input_file, options=options)
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


def test_process_job_input_file_deleted_on_success(tmp_path: Path) -> None:
    """The uploaded input PDF is deleted from disk as soon as processing finishes successfully."""
    store = JobStore()
    input_file = make_input_file(tmp_path, MULTIPAGE_PDF)
    assert input_file.exists()

    job = store.create_job(
        input_path=input_file, options=GenerationOptions(num_questions=1)
    )
    valid_json = json.dumps(
        {"questions": [{"question": "Q?", "answer": "A.", "page": 1}]}
    )
    provider = FakeProvider(valid_json)

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "done"
    # Privacy check: input file MUST be unlinked
    assert not input_file.exists()

    if updated.output_path and updated.output_path.exists():
        updated.output_path.unlink()


def test_process_job_input_file_deleted_on_failure(tmp_path: Path) -> None:
    """The uploaded input PDF is deleted from disk as soon as processing finishes even if it failed."""
    store = JobStore()
    input_file = make_input_file(tmp_path, SCANNED_PDF)
    assert input_file.exists()

    job = store.create_job(input_path=input_file, options=GenerationOptions())
    provider = FakeProvider("{}")

    process_job(job.id, provider=provider, store=store)

    updated = store.get_job(job.id)
    assert updated is not None
    assert updated.status == "failed"
    # Privacy check: input file MUST be unlinked on failure as well
    assert not input_file.exists()


def test_concurrency_semaphore_limits_parallel_jobs(tmp_path: Path) -> None:
    """When concurrent jobs exceed semaphore limit, extra jobs remain queued until a slot frees up."""
    store = JobStore()
    sem = threading.Semaphore(2)

    active_count = 0
    max_active_seen = 0
    lock = threading.Lock()
    first_two_entered = threading.Event()
    release_first_two = threading.Event()

    class SlowProvider(LLMProvider):
        def generate_json(self, prompt: str, system: str | None = None) -> str:
            nonlocal active_count, max_active_seen
            with lock:
                active_count += 1
                if active_count > max_active_seen:
                    max_active_seen = active_count
                if active_count == 2:
                    first_two_entered.set()
            release_first_two.wait(timeout=5.0)
            with lock:
                active_count -= 1
            return json.dumps(
                {"questions": [{"question": "Q?", "answer": "A.", "page": 1}]}
            )

    provider = SlowProvider()
    jobs = []
    threads = []

    for i in range(3):
        in_path = tmp_path / f"job_{i}.pdf"
        in_path.write_bytes(MULTIPAGE_PDF.read_bytes())
        job = store.create_job(
            input_path=in_path, options=GenerationOptions(num_questions=1)
        )
        jobs.append(job)

    for job in jobs:
        t = threading.Thread(
            target=process_job,
            args=(job.id, provider, store, sem),
        )
        t.daemon = True
        threads.append(t)
        t.start()

    # Wait for 2 jobs to enter processing in provider
    assert first_two_entered.wait(timeout=3.0)

    # At this point, job 0 and job 1 are processing, job 2 should still be queued
    processing_count = sum(
        1 for j in jobs if getattr(store.get_job(j.id), "status", None) == "processing"
    )
    queued_count = sum(
        1 for j in jobs if getattr(store.get_job(j.id), "status", None) == "queued"
    )
    assert processing_count == 2
    assert queued_count == 1
    assert max_active_seen == 2

    # Release the first two jobs
    release_first_two.set()
    for t in threads:
        t.join(timeout=5.0)

    # All 3 jobs should be done
    for job in jobs:
        rec = store.get_job(job.id)
        assert rec is not None
        assert rec.status == "done"
        if rec.output_path and rec.output_path.exists():
            rec.output_path.unlink()


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
