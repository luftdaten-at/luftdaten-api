from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from routers import city_router, station_router

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

if os.getenv('BACKGROUND_SERVICE') == 'True':
    # Scheduler starten
    scheduler.start()

    # Stellen Sie sicher, dass der Scheduler sauber beendet wird
    atexit.register(lambda: scheduler.shutdown())


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