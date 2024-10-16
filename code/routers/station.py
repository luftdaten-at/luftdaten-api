from fastapi import APIRouter, BackgroundTasks, Depends, Response, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import get_db
import csv
import json
import io

from models import Station, Location, Measurement, Values
from schemas import StationDataCreate, SensorsCreate
from utils import get_or_create_location, download_csv
from services.hourly_average import calculate_hourly_average

router = APIRouter()


# Old endpoints for compatability reason
@router.get("/current/all", response_class=Response)
async def get_current_station_data_all():
    """
    Returns the active stations with lat, lon, PM1, PM10 and PM2.5.
    """
    csv_url = "https://dev.luftdaten.at/d/station/history/all"
    csv_data = download_csv(csv_url)
    return Response(content=csv_data, media_type="text/csv")

@router.get("/history", response_class=Response)
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


# New endpoints
@router.get("/current", response_class=Response, tags=["station", "current"])
async def get_current_station_data(
    station_ids: str = None,
    last_active: int = 3600,
    output_format: str = "geojson",
    db: Session = Depends(get_db)
):
    """
    Returns the latest data of active stations.
    """

    time_threshold = datetime.now(tz=ZoneInfo("Europe/Vienna")) - timedelta(seconds=last_active)

    if station_ids:
        station_id_list = station_ids.split(",")
        stations = db.query(Station).join(Location).filter(Station.device.in_(station_id_list)).all()
    else:
        stations = db.query(Station).join(Location).filter(Station.last_active >= time_threshold).all()

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
                    "coordinates": [station.location.lon, station.location.lat],
                },
                "properties": {
                    "device": station.device,
                    "time": str(station.last_active),
                    "height": station.location.height,
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


@router.post("/data", tags=["station"])
async def create_station_data(
    station: StationDataCreate, 
    sensors: SensorsCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Empfangszeit des Requests erfassen
    time_received = datetime.now()

    # Prüfen, ob die Station bereits existiert
    db_station = db.query(Station).filter(Station.device == station.device).first()

    if db_station is None:
        # Neue Station und neue Location anlegen
        new_location = Location(
            lat=station.location.lat,
            lon=station.location.lon,
            height=float(station.location.height)
        )
        db.add(new_location)
        db.commit()
        db.refresh(new_location)

        # Neue Station anlegen und das source-Feld überprüfen (Standardwert ist 1)
        db_station = Station(
            device=station.device,
            firmware=station.firmware,
            apikey=station.apikey,
            location_id=new_location.id,
            last_active=station.time,
            source=station.source if station.source is not None else 1
        )
        db.add(db_station)
        db.commit()
        db.refresh(db_station)
    else:
        # Station existiert, API-Schlüssel überprüfen
        if db_station.apikey != station.apikey:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        updated = False

        # Überprüfen, ob Location aktualisiert werden muss
        if db_station.location is None or (
            db_station.location.lat != station.location.lat or 
            db_station.location.lon != station.location.lon or
            db_station.location.height != float(station.location.height)
        ):
            new_location = get_or_create_location(db, station.location.lat, station.location.lon, float(station.location.height))
            db_station.location_id = new_location.id
            updated = True

        if db_station.firmware != station.firmware:
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

    # Starte die Berechnung der stündlichen Durchschnittswerte im Hintergrund
    background_tasks.add_task(calculate_hourly_average, db_station.id, db)

    return {"status": "success"}


@router.get("/historical", response_class=Response, tags=["station"])
async def get_historical_station_data(
    station_ids: str = Query(..., description="Comma-separated list of station devices"),
    start: str = Query(..., description="Supply in format: YYYY-MM-DDThh:mm. Time is optional."),
    end: str = Query(..., description="Supply in format: YYYY-MM-DDThh:mm. Time is optional."),
    output_format: str = "csv",
    db: Session = Depends(get_db)
):
    # Konvertiere die Liste von station_devices in eine Liste
    devices = station_ids.split(",") if station_ids else []

    # Konvertiere start und end in datetime-Objekte
    try:
        start_date = datetime.strptime(start, "%Y-%m-%dT%H:%M") if start else None
        end_date = datetime.strptime(end, "%Y-%m-%dT%H:%M") if end else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DDThh:mm")

    # Datenbankabfrage, um die Stationen nach station_device zu filtern
    query = db.query(Measurement).join(Station).filter(Station.device.in_(devices))

    if start_date:
        query = query.filter(Measurement.time_measured >= start_date)
    if end_date:
        query = query.filter(Measurement.time_measured <= end_date)

    measurements = query.all()

    if not measurements:
        return Response(status_code=404, content="No data found for the specified devices and time range.")

    if output_format == "csv":
        csv_data = "device,time_measured,dimension,value\n"
        for measurement in measurements:
            for value in measurement.values:
                csv_data += f"{measurement.station.device},{measurement.time_measured},{value.dimension},{value.value}\n"
        return Response(content=csv_data, media_type="text/csv")
    else:
        json_data = [
            {
                "device": measurement.station.device,
                "time_measured": measurement.time_measured,
                "values": [{"dimension": value.dimension, "value": value.value} for value in measurement.values]
            }
            for measurement in measurements
        ]
        return Response(content=json.dumps(json_data), media_type="application/json")

@router.get("/all", response_class=Response, tags=["station"])
async def get_all_stations(
    output_format: str = Query(default="csv", enum=["json", "csv"]),
    db: Session = Depends(get_db)
):
    """
    Return all registered stations with their locations and number of measurements.
    """
    # Abfrage aller Stationen mit zugehörigen Location und Measurements
    stations = db.query(Station).all()

    # Struktur für die Antwort vorbereiten
    result = []
    for station in stations:
        # Zähle die Anzahl der Measurements, die mit dieser Station verknüpft sind
        measurements_count = db.query(Measurement).filter(Measurement.station_id == station.id).count()

        # Erstelle das Ausgabeobjekt für jede Station
        station_data = {
            "id": station.device,
            "last_active": station.last_active,
            "location": {
                "lat": station.location.lat if station.location else None,
                "lon": station.location.lon if station.location else None
            },
            "measurements_count": measurements_count
        }
        result.append(station_data)

    # Rückgabe als JSON
    if output_format == "json":
        return result
    
    # Rückgabe als CSV
    else:
        output = io.StringIO()
        writer = csv.writer(output)

        # Schreibe Header
        writer.writerow(["id", "last_active", "location_lat", "location_lon", "measurements_count"])

        # Schreibe Daten
        for station in result:
            writer.writerow([
                station["id"],
                station["last_active"],
                station["location"]["lat"],
                station["location"]["lon"],
                station["measurements_count"]
            ])

        response = Response(content=output.getvalue(), media_type="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=stations.csv"
        return response