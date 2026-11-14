from __future__ import annotations

import logging
from pathlib import Path
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import ValidationError
import pymupdf

from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.schemas import GenerationOptions, JobStatus
from app.services.jobs import create_job, get_job, process_job
from app.utils.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"

router = APIRouter()


@router.post(
    "/jobs",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(check_rate_limit)],
    summary="Submit a PDF for study guide generation",
)
async def submit_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF document to convert"),
    num_questions: int = Form(10, description="Target question count (1-50)"),
    difficulty: str = Form("medium", description="easy | medium | hard"),
    detail: str = Form("short", description="short | detailed"),
    provider: LLMProvider = Depends(get_provider),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Validate upload, store PDF safely, and enqueue study guide generation."""
    # 1. Validate generation parameters
    try:
        options = GenerationOptions(
            num_questions=num_questions,
            difficulty=difficulty,  # type: ignore[arg-type]
            detail=detail,  # type: ignore[arg-type]
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        )

    # 2. Validate MIME content type
    content_type = (file.content_type or "").lower().strip()
    if content_type and "pdf" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content type. Only PDF documents are supported.",
        )

    # 3. Read stream, enforce MAX_FILE_SIZE_MB, and verify %PDF magic bytes
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    job_uuid = str(uuid.uuid4())
    upload_path = UPLOADS_DIR / f"{job_uuid}.pdf"

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    total_bytes = 0
    header_verified = False

    try:
        with open(upload_path, "wb") as out_f:
            while chunk := await file.read(65536):
                if not header_verified:
                    if not chunk.startswith(b"%PDF"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Invalid PDF file: missing %PDF header.",
                        )
                    header_verified = True

                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {settings.max_file_size_mb} MB.",
                    )
                out_f.write(chunk)

        if not header_verified or total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file provided.",
            )

    except Exception:
        if upload_path.exists():
            upload_path.unlink()
        raise

    # 4. Enforce MAX_PAGE_COUNT using PyMuPDF
    try:
        doc = pymupdf.open(upload_path)
        page_count = len(doc)
        doc.close()
    except Exception as exc:
        if upload_path.exists():
            upload_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Corrupted or unreadable PDF document.",
        ) from exc

    if page_count > settings.max_page_count:
        if upload_path.exists():
            upload_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"PDF page count ({page_count}) exceeds limit of {settings.max_page_count} pages.",
        )

    # 5. Create job in store and schedule processing
    job = create_job(input_path=upload_path, options=options, job_id=job_uuid)
    background_tasks.add_task(process_job, job.id, provider)

    return {"id": job.id, "status": job.status}


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatus,
    summary="Get job status and progress",
)
def get_job_status(job_id: str) -> JobStatus:
    """Retrieve current processing status and progress for a given job ID."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    return job.to_status()


@router.get(
    "/jobs/{job_id}/download",
    summary="Download the generated study guide PDF",
)
def download_job_pdf(job_id: str) -> FileResponse:
    """Download generated study guide PDF once processing is complete."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )
    if job.status != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job is not done yet (current status: {job.status})",
        )
    if not job.output_path or not job.output_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generated PDF file not found on server",
        )

    return FileResponse(
        path=job.output_path,
        media_type="application/pdf",
        filename=f"study_guide_{job_id}.pdf",
    )
