"""Rate limiting with a shared database backend.

The default backend stores counters in the application database, so limits are
shared by every worker and instance pointing at the same database. An
in-process backend remains available for lightweight local development.

The client IP is taken from ``request.client.host`` (the transport peer), never
from spoofable forwarding headers. Deployments behind a proxy must configure
that proxy to pass the real peer address or enforce limits at the edge.
"""

import logging
import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("freelanceflow.ratelimit")

BACKEND = os.getenv("RATE_LIMIT_BACKEND", "database").strip().lower()
FAIL_OPEN = os.getenv("RATE_LIMIT_FAIL_OPEN", "true").strip().lower() != "false"
_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() != "false"

_LOCK = threading.Lock()
_HITS: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    """Clear counters (used by automated tests)."""
    with _LOCK:
        _HITS.clear()
    if BACKEND == "database":
        try:
            from .database import SessionLocal
            from .models import RateLimitCounter

            db = SessionLocal()
            try:
                db.query(RateLimitCounter).delete()
                db.commit()
            finally:
                db.close()
        except Exception:
            # Tables may not exist yet during test database setup.
            pass


def _memory_check(scope: str, key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    bucket = _HITS[(scope, key)]
    with _LOCK:
        while bucket and bucket[0] <= now - window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window_seconds - (now - bucket[0])))
            raise HTTPException(status_code=429, detail="Too many requests. Please retry later.", headers={"Retry-After": str(retry_after)})
        bucket.append(now)


def _database_check(scope: str, key: str, limit: int, window_seconds: int) -> None:
    from .database import SessionLocal
    from .models import RateLimitCounter

    window_bucket = int(time.time()) // max(1, window_seconds)
    retry_after = max(1, window_seconds - (int(time.time()) % max(1, window_seconds)))
    db = SessionLocal()
    try:
        row = db.query(RateLimitCounter).filter(
            RateLimitCounter.scope == scope,
            RateLimitCounter.key == key,
            RateLimitCounter.window_bucket == window_bucket,
        ).with_for_update().first()
        if row is None:
            db.add(RateLimitCounter(scope=scope, key=key, window_bucket=window_bucket, count=1))
            try:
                db.commit()
                return
            except SQLAlchemyError:
                db.rollback()
                row = db.query(RateLimitCounter).filter(
                    RateLimitCounter.scope == scope,
                    RateLimitCounter.key == key,
                    RateLimitCounter.window_bucket == window_bucket,
                ).with_for_update().first()
        if row is not None:
            if row.count >= limit:
                raise HTTPException(status_code=429, detail="Too many requests. Please retry later.", headers={"Retry-After": str(retry_after)})
            row.count += 1
            db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as error:
        db.rollback()
        logger.warning("Rate-limit backend unavailable: %s", type(error).__name__)
        if not FAIL_OPEN:
            raise HTTPException(status_code=503, detail="Service temporarily unavailable") from error
    finally:
        db.close()


def check_rate_limit(scope: str, key: str, limit: int, window_seconds: int = 60) -> None:
    if not _ENABLED:
        return
    if BACKEND == "memory":
        _memory_check(scope, key, limit, window_seconds)
    else:
        _database_check(scope, key, limit, window_seconds)


def rate_limit(scope: str, limit: int, window_seconds: int = 60):
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        check_rate_limit(scope, client, limit, window_seconds)

    return dependency
