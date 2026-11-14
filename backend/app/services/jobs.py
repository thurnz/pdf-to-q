from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
from typing import Literal
import uuid

from app.config import get_settings
from app.llm.base import LLMError, LLMProvider, RateLimitError
from app.schemas import GenerationOptions, JobStatus
from app.services.pdf_builder import build_qa_pdf_to_file
from app.services.pdf_extract import ScannedPDFError, extract_pdf_pages
from app.services.qa_generator import DocumentTooLongError, generate_qa

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"
OUTPUTS_DIR = STORAGE_DIR / "outputs"


@dataclass
class JobRecord:
    """Internal representation of a study guide generation job."""

    id: str
    status: Literal["queued", "processing", "done", "failed"]
    progress: float
    error: str | None
    options: GenerationOptions
    input_path: Path
    output_path: Path | None
    created_at: datetime

    def to_status(self) -> JobStatus:
        """Convert internal record to public JobStatus schema."""
        return JobStatus(
            id=self.id,
            status=self.status,
            progress=self.progress,
            error=self.error,
        )


class JobStore:
    """Thread-safe in-memory job store backed by a dictionary and threading lock."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        input_path: Path,
        options: GenerationOptions,
        job_id: str | None = None,
    ) -> JobRecord:
        """Create and store a new job in queued state."""
        jid = job_id or str(uuid.uuid4())
        record = JobRecord(
            id=jid,
            status="queued",
            progress=0.0,
            error=None,
            options=options,
            input_path=input_path,
            output_path=None,
            created_at=datetime.now(timezone.utc),
        )
        with self._lock:
            self._jobs[jid] = record
        return record

    def get_job(self, job_id: str) -> JobRecord | None:
        """Retrieve a job record by its ID."""
        with self._lock:
            return self._jobs.get(job_id)

    def update_job(
        self,
        job_id: str,
        *,
        status: Literal["queued", "processing", "done", "failed"] | None = None,
        progress: float | None = None,
        error: str | None = None,
        output_path: Path | None = None,
    ) -> JobRecord | None:
        """Update job fields safely within lock."""
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if error is not None:
                job.error = error
            if output_path is not None:
                job.output_path = output_path
            return job

    def cleanup_expired(self, retention_seconds: int | None = None) -> int:
        """Remove jobs and associated files older than retention period."""
        if retention_seconds is None:
            retention_seconds = get_settings().file_retention_seconds

        now = datetime.now(timezone.utc)
        expired_ids: list[str] = []

        with self._lock:
            for jid, record in self._jobs.items():
                age_seconds = (now - record.created_at).total_seconds()
                if age_seconds > retention_seconds:
                    expired_ids.append(jid)

            for jid in expired_ids:
                record = self._jobs.pop(jid, None)
                if record:
                    self._delete_file_safely(record.input_path)
                    if record.output_path:
                        self._delete_file_safely(record.output_path)

        if expired_ids:
            logger.info("Cleaned up %d expired job(s).", len(expired_ids))
        return len(expired_ids)

    @staticmethod
    def _delete_file_safely(path: Path | None) -> None:
        if path and path.exists():
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("Failed to delete expired file %s: %s", path.name, exc)


# Global job store singleton
job_store = JobStore()


def create_job(
    input_path: Path,
    options: GenerationOptions,
    job_id: str | None = None,
) -> JobRecord:
    """Module-level helper to create a job in the default job store."""
    return job_store.create_job(input_path, options, job_id=job_id)


def get_job(job_id: str) -> JobRecord | None:
    """Module-level helper to get a job from the default job store."""
    return job_store.get_job(job_id)


def update_job(
    job_id: str,
    *,
    status: Literal["queued", "processing", "done", "failed"] | None = None,
    progress: float | None = None,
    error: str | None = None,
    output_path: Path | None = None,
) -> JobRecord | None:
    """Module-level helper to update a job in the default job store."""
    return job_store.update_job(
        job_id,
        status=status,
        progress=progress,
        error=error,
        output_path=output_path,
    )


def cleanup_expired(retention_seconds: int | None = None) -> int:
    """Module-level helper to run cleanup on the default job store."""
    return job_store.cleanup_expired(retention_seconds)


def process_job(
    job_id: str,
    provider: LLMProvider,
    store: JobStore | None = None,
) -> None:
    """Execute the end-to-end processing pipeline for a job in the background."""
    active_store = store or job_store
    job = active_store.get_job(job_id)
    if not job:
        logger.error("Cannot process non-existent job ID: %s", job_id)
        return

    active_store.update_job(job_id, status="processing", progress=0.1)

    try:
        # Stage 1: PDF extraction
        extraction_result = extract_pdf_pages(job.input_path)
        extraction_result.require_extractable_text()
        active_store.update_job(job_id, progress=0.3)

        # Stage 2: Q&A generation via LLM
        qa_items = generate_qa(
            pages=extraction_result.pages,
            options=job.options,
            provider=provider,
        )
        if not qa_items:
            raise ValueError("No questions could be generated from this document")
        active_store.update_job(job_id, progress=0.7)

        # Stage 3: Output PDF generation
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUTS_DIR / f"{job_id}.pdf"
        doc_title = f"Study Guide: {job.input_path.stem.replace('_', ' ').title()}"
        build_qa_pdf_to_file(title=doc_title, qa_items=qa_items, output_path=out_path)

        active_store.update_job(
            job_id, status="done", progress=1.0, output_path=out_path
        )
        logger.info("Job %s completed successfully.", job_id)

    except ScannedPDFError:
        logger.warning("Job %s failed: scanned PDF / insufficient text", job_id)
        active_store.update_job(
            job_id,
            status="failed",
            error="Scanned PDF not supported yet: document contains little or no extractable text",
        )
    except DocumentTooLongError:
        logger.warning("Job %s failed: document exceeded length limit", job_id)
        active_store.update_job(
            job_id,
            status="failed",
            error="Document is too long for now",
        )
    except RateLimitError:
        logger.warning("Job %s failed: AI service rate limited", job_id)
        active_store.update_job(
            job_id,
            status="failed",
            error="AI service is rate limited, try again later",
        )
    except LLMError:
        logger.warning("Job %s failed: AI service error", job_id)
        active_store.update_job(
            job_id,
            status="failed",
            error="AI service error, try again later",
        )
    except Exception:
        logger.exception("Job %s failed with unexpected exception", job_id)
        active_store.update_job(
            job_id,
            status="failed",
            error="Something went wrong",
        )
