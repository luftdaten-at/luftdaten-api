"""
Request statistics middleware for API usage tracking.

Increments in-memory counters per request (path, method, status).
Excludes monitor and metrics endpoints from tracking.
"""
import threading
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


# Shared state - thread-safe counters
_lock = threading.Lock()
_requests_total = 0
_requests_by_endpoint: dict[str, int] = defaultdict(int)
_requests_by_status: dict[str, int] = defaultdict(int)

# Path prefixes to exclude from stats (monitoring endpoints)
_EXCLUDED_PREFIXES = ("/monitor", "/metrics", "/health")


def _should_track(path: str) -> bool:
    """Exclude health and monitor endpoints from request stats."""
    return not any(path.startswith(prefix) for prefix in _EXCLUDED_PREFIXES)


def _normalize_path(path: str) -> str:
    """Use path for grouping; strip /v1 prefix for display."""
    p = path
    if p.startswith("/v1"):
        p = p[3:] or "/"
    return p or "/"


def record_request(path: str, method: str, status_code: int) -> None:
    """Record a request for statistics."""
    normalized = _normalize_path(path)
    if not _should_track(normalized):
        return
    status_key = str(status_code)
    with _lock:
        global _requests_total
        _requests_total += 1
        _requests_by_endpoint[normalized] += 1
        _requests_by_status[status_key] += 1


def get_request_stats() -> dict:
    """Get current request statistics (thread-safe snapshot)."""
    with _lock:
        return {
            "requests_total": _requests_total,
            "requests_by_endpoint": dict(_requests_by_endpoint),
            "requests_by_status": {k: v for k, v in sorted(_requests_by_status.items())},
        }


class RequestStatsMiddleware(BaseHTTPMiddleware):
    """Middleware that records request counts for monitoring."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.scope.get("path") or request.url.path
        method = request.method
        status = response.status_code
        record_request(path, method, status)
        return response
