"""FastAPI dependencies for request-scoped and app-scoped values."""
from fastapi import Request


def get_blacklist(request: Request) -> frozenset[str]:
    """
    Get the set of blacklisted station device IDs.

    Loaded at app startup from config/station_blacklist.json.
    Returns empty frozenset if not yet loaded (e.g. during tests).
    """
    return getattr(request.app.state, "blacklisted_station_ids", frozenset())
