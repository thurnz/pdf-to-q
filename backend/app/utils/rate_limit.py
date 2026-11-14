from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import logging
import threading

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class InMemoryRateLimiter:
    """Thread-safe sliding-window rate limiter per client IP."""

    def __init__(self, requests_per_minute: int | None = None) -> None:
        self._requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def get_limit(self) -> int:
        """Get the configured rate limit per minute."""
        if self._requests_per_minute is not None:
            return self._requests_per_minute
        return get_settings().rate_limit_per_minute

    def check(self, ip: str, limit: int | None = None) -> None:
        """Check if client IP is within rate limits; raise 429 if exceeded."""
        effective_limit = limit if limit is not None else self.get_limit()
        now = datetime.now(timezone.utc).timestamp()
        window_start = now - 60.0

        with self._lock:
            recent = [ts for ts in self._requests[ip] if ts > window_start]
            if len(recent) >= effective_limit:
                logger.warning(
                    "Rate limit exceeded for client IP %s (%d/%d per min)",
                    ip,
                    len(recent),
                    effective_limit,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please wait before submitting another job.",
                )
            recent.append(now)
            self._requests[ip] = recent

    def reset(self) -> None:
        """Clear all recorded request timestamps."""
        with self._lock:
            self._requests.clear()


rate_limiter = InMemoryRateLimiter()


def check_rate_limit(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> None:
    """FastAPI dependency to enforce rate limiting on endpoints."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    rate_limiter.check(client_ip, limit=settings.rate_limit_per_minute)
