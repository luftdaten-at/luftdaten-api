from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import city_router, station_router

app = FastAPI(
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
app.include_router(station_router, prefix="/v1/station")
app.include_router(city_router, prefix="/v1/city")