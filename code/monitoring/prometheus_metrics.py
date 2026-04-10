"""
Custom Prometheus metrics: per-area request counter (Phase C) and application gauges (Phase D).

Default HTTP metrics still come from prometheus-fastapi-instrumentator; this module adds
`luftdaten_*` series for Grafana roll-ups and health signals.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import metrics as instrumentator_metrics
from sqlalchemy import text

from database import sync_engine

logger = logging.getLogger(__name__)

# --- Phase C: low-cardinality "area" for executive / grouped dashboards ---
LUFTDATEN_HTTP_REQUESTS_TOTAL = Counter(
    "luftdaten_http_requests_total",
    "HTTP requests by logical API area (status is grouped 2xx/4xx/… like instrumentator).",
    labelnames=("area", "method", "status"),
)

# --- Phase D: refreshed on a timer, not on every request ---
LUFTDATEN_BLACKLIST_SIZE = Gauge(
    "luftdaten_blacklist_size",
    "Number of station IDs in the blacklist config.",
)
LUFTDATEN_SCHEDULER_JOBS = Gauge(
    "luftdaten_scheduler_jobs",
    "Number of registered APScheduler jobs.",
)
LUFTDATEN_DB_UP = Gauge(
    "luftdaten_db_up",
    "1 if SELECT 1 succeeds, else 0.",
)


def handler_to_area(handler: str) -> str:
    """Map route template to a small fixed set of label values."""
    if not handler or handler == "none":
        return "other"
    if handler.startswith("/station"):
        return "station"
    if handler.startswith("/city"):
        return "city"
    if handler.startswith("/statistics"):
        return "statistics"
    if handler.startswith("/health"):
        return "health"
    if handler.startswith("/monitor"):
        return "monitor"
    if handler.startswith("/metrics"):
        return "metrics"
    return "other"


def instrumentation_record_area(info: instrumentator_metrics.Info) -> None:
    """Instrumentator callback: one increment per non-excluded request."""
    area = handler_to_area(info.modified_handler)
    LUFTDATEN_HTTP_REQUESTS_TOTAL.labels(
        area=area,
        method=info.method,
        status=info.modified_status,
    ).inc()


def update_prometheus_app_gauges(app: Any, scheduler: Optional[Any] = None) -> None:
    """Update blacklist, scheduler, and DB gauges. Safe for APScheduler."""
    try:
        bl = getattr(app.state, "blacklisted_station_ids", None)
        LUFTDATEN_BLACKLIST_SIZE.set(len(bl) if bl is not None else 0)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("luftdaten_blacklist_size gauge: %s", exc)
        LUFTDATEN_BLACKLIST_SIZE.set(0)

    try:
        if scheduler is not None and getattr(scheduler, "running", False):
            LUFTDATEN_SCHEDULER_JOBS.set(len(scheduler.get_jobs()))
        else:
            LUFTDATEN_SCHEDULER_JOBS.set(0)
    except Exception as exc:  # pragma: no cover
        logger.debug("luftdaten_scheduler_jobs gauge: %s", exc)
        LUFTDATEN_SCHEDULER_JOBS.set(0)

    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        LUFTDATEN_DB_UP.set(1)
    except Exception:
        LUFTDATEN_DB_UP.set(0)
