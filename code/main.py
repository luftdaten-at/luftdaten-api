from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import city_router, station_router

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

# Register routers
app.include_router(station_router, prefix="/station")
app.include_router(city_router, prefix="/city")