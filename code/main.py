from fastapi import FastAPI, Depends, Response, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import requests

from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json

from schemas import StationDataCreate, SensorsCreate
from models import Measurement, Station, Values

from enums import SensorModel


app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Helper function to get or create a location
def get_or_create_location(db: Session, lat: float, lon: float, height: float):
    # Prüfen, ob bereits eine Location mit lat, lon und height existiert
    location = db.query(Location).filter(
        Location.lat == lat,
        Location.lon == lon,
        Location.height == height
    ).first()

    # Falls keine existiert, erstelle eine neue Location
    if location is None:
        location = Location(lat=lat, lon=lon, height=height)
        db.add(location)
        db.commit()
        db.refresh(location)

    return location

# Old endpoints for compatability reason

def download_csv(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

@app.get("/v1/station/current/all/", response_class=Response)
async def get_current_station_data_all():
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


@app.get("/v1/station/current", response_class=Response)
async def get_current_station_data(
    station_ids: str = None,
    last_active: int = 3600,
    output_format: str = "geojson",
    db: Session = Depends(get_db)
):
    """
    Current Station Data with the latest measurement.
    Wenn keine station_ids angegeben sind, werden alle Stationen ausgegeben, die in den letzten last_active Sekunden aktiv waren.
    """

    # Berechne den Zeitpunkt, ab dem die Stationen als "aktiv" gelten
    time_threshold = datetime.now(tz=ZoneInfo("Europe/Vienna")) - timedelta(seconds=last_active)

    if station_ids:
        station_id_list = station_ids.split(",")
        stations = db.query(Station).filter(Station.device.in_(station_id_list)).all()
    else:
        stations = db.query(Station).filter(Station.last_active >= time_threshold).all()

    if not stations:
        raise HTTPException(status_code=404, detail="No stations found")

    if output_format == "geojson":
        features = []
        for station in stations:
            measurements = db.query(Measurement).filter(
                Measurement.station_id == station.id,
                Measurement.time_measured == station.last_active
            ).all()

            sensors = []
            for measurement in measurements:
                values = db.query(Values).filter(Values.measurement_id == measurement.id).all()
                sensors.append({
                    "sensor_model": measurement.sensor_model,
                    "values": [{"dimension": value.dimension, "value": value.value} for value in values]
                })

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [station.lon, station.lat],
                },
                "properties": {
                    "device": station.device,
                    "time": str(station.last_active),
                    "height": station.height,
                    "sensors": sensors
                }
            })

        content = {
            "type": "FeatureCollection",
            "features": features,
        }
        content = json.dumps(content)
        media_type = "application/geo+json"

    elif output_format == "csv":
        csv_data = "device,lat,lon,last_active,height,sensor_model,dimension,value\n"
        for station in stations:
            measurements = db.query(Measurement).filter(
                Measurement.station_id == station.id,
                Measurement.time_measured == station.last_active
            ).all()

            for measurement in measurements:
                values = db.query(Values).filter(Values.measurement_id == measurement.id).all()

                for value in values:
                    csv_data += f"{station.device},{station.lat},{station.lon},{station.last_active},{station.height},{measurement.sensor_model},{value.dimension},{value.value}\n"

        content = csv_data
        media_type = "text/csv"

    else:
        return Response(content="Invalid output format", media_type="text/plain", status_code=400)

    return Response(content=content, media_type=media_type)


@app.post("/v1/station/data/")
async def create_station_data(
    station: StationDataCreate, 
    sensors: SensorsCreate, 
    db: Session = Depends(get_db)
):
    # Empfangszeit des Requests erfassen
    time_received = datetime.now()

    # Hole oder erstelle eine Location basierend auf lat, lon, height
    location = get_or_create_location(db, station.location.lat, station.location.lon, float(station.location.height))

    # Prüfen, ob die Station bereits existiert
    db_station = db.query(Station).filter(Station.device == station.device).first()

    if db_station is None:
        # Neue Station anlegen und mit der Location verknüpfen
        db_station = Station(
            device=station.device,
            firmware=station.firmware,
            apikey=station.apikey,
            last_active=station.time,
            location_id=location.id  # Verknüpfung zur Location
        )
        db.add(db_station)
        db.commit()
        db.refresh(db_station)
    else:
        if db_station.apikey != station.apikey:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        # Prüfen, ob die Location-Daten abweichen
        if (db_station.location.lat != station.location.lat or 
            db_station.location.lon != station.location.lon or
            db_station.location.height != float(station.location.height)):
            
            # Erstelle eine neue Location, wenn die aktuellen Standortdaten abweichen
            new_location = get_or_create_location(db, station.location.lat, station.location.lon, float(station.location.height))
            db_station.location_id = new_location.id  # Verknüpfe die Station mit der neuen Location
            db.commit()

        # Prüfe und aktualisiere die Firmware, falls sie abweicht
        if db_station.firmware != station.firmware:
            db_station.firmware = station.firmware
            db.commit()

    # Durch alle Sensoren iterieren
    for sensor_id, sensor_data in sensors.root.items():
        # Prüfen, ob bereits eine Messung mit dem gleichen time_measured und sensor_model existiert
        existing_measurement = db.query(Measurement).filter(
            Measurement.station_id == db_station.id,
            Measurement.time_measured == station.time,
            Measurement.sensor_model == sensor_data.type
        ).first()

        if existing_measurement:
            raise HTTPException(
                status_code=422,
                detail="Measurement already in Database"
            )

        # Wenn keine bestehende Messung gefunden wurde, füge eine neue hinzu
        db_measurement = Measurement(
            sensor_model=sensor_data.type,
            station_id=db_station.id,
            time_measured=station.time,
            time_received=time_received,
            location_id=db_station.location_id  # Verknüpfe die Messung mit der neuen Location
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