from fastapi import FastAPI, Request
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