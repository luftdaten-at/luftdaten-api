from fastapi import FastAPI, Depends, Response, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import requests

from sqlalchemy.orm import Session
from sqlalchemy import desc
from database import get_db

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import csv
import io

from schemas import StationDataCreate, SensorsCreate
from models import Station, Measurement, Values

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
    station_ids: str = None,  # Eine Liste von alphanumerischen Station IDs (z.B. "00112233AABB,00112233CCDD")
    last_active: int = 3600,  # Zeitspanne in Sekunden, die Zeitraum angibt, in welchem Stationen aktiv gewesen sein müssen
    output_format: str = "geojson",  # Standardmäßig GeoJSON
    db: Session = Depends(get_db)
):
    """
    Current Station Data with the latest measurement.
    Wenn keine station_ids angegeben sind, werden alle Stationen ausgegeben, die in den letzten last_active Sekunden aktiv waren.
    """

    # Berechne den Zeitpunkt, ab dem die Stationen als "aktiv" gelten
    time_threshold = datetime.now(tz=ZoneInfo("Europe/Vienna")) - timedelta(seconds=last_active)

    if station_ids:
        # Station IDs als Liste von Strings (alphanumerisch, z.B. "00112233AABB")
        station_id_list = station_ids.split(",")
        # Abfrage auf die Stationen basierend auf den alphanumerischen Gerätenamen (device)
        stations = db.query(Station).filter(Station.device.in_(station_id_list)).all()

    else:
        # Abfrage auf alle Stationen, die in den letzten last_active Sekunden aktiv waren
        stations = db.query(Station).filter(Station.last_active >= time_threshold).all()
        #stations = db.query(Station).all()
    if not stations:
        raise HTTPException(status_code=404, detail="No stations found")

    # Initialisierung der Ausgabe basierend auf dem gewünschten Format
    if output_format == "geojson":
        features = []

        for station in stations:
            # Finde alle Messungen, die den gleichen Zeitpunkt wie "last_active" haben
            measurements = db.query(Measurement).filter(
                Measurement.station_id == station.id,
                Measurement.time_measured == station.last_active
            ).all()

            # Für jede Messung die zugehörigen Values abfragen
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
            # Finde alle Messungen, die den gleichen Zeitpunkt wie "last_active" haben
            measurements = db.query(Measurement).filter(
                Measurement.station_id == station.id,
                Measurement.time_measured == station.last_active
            ).all()

            # Für jede Messung die zugehörigen Values abfragen
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

    # Prüfen, ob die Station bereits existiert
    db_station = db.query(Station).filter(Station.device == station.device).first()

    if db_station is None:
        # Neue Station anlegen
        db_station = Station(
            device=station.device,
            firmware=station.firmware,
            apikey=station.apikey,
            lat=station.location.lat,
            lon=station.location.lon,
            height=float(station.location.height),
            last_active=station.time
        )
        db.add(db_station)
        db.commit()
        db.refresh(db_station)
    else:
        if db_station.apikey != station.apikey:
            # Fehler werfen, wenn der APIKEY nicht übereinstimmt
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        # Station existiert bereits, prüfe und aktualisiere ggf. lon, lat, height und firmware
        updated = False
        if (db_station.lat != station.location.lat or 
            db_station.lon != station.location.lon or
            db_station.height != float(station.location.height) or
            db_station.firmware != station.firmware):
            
            # Aktualisierung der Station mit den neuen Werten
            db_station.lat = station.location.lat
            db_station.lon = station.location.lon
            db_station.height = float(station.location.height)
            db_station.firmware = station.firmware
            updated = True

        if updated:
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
            # Fehler werfen, wenn die Messung bereits existiert
            raise HTTPException(
                status_code=422,
                detail="Measurement already in Database"
            )

        # Wenn keine bestehende Messung gefunden wurde, füge eine neue hinzu
        db_measurement = Measurement(
            sensor_model=sensor_data.type,
            station_id=db_station.id,
            time_measured=station.time,  # Die Zeit der Messung (aus den Daten)
            time_received=time_received  # Empfangszeit des Requests
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