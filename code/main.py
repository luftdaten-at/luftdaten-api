from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import city_router, station_router

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Register routers
app.include_router(station_router, prefix="/v1/station")
app.include_router(city_router, prefix="/v1/city")