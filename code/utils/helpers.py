"""
General helper utilities.

This module contains general-purpose helper functions.
"""

from datetime import datetime, timezone


def as_naive_utc(dt: datetime) -> datetime:
    """Normalize to UTC naive for TIMESTAMP WITHOUT TIME ZONE columns (asyncpg-safe)."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def max_as_naive_utc(a: datetime, b: datetime) -> datetime:
    """Compare two datetimes (naive assumed UTC) and return the later as naive UTC."""
    a_aware = a.replace(tzinfo=timezone.utc) if a.tzinfo is None else a.astimezone(timezone.utc)
    b_aware = b.replace(tzinfo=timezone.utc) if b.tzinfo is None else b.astimezone(timezone.utc)
    return max(a_aware, b_aware).replace(tzinfo=None)


def float_default(x, default=None):
    """
    Try to convert x to float, return default if conversion fails.
    
    Args:
        x: Value to convert to float
        default: Default value to return if conversion fails (default: None)
    
    Returns:
        float value if conversion succeeds, otherwise default value
    """
    try:
        return float(x)
    except (ValueError, TypeError):
        return default
