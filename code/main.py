from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from monitoring.prometheus_metrics import (
    instrumentation_record_area,
    update_prometheus_app_gauges,
)
from routers import city_router, station_router, health_router, statistics_router
from routers.monitor import router as monitor_router
from routers.health import set_scheduler
from utils.blacklist import load_blacklist_from_file
from middleware.request_stats import RequestStatsMiddleware

from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from tasks.periodic_tasks import import_sensor_community_data, refresh_statistics_cache, refresh_stations_summary_cache

from database import scheduler_async_engine

import os
import logging

# Lese das Logging-Level aus der Umgebungsvariablen "LOG_LEVEL" (Standard ist "INFO")
log_level = os.getenv("LOG_LEVEL", "INFO").upper()

# Mapping von String-Level zu tatsächlichen Logging-Level-Objekten
log_level_mapping = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}

# Setze das Logging-Level basierend auf der Umgebungsvariablen
logging.basicConfig(level=log_level_mapping.get(log_level, logging.INFO))


def _cors_allowlist():
    """
    CORS: `allow_origins=['*']` must not be combined with `allow_credentials=True`
    (browser will block; fetch with credentials: 'include' requires an explicit origin).
    Override with CORS_ORIGINS (comma-separated). Use CORS_ORIGINS=* for public wildcard
    without credentials.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw == "*":
        return ["*"], False
    if raw:
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        cred = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() in ("1", "true", "yes")
        return origins, cred
    return (
        [
            "https://datahub.luftdaten.at",
            "https://www.luftdaten.at",
            "https://luftdaten.at",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        True,
    )


_cors_origins, _cors_credentials = _cors_allowlist()

app = FastAPI(
    title="Luftdaten.at API",
    description="Open source database, analytics and API for air quality and micro climate data.",
    version="0.3",
    servers=[
        {"url": "/v1", "description": "Main API server"},
    ],
    openapi_tags=[
        {
            "name": "station",
            "description": "Operations related to station data (e.g., historical, current)."
        },
        {
            "name": "city",
            "description": "Operations related to city-level data."
        },
        {
            "name": "current",
            "description": "Operations related to getting current data (e.g., for stations, cities)."
        },
        {
            "name": "health",
            "description": "Health check endpoints to monitor API status and dependencies."
        },
        {
            "name": "statistics",
            "description": "Statistics endpoints to get database statistics and analytics."
        },
        {
            "name": "monitor",
            "description": "Monitoring and observability (database usage, API stats, Prometheus metrics)."
        }
    ]
)

app.add_middleware(RequestStatsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_credentials,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()

# Planen Sie die Aufgabe alle 5 Minuten
scheduler.add_job(import_sensor_community_data, 'interval', minutes=5)

# Refresh statistics materialized views every hour
scheduler.add_job(refresh_statistics_cache, 'interval', hours=1)

# Refresh stations summary materialized view every 10 minutes
scheduler.add_job(refresh_stations_summary_cache, 'interval', minutes=10)

# Scheduler starten
scheduler.start()


def refresh_prometheus_gauges():
    """Periodic refresh of luftdaten_* gauges (blacklist, scheduler, DB up)."""
    update_prometheus_app_gauges(app, scheduler)


scheduler.add_job(
    refresh_prometheus_gauges,
    "interval",
    minutes=1,
    id="prometheus_app_gauges",
    replace_existing=True,
)

# Stellen Sie sicher, dass der Scheduler sauber beendet wird
def shutdown_scheduler():
    """Shutdown scheduler, handling potential logging errors during test teardown"""
    try:
        # Suppress scheduler's logger to prevent logging errors when handlers are closed
        scheduler_logger = logging.getLogger('apscheduler')
        original_level = scheduler_logger.level
        scheduler_logger.setLevel(logging.CRITICAL)
        
        # Also disable all handlers temporarily
        original_handlers = scheduler_logger.handlers[:]
        scheduler_logger.handlers.clear()
        
        try:
            scheduler.shutdown()
        finally:
            try:
                scheduler_async_engine.sync_engine.dispose()
            except Exception:
                pass
            # Restore logger state (though this may not work if logging is already shut down)
            try:
                scheduler_logger.setLevel(original_level)
                scheduler_logger.handlers = original_handlers
            except (ValueError, OSError, AttributeError):
                pass
    except (ValueError, OSError, AttributeError):
        # Ignore any errors during shutdown - logging may already be closed
        pass

atexit.register(shutdown_scheduler)


@app.on_event("startup")
def load_station_blacklist():
    """Load station blacklist from config file into app state."""
    app.state.start_time = datetime.now(timezone.utc)
    try:
        app.state.blacklisted_station_ids = load_blacklist_from_file()
    except Exception as e:
        logging.getLogger(__name__).error("Failed to load station blacklist: %s", e)
        app.state.blacklisted_station_ids = frozenset()
    refresh_prometheus_gauges()


# Middleware to add /v1 prefix to all routes
@app.middleware("http")
async def add_version_prefix(request: Request, call_next):
    if request.url.path.startswith("/v1"):
        request.scope["path"] = request.url.path[3:]  # Remove '/v1' from the path
    response = await call_next(request)
    return response

# Register routers
app.include_router(station_router, prefix="/station")
app.include_router(city_router, prefix="/city")
app.include_router(health_router, prefix="/health")
app.include_router(statistics_router, prefix="/statistics")
app.include_router(monitor_router, prefix="/monitor")

# Prometheus: tuned defaults + per-area counter; scrape noise excluded via handler regex
_LATENCY_LOWR_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0)
Instrumentator(
    excluded_handlers=[
        r"^/metrics$",
        r"^/health/simple$",
        r"^/monitor(/.*)?$",
    ],
    should_round_latency_decimals=True,
    round_latency_decimals=4,
).add(instrumentation_record_area).instrument(
    app,
    latency_lowr_buckets=_LATENCY_LOWR_BUCKETS,
).expose(app, endpoint="/metrics")

# Set scheduler reference for health checks
set_scheduler(scheduler)