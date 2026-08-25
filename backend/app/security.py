"""
Security - API key auth + rate limiting.

Both are intentionally dependency-free (no slowapi/redis) to avoid
another install saga. Rate limiting is in-memory, which is perfectly
fine for a single-process dev/demo server - it resets on restart and
doesn't scale across multiple workers, but that's not this project's
deployment target.
"""

from fastapi import Header, HTTPException, Request
from collections import defaultdict, deque
from time import time
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


# ==================== API KEY AUTH ====================

def verify_api_key(x_api_key: Optional[str] = Header(default=None)):
    """
    FastAPI dependency - checks the X-API-Key header against settings.api_key.

    If settings.api_key is blank (the default), auth is disabled entirely -
    this keeps local development frictionless. Set API_KEY in .env to
    require it.
    """
    if not settings.auth_enabled():
        return  # auth disabled - allow everyone through

    if not x_api_key or x_api_key != settings.api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid X-API-Key header.",
        )


# ==================== RATE LIMITING ====================

class InMemoryRateLimiter:
    """
    Simple sliding-window rate limiter, keyed by client IP.

    Keeps a deque of request timestamps per client; on each check it
    drops timestamps older than 60 seconds, then compares the remaining
    count against the configured limit.
    """

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)

    def check(self, client_key: str, limit_per_minute: int):
        now = time()
        window_start = now - 60
        hits = self._hits[client_key]

        while hits and hits[0] < window_start:
            hits.popleft()

        if len(hits) >= limit_per_minute:
            retry_after = int(60 - (now - hits[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded ({limit_per_minute}/min). Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)


rate_limiter = InMemoryRateLimiter()


def enforce_rate_limit(request: Request):
    """FastAPI dependency - call this on any endpoint you want rate-limited."""
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter.check(client_ip, settings.rate_limit_per_minute)
