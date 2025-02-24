from fastapi import APIRouter, BackgroundTasks, Depends, Response, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text, case
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from database import get_db
import csv
import json
import io
from functools import wraps
from enum import Enum
from itertools import groupby

from models import Station, Location, Measurement, Values, StationStatus, HourlyDimensionAverages, City
from schemas import StationDataCreate, SensorsCreate, StationStatusCreate
from utils import get_or_create_location, download_csv, get_or_create_station, standard_output_to_csv, standard_output_to_json
from enums import Precision, OutputFormat, Order, Dimension


router = APIRouter()


# Old endpoints for compatability reason
@router.get("/current/all", response_class=Response)
async def get_current_station_data_all(db: Session = Depends(get_db)):
    """
    Returns the active stations with lat, lon, PM1, PM10 and PM2.5.
    """

    PM2_5_LOWER_BOUND, PM2_5_UPPER_BOUND = Dimension.get_filter_threshold(Dimension.PM2_5)

    q = (
        db.query(
            Station.device,
            Location.lat,
            Location.lon,
            func.avg(case((Values.dimension == Dimension.PM1_0, Values.value))).label("PM1"),
            func.avg(case((Values.dimension == Dimension.PM2_5, Values.value))).label("PM2_5"),
            func.avg(case((Values.dimension == Dimension.PM10_0, Values.value))).label("PM10"),
        )
        .join(Measurement, Measurement.station_id == Station.id)
        .join(Location, Location.id == Measurement.location_id)
        .join(Values, Values.measurement_id == Measurement.id)
        .filter(Station.last_active == Measurement.time_measured)
        .group_by(
            Station.id,
            Station.device,
            Measurement.id,
            Measurement.time_measured,
            Location.lat,
            Location.lon
        )
        .having(func.avg(case((Values.dimension == Dimension.PM2_5, Values.value))) > PM2_5_LOWER_BOUND)
        .having(func.avg(case((Values.dimension == Dimension.PM2_5, Values.value))) < PM2_5_UPPER_BOUND)
        .order_by(Measurement.time_measured)
    )

    csv = "sid,latitude,longitude,pm1,pm25,pm10\n"
    csv += "\n".join(",".join([str(y) for y in x]) for x in q.all())

    return Response(content=csv, media_type="text/csv")


@router.get("/history", response_class=Response)
async def get_history_station_data(
    station_ids: str = None,
    smooth: str = "100",
    start: str = Query(None, description="Supply in ISO format: YYYY-MM-DDThh:mm+xx:xx. Time is optional."),
    db: Session = Depends(get_db)
):
    """
    Returns the values from a single station in a given time.
    """

    # TODO: wich time zone should the user enter
    start_time = datetime.fromisoformat(start) if start else None
    station_ids = station_ids.split(',') if station_ids else None

    q = (
        db.query(
            Measurement.time_measured,
            Station.device,
            Location.lat,
            Location.lon,
            func.avg(case((Values.dimension == 2, Values.value))).label("PM1"),
            func.avg(case((Values.dimension == 3, Values.value))).label("PM2_5"),
            func.avg(case((Values.dimension == 5, Values.value))).label("PM10"),
        )
        .join(Measurement, Measurement.station_id == Station.id)
        .join(Location, Location.id == Measurement.location_id)
        .join(Values, Values.measurement_id == Measurement.id)
        .group_by(
            Station.id,
            Station.device,
            Measurement.id,
            Measurement.time_measured,
            Location.lat,
            Location.lon
        )
        .having(func.avg(case((Values.dimension == 2, Values.value))).isnot(None))
        .having(func.avg(case((Values.dimension == 3, Values.value))).isnot(None))
        .having(func.avg(case((Values.dimension == 5, Values.value))).isnot(None))
        .order_by(Measurement.time_measured)
    )

    if station_ids:
        q = q.filter(Station.device.in_(station_ids))

    if start_time:
        q = q.filter(Measurement.time_measured >= start_time)

    csv = "timestamp,sid,latitude,longitude,pm1,pm25,pm10\n"
    csv += "\n".join(
        ",".join([time.isoformat()] + [str(o) for o in other])
        for time, *other in q.all()
    )

    return Response(content=csv, media_type="text/csv")

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

@router.post("/status", tags=["station"])
async def create_station_status(
    station: StationDataCreate,
    status_list: list[StationStatusCreate],
    db: Session = Depends(get_db)
):

    db_station = get_or_create_station(
        db=db,
        station=station
    )

    for status in status_list:
        db_status = StationStatus(
            station_id = db_station.id,
            timestamp = status.time,
            level = status.level,
            message = status.message
        )
        db.add(db_status)
        db.commit()
        db.refresh(db_status)

    return {"status": "success"}


@router.post("/data", tags=["station"])
async def create_station_data(
    station: StationDataCreate,
    sensors: SensorsCreate,
    db: Session = Depends(get_db)
):

    print(station)

    db_station = get_or_create_station(
        db = db,
        station = station
    )

    # Empfangszeit des Requests erfassen
    time_received = datetime.now(timezone.utc)

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
        
    db_station.last_active = station.time

    db.commit()

    return {"status": "success"}


@router.get("/topn", response_class=Response, tags=["station"])
async def get_topn_stations_by_dim(
    n: int = Query(..., description="limit"),
    dimension: int = Query(..., description="Dimension ID to compare"),
    order: Order = Query(Order.MIN, description="Get (Min/Max) n stations"),
    output_format: OutputFormat = Query(OutputFormat.CSV, description="Ouput format"),
    db: Session = Depends(get_db)
):

    LOWER_BOUND, UPPER_BOUND = Dimension.get_filter_threshold(dimension)

    compare = Values.value
    if order == Order.MAX:
        compare = Values.value.desc()
    q = (
        db.query(
            Station.device,
            Measurement.time_measured,
            Values.dimension,
            Values.value,
        )
        .join(Measurement, Measurement.station_id == Station.id)
        .join(Values, Values.measurement_id == Measurement.id)
        .filter(Station.last_active == Measurement.time_measured)
        .filter(Values.dimension == dimension)
        .filter(Values.value > LOWER_BOUND)
        .filter(Values.value < UPPER_BOUND)
        .order_by(compare)
        .limit(n)
    )

    if output_format == 'csv':
        return Response(content=standard_output_to_csv(q.all()), media_type="text/csv")
    elif output_format == 'json':
        return Response(content=standard_output_to_json(q.all()), media_type="application/json")


@router.get("/historical", response_class=Response, tags=["station"])
async def get_historical_station_data(
    station_ids: str = Query(..., description="Comma-separated list of station devices"),
    start: str = Query(None, description="Supply in ISO format: YYYY-MM-DDThh:mm+xx:xx. Time is optional."),
    end: str = Query(None, description="Supply in ISO format: YYYY-MM-DDThh:mm+xx:xx. Time is optional."),
    precision: Precision = Query(Precision.MAX, description="Precision of data points"),
    city_slugs: str = Query(None, description="Comma-seperated list of city_slugs"),
    output_format: OutputFormat = Query(OutputFormat.CSV, description="Ouput format"),
    db: Session = Depends(get_db)
):
    # Konvertiere die Liste von station_devices in eine Liste
    devices = station_ids.split(",") if station_ids else []
    cities = city_slugs.split(",") if city_slugs else [] 

    # Konvertiere start und end in datetime-Objekte
    try:
        start_date = datetime.fromisoformat(start) if start else None
        end_date = datetime.fromisoformat(end) if end else None 
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DDThh:mm")

    time_fram = Precision.get_time_frame(precision)
    truncated_time = func.date_trunc(time_fram, Measurement.time_measured).label('time')

    q = (
        db.query(
            Station.device,
            truncated_time,
            Values.dimension,
            func.avg(Values.value).label('avg_value')
        )
        .join(Values)
        .join(Station)
        .filter(or_(not devices, Station.device.in_(devices)))
        .join(Location)
        .outerjoin(City)
        .filter(or_(not cities, City.slug.in_(cities)))
        .group_by(Measurement.station_id, Station.device, truncated_time, Values.dimension)
        .order_by(Measurement.station_id, Station.device, truncated_time, Values.dimension)
    )

    if start_date is not None:
        q = q.filter(truncated_time >= start_date)
    if end_date is not None:
        q = q.filter(truncated_time <= end_date)

    if output_format == 'csv':
        return Response(content=standard_output_to_csv(q.all()), media_type="text/csv")
    elif output_format == 'json':
        return Response(content=standard_output_to_json(q.all()), media_type="application/json")


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