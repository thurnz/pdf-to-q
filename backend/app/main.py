from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.services.jobs import cleanup_expired

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes


async def _periodic_cleanup() -> None:
    """Background loop that periodically cleans up expired jobs and files."""
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
            deleted = await asyncio.to_thread(cleanup_expired)
            if deleted > 0:
                logger.info("Periodic cleanup removed %d expired job(s).", deleted)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Error during periodic cleanup: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle tasks."""
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


settings = get_settings()

app = FastAPI(
    title="PDF → Q&A Study Guide",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness check."""
    return {"status": "ok"}
