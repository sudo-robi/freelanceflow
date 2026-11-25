"""Dependency-free in-process sliding-window rate limiting.

Keys use trusted transport metadata (client IP) or authenticated user IDs,
never spoofable proxy headers such as X-Forwarded-For. Instances are local to
one worker; deployments behind multiple workers should also rate-limit at the
edge. This limitation is documented in DEPLOYMENT.md.
"""

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() != "false"
_LOCK = threading.Lock()
_HITS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    """Clear counters (used by automated tests)."""
    with _LOCK:
        _HITS.clear()


def check_rate_limit(scope: str, key: str, limit: int, window_seconds: int = 60) -> None:
    if not _ENABLED:
        return
    now = time.monotonic()
    bucket = (_HITS[(scope, key)])
    with _LOCK:
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please retry later.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def rate_limit(scope: str, limit: int, window_seconds: int = 60):
    """FastAPI dependency factory for a named rate-limit bucket."""

    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        check_rate_limit(scope, client, limit, window_seconds)

    return dependency
