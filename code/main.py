from fastapi import FastAPI, Depends, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from sqlalchemy.orm import Session
from database import SessionLocal

from schemas import StationDataCreate, SensorsCreate
from models import Station, Measurement, Values


def download_csv(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/v1/station/current/all/", response_class=Response)
async def get_current_station_data():
    """
    Returns the active stations with lat, lon, PM1, PM10 and PM2.5.
    """
    csv_url = "https://dev.luftdaten.at/d/station/history/all"
    csv_data = download_csv(csv_url)
    return Response(content=csv_data, media_type="text/csv")

@app.get("/v1/station/history/", response_class=Response)
async def get_history_station_data(
    station_ids: str = None,
    smooth: str = "100",
    start: str = None
):
    """
    Returns the values from a single station in a given time.
    """
    csv_url = f"https://dev.luftdaten.at/d/station/history?sid={station_ids}&smooth={smooth}&from={start}"
    csv_data = download_csv(csv_url)
    return Response(content=csv_data, media_type="text/csv")

# @app.get("/v1/city/current/", response_class=Response)
# async def get_current_station_data(
#     city: str = None
# ):
#     data = ""
#     return Response(content=data, media_type="application/json")

@app.post("/v1/station/data/")
async def create_station_data(
    station: StationDataCreate, 
    sensors: SensorsCreate, 
    db: Session = Depends(get_db)
):
    # Prüfen, ob die Station bereits existiert
    db_station = db.query(Station).filter(Station.device == station.device).first()

    if db_station is None:
        # Neue Station anlegen
        db_station = Station(
            device=station.device,
            lat=station.location.lat,
            lon=station.location.lon,
            height=float(station.location.height),
            time=station.time
        )
        db.add(db_station)
        db.commit()
        db.refresh(db_station)

    # Durch alle Sensoren iterieren
    for sensor_id, sensor_data in sensors.root.items():
        db_measurement = Measurement(
            sensor_model=sensor_data.type,
            station_id=db_station.id
        )
        db.add(db_measurement)
        db.commit()
        db.refresh(db_measurement)

        # Werte (dimension, value) für die Messung hinzufügen
        for dimension, value in sensor_data.data.items():
            db_value = Values(
                dimension=dimension,
                value=value,
                measurement_id=db_measurement.id
            )
            db.add(db_value)

    db.commit()

    return {"status": "success"}