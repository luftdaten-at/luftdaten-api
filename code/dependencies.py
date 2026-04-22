"""FastAPI dependencies for request-scoped and app-scoped values."""
import os
import secrets

from fastapi import HTTPException, Request, status


def verify_admin_api_key(request: Request) -> None:
    """
    Require ``Authorization: Bearer <token>`` matching ``ADMIN_API_KEY`` (env).

    Uses constant-time comparison. If ``ADMIN_API_KEY`` is unset, returns 503.
    """
    configured = os.getenv("ADMIN_API_KEY", "").strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API key is not configured.",
        )
    auth = request.headers.get("Authorization") or ""
    prefix = "Bearer "
    if not auth.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin authentication.",
        )
    token = auth[len(prefix) :].strip()
    try:
        ok = secrets.compare_digest(token, configured)
    except (TypeError, ValueError):
        ok = False
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin authentication.",
        )


def get_blacklist(request: Request) -> frozenset[str]:
    """
    Get the set of blacklisted station device IDs.

    Loaded at app startup from config/station_blacklist.json.
    Returns empty frozenset if not yet loaded (e.g. during tests).
    """
    return getattr(request.app.state, "blacklisted_station_ids", frozenset())
