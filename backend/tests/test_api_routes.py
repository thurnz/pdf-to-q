from __future__ import annotations

from collections.abc import Generator
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.config import Settings, get_settings
from app.llm.base import LLMProvider
from app.llm.factory import get_provider
from app.main import app
from app.schemas import GenerationOptions
from app.services.jobs import job_store
from app.utils.rate_limit import rate_limiter

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MULTIPAGE_PDF = FIXTURES_DIR / "multipage_text.pdf"


class FakeProvider(LLMProvider):
    """Test LLM provider that returns predetermined JSON."""

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text

    def generate_json(self, prompt: str, system: str | None = None) -> str:
        return self.response_text


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """TestClient configured with a fake LLM provider and cleared rate limiter."""
    rate_limiter.reset()
    fake_provider = FakeProvider(
        json.dumps(
            {
                "questions": [
                    {
                        "question": "What is memory?",
                        "answer": "Storage component.",
                        "page": 1,
                    }
                ]
            }
        )
    )
    app.dependency_overrides[get_provider] = lambda: fake_provider

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    rate_limiter.reset()


def test_submit_poll_and_download_flow(client: TestClient) -> None:
    """Full API lifecycle: POST /jobs -> GET /jobs/{id} -> GET /jobs/{id}/download."""
    pdf_bytes = MULTIPAGE_PDF.read_bytes()

    # 1. POST /jobs
    response = client.post(
        "/jobs",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        data={"num_questions": 3, "difficulty": "medium", "detail": "short"},
    )
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    job_id = data["id"]
    assert data["status"] in ("queued", "processing", "done")

    # 2. GET /jobs/{id} (TestClient executes BackgroundTasks synchronously)
    status_resp = client.get(f"/jobs/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["id"] == job_id
    assert status_data["status"] == "done"
    assert status_data["progress"] == 1.0
    assert status_data["error"] is None

    # 3. GET /jobs/{id}/download
    download_resp = client.get(f"/jobs/{job_id}/download")
    assert download_resp.status_code == 200
    assert download_resp.headers["content-type"] == "application/pdf"
    assert download_resp.content.startswith(b"%PDF")


def test_submit_non_pdf_file_rejected(client: TestClient) -> None:
    """Uploading a non-PDF file returns 400 Bad Request."""
    response = client.post(
        "/jobs",
        files={"file": ("notes.txt", b"plain text content", "text/plain")},
        data={"num_questions": 5},
    )
    assert response.status_code == 400
    assert "Only PDF documents are supported" in response.json()["detail"]


def test_submit_fake_pdf_missing_magic_bytes(client: TestClient) -> None:
    """File claiming to be PDF but without %PDF magic bytes is rejected with 400."""
    fake_bytes = b"NOT_A_REAL_PDF_HEADER_DATA_HERE"
    response = client.post(
        "/jobs",
        files={"file": ("fake.pdf", fake_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    assert "missing %PDF header" in response.json()["detail"]


def test_submit_oversized_file_rejected(client: TestClient) -> None:
    """File exceeding MAX_FILE_SIZE_MB returns 413 Request Entity Too Large."""
    # Temporarily set max_file_size_mb to 0.001 MB (~1KB)
    small_settings = Settings(
        _env_file=None,
        gemini_model="test-model",
        max_file_size_mb=0,  # 0 MB means max_bytes is 0
    )
    app.dependency_overrides[get_settings] = lambda: small_settings

    pdf_bytes = MULTIPAGE_PDF.read_bytes()
    response = client.post(
        "/jobs",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 413
    assert "File exceeds maximum allowed size" in response.json()["detail"]


def test_submit_too_many_pages_rejected(client: TestClient) -> None:
    """PDF with more pages than MAX_PAGE_COUNT returns 400 Bad Request."""
    # Fixture has 3 pages; limit to 1
    strict_settings = Settings(
        _env_file=None,
        gemini_model="test-model",
        max_page_count=1,
    )
    app.dependency_overrides[get_settings] = lambda: strict_settings

    pdf_bytes = MULTIPAGE_PDF.read_bytes()
    response = client.post(
        "/jobs",
        files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
    )
    assert response.status_code == 400
    assert "exceeds limit of 1 pages" in response.json()["detail"]


def test_get_unknown_job_returns_404(client: TestClient) -> None:
    """GET /jobs/{id} for unknown job returns 404."""
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_download_unknown_job_returns_404(client: TestClient) -> None:
    """GET /jobs/{id}/download for unknown job returns 404."""
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000/download")
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_download_before_done_returns_409(client: TestClient) -> None:
    """Attempting to download a job that is still processing returns 409 Conflict."""
    job = job_store.create_job(
        input_path=MULTIPAGE_PDF,
        options=GenerationOptions(),
    )
    job_store.update_job(job.id, status="processing", progress=0.4)

    response = client.get(f"/jobs/{job.id}/download")
    assert response.status_code == 409
    assert "Job is not done yet" in response.json()["detail"]


def test_rate_limit_exceeded_returns_429(client: TestClient) -> None:
    """Submitting more than rate_limit_per_minute requests returns 429."""
    rate_limited_settings = Settings(
        _env_file=None,
        gemini_model="test-model",
        rate_limit_per_minute=2,
    )
    app.dependency_overrides[get_settings] = lambda: rate_limited_settings

    pdf_bytes = MULTIPAGE_PDF.read_bytes()

    # Request 1: success (202)
    resp1 = client.post(
        "/jobs",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp1.status_code == 202

    # Request 2: success (202)
    resp2 = client.post(
        "/jobs",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp2.status_code == 202

    # Request 3: rate limit exceeded (429)
    resp3 = client.post(
        "/jobs",
        files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
    )
    assert resp3.status_code == 429
    assert "Rate limit exceeded" in resp3.json()["detail"]
