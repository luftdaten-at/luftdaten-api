"""Tests for utils.helpers datetime helpers."""

from datetime import datetime, timezone

from utils.helpers import as_naive_utc, format_datetime_vienna_iso


def test_format_datetime_vienna_iso_from_utc_naive():
    utc_naive = datetime(2026, 1, 15, 12, 0, 0)
    s = format_datetime_vienna_iso(utc_naive)
    assert s is not None
    parsed = datetime.fromisoformat(s)
    assert parsed.astimezone(timezone.utc).replace(tzinfo=None) == utc_naive
    assert "+01:00" in s  # January: CET


def test_format_datetime_vienna_iso_from_aware_utc():
    aware = datetime(2026, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
    s = format_datetime_vienna_iso(aware)
    parsed = datetime.fromisoformat(s)
    assert parsed.astimezone(timezone.utc) == aware


def test_as_naive_utc_leaves_naive_unchanged():
    d = datetime(2026, 6, 1, 10, 0, 0)
    assert as_naive_utc(d) is d
