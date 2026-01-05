from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import city_router, station_router, health_router, statistics_router
from routers.health import set_scheduler

from apscheduler.schedulers.background import BackgroundScheduler
import atexit
from tasks.periodic_tasks import import_sensor_community_data

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
        }
    ]
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()

# Planen Sie die Aufgabe alle 5 Minuten
scheduler.add_job(import_sensor_community_data, 'interval', minutes=5)

# Scheduler starten
scheduler.start()

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

# Set scheduler reference for health checks
set_scheduler(scheduler)