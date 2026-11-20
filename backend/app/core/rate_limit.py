"""In-memory sliding-window rate limiter for sensitive routes.

Protects login, demo creation, signup and AI uploads on a single Cloud Run
instance without adding Redis. Bounded in memory so spoofed IPs cannot grow
the table indefinitely.
"""

from collections import deque
from collections.abc import Callable
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

from app.core.config import settings

MAX_BUCKETS = 10_000
_lock = Lock()
_buckets: dict[tuple[str, str], deque[float]] = {}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Cloud Run (GFE) and Vercel append the real client IP at the end;
        # reading the leftmost value would let a caller spoof the header.
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def _prune(now: float, window_seconds: int) -> None:
    cutoff = now - window_seconds
    stale = [key for key, hits in _buckets.items() if not hits or hits[-1] <= cutoff]
    for key in stale:
        del _buckets[key]
    while len(_buckets) >= MAX_BUCKETS:
        _buckets.pop(next(iter(_buckets)))


def check_rate_limit(scope: str, key: str, limit: int, window_seconds: int) -> None:
    if not settings.RATE_LIMIT_ENABLED:
        return
    now = monotonic()
    cutoff = now - window_seconds
    bucket_key = (scope, key)
    with _lock:
        hits = _buckets.get(bucket_key)
        if hits is None:
            if len(_buckets) >= MAX_BUCKETS:
                _prune(now, window_seconds)
            hits = deque()
            _buckets[bucket_key] = hits
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= limit:
            retry_after = max(1, int(hits[0] + window_seconds - now) + 1)
            raise HTTPException(
                status_code=429,
                detail="Trop de tentatives, réessayez dans quelques instants",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)


def rate_limit(
    scope: str, limit: int, window_seconds: int
) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        check_rate_limit(scope, client_ip(request), limit, window_seconds)

    return dependency


def reset_rate_limits() -> None:
    with _lock:
        _buckets.clear()
