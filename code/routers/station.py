import csv
import json
import io
import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, Response, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text, case
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from database import get_db
from functools import wraps
from enum import Enum
from collections import defaultdict

from models import Station, Location, Measurement, CalibrationMeasurement, Values, StationStatus, HourlyDimensionAverages, City
from schemas import StationDataCreate, SensorsCreate, StationStatusCreate
from utils import get_or_create_location, download_csv, get_or_create_station, standard_output_to_csv, standard_output_to_json
from enums import Precision, OutputFormat, Order, Dimension, CURRENT_TIME_RANGE_MINUTES


router = APIRouter()


@router.get('/calibration', response_class=Response, tags=['station', 'calibration'])
async def get_calibration_data(
    station_ids: str = Query(None, description="Comma-separated list of station device IDs to filter by. If not provided, all stations with calibration data are returned."),
    data: bool = Query(True, description="If True, returns calibration measurement data. If False, returns only station device IDs."),
    hours: int = Query(1, description="Number of hours to look back for calibration measurements. Default is 1 hour."),
    db: Session = Depends(get_db)
):
    """
    Get calibration data for stations.
    
    Returns calibration measurements in CSV format. Calibration data is used to improve
    measurement accuracy by comparing sensor readings against known reference values.
    
    **Parameters:**
    - **station_ids**: Optional comma-separated list of station device IDs
    - **data**: If True, returns full calibration data (device, sensor_model, dimension, value, time).
                If False, returns only station device IDs.
    - **hours**: Time window in hours to look back for calibration measurements
    
    **Response Format:**
    - CSV format with columns: device, sensor_model, dimension, value, time_measured
    - If data=False: CSV with single column of station device IDs
    
    **Example Response:**
    ```
    device,sensor_model,dimension,value,time_measured
    station_123,13,3,15.5,2024-01-01T12:00:00
    ```
    """
    stations = db.query(Station).join(Station.calibration_measurements).all()
    if station_ids is not None:
        station_id_list = station_ids.split(",")
        stations = db.query(Station).filter(Station.device.in_(station_id_list)).all()
    # csv
    # device id, sensor.model, dimension, value, time
    csv = []
    lower = datetime.now(timezone.utc) - timedelta(hours=hours)
    if data:
        measurements = []
        for station in stations:
            q = db.query(CalibrationMeasurement).filter(CalibrationMeasurement.station_id == station.id, CalibrationMeasurement.time_measured >= lower)
            #print(q)
            measurements.extend(q.all())
        for m in measurements:
            for v in m.values:
                csv.append(','.join(str(x) for x in [
                    m.station.device,
                    m.sensor_model,
                    v.dimension,
                    v.value,
                    m.time_measured,
                ]))
    else:
        for station in stations:
            csv.append(str(station.device))
    
    return Response(content='\n'.join(csv), media_type="text/csv")


@router.get("/info", response_class=Response, tags=['station'])
async def get_station_info(
    station_id: str = Query(..., description="The device ID of the station to get information for."),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific station.
    
    Returns station metadata including device ID, firmware version, location coordinates,
    last active timestamp, and all sensor measurements from the most recent measurement time.
    
    **Parameters:**
    - **station_id**: The device ID of the station (required)
    
    **Response:**
    - JSON object containing:
      - **station**: Station metadata (time, device, firmware, location)
      - **sensors**: Dictionary of sensor measurements indexed by sensor ID, containing
        sensor type and dimension-value pairs
    
    **Example Response:**
    ```json
    {
      "station": {
        "time": "2024-01-01T12:00:00",
        "device": "station_123",
        "firmware": "1.0",
        "location": {
          "lat": 48.2082,
          "lon": 16.3738,
          "height": 100.0
        }
      },
      "sensors": {
        "0": {
          "type": 13,
          "data": {
            "2": 10.5,
            "3": 15.2
          }
        }
      }
    }
    ```
    
    **Errors:**
    - 404: Station not found
    """
    station = db.query(Station).filter(Station.device == station_id).first()
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    measurements = db.query(Measurement).filter(Measurement.station_id == station.id, Measurement.time_measured == station.last_active).all()
    j = {
        "station":{
            "time": station.last_active.isoformat(),
            "device": station.device,
            "firmware": station.firmware,
            "location": {
                "lat": station.location.lat,
                "lon": station.location.lon,
                "height": station.location.height
            }
        },
        "sensors": {
            #k : {v} for k
            idx : {"type": m.sensor_model, "data": {v.dimension: v.value for v in m.values}}
            for idx, m in enumerate(measurements)
        }
    }
    return Response(content=json.dumps(j), media_type='application/json')


# Old endpoints for compatability reason
@router.get("/current/all", response_class=Response, tags=["station", "current"], deprecated=True)
async def get_current_station_data_all(
    db: Session = Depends(get_db),
):
    """
    Get all active stations with PM measurements (legacy endpoint).
    
    **Deprecated**: This endpoint is maintained for backward compatibility.
    Use `/station/current` instead for more flexible data access.
    
    Returns active stations (where last_active matches time_measured) with
    latitude, longitude, and averaged PM1, PM2.5, and PM10 values.
    
    **Response Format:**
    - CSV format with columns: sid, latitude, longitude, pm1, pm25, pm10
    - Only includes stations with valid PM2.5 values within filter thresholds
    
    **Example Response:**
    ```
    sid,latitude,longitude,pm1,pm25,pm10
    station_123,48.2082,16.3738,10.5,15.2,20.3
    ```
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


@router.get("/history", response_class=Response, tags=["station"], deprecated=True)
async def get_history_station_data(
    station_ids: str = Query(None, description="Comma-separated list of station device IDs. If not provided, all stations are included."),
    smooth: str = Query("100", description="Smoothing parameter (currently not used, maintained for compatibility)."),
    start: str = Query(None, description="Start time in ISO format: YYYY-MM-DDThh:mm+xx:xx. If not provided, returns all available data."),
    db: Session = Depends(get_db)
):
    """
    Get historical station data (legacy endpoint).
    
    **Deprecated**: This endpoint is maintained for backward compatibility.
    Use `/station/historical` instead for more flexible historical data access.
    
    Returns historical PM measurements (PM1, PM2.5, PM10) for specified stations.
    
    **Parameters:**
    - **station_ids**: Optional comma-separated list of station device IDs
    - **smooth**: Smoothing parameter (not currently used)
    - **start**: Optional start time in ISO format
    
    **Response Format:**
    - CSV format with columns: timestamp, sid, latitude, longitude, pm1, pm25, pm10
    
    **Example Response:**
    ```
    timestamp,sid,latitude,longitude,pm1,pm25,pm10
    2024-01-01T12:00:00,station_123,48.2082,16.3738,10.5,15.2,20.3
    ```
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
    station_ids: str = Query(None, description="Comma-separated list of station device IDs to filter by. If not provided, all active stations are returned."),
    last_active: int = Query(3600, description="Time window in seconds. Stations with last_active within this window are considered active. Default is 3600 seconds (1 hour)."),
    output_format: str = Query("geojson", description="Output format: 'geojson' or 'csv'. Default is 'geojson'."),
    calibration_data: bool = Query(False, description="If true, includes calibration sensor data in the response."),
    db: Session = Depends(get_db)
):
    """
    Get current measurement data from active stations.
    
    Returns the latest measurement data from stations that have been active within
    the specified time window. Data includes sensor measurements with dimensions
    and values for each sensor model.
    
    **Parameters:**
    - **station_ids**: Optional comma-separated list of station device IDs to filter
    - **last_active**: Time window in seconds (default: 3600 = 1 hour)
    - **output_format**: 'geojson' (default) or 'csv'
    - **calibration_data**: If true, includes calibration measurements
    
    **Response Formats:**
    
    **GeoJSON** (default):
    - FeatureCollection with Point geometries
    - Each feature contains station properties: device, time, height, sensors
    - Sensors array contains sensor_model and values (dimension-value pairs)
    
    **CSV**:
    - Columns: device, lat, lon, last_active, height, sensor_model, dimension, value
    - If calibration_data=true: additional 'calibration' column (true/false)
    
    **Example GeoJSON Response:**
    ```json
    {
      "type": "FeatureCollection",
      "features": [
        {
          "type": "Feature",
          "geometry": {
            "type": "Point",
            "coordinates": [16.3738, 48.2082]
          },
          "properties": {
            "device": "station_123",
            "time": "2024-01-01T12:00:00",
            "height": 100.0,
            "sensors": [
              {
                "sensor_model": 13,
                "values": [
                  {"dimension": 2, "value": 10.5},
                  {"dimension": 3, "value": 15.2}
                ]
              }
            ]
          }
        }
      ]
    }
    ```
    
    **Errors:**
    - 404: No stations found matching the criteria
    - 400: Invalid output format
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

            calibration_sensors = []
            if calibration_data:
                for calibration_measurement in db.query(CalibrationMeasurement).filter(
                    CalibrationMeasurement.station_id == station.id,
                    CalibrationMeasurement.time_measured == station.last_active
                ):
                    calibration_values = db.query(Values).filter(Values.calibration_measurement_id == calibration_measurement.id).all()
                    calibration_sensors.append({
                        "sensor_model": calibration_measurement.sensor_model,
                        "values": [{"dimension": value.dimension, "value": value.value} for value in calibration_values]
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

            if calibration_data and calibration_sensors:
                features[-1]["properties"]["calibration_sensors"] = calibration_sensors

        content = {
            "type": "FeatureCollection",
            "features": features,
        }
        content = json.dumps(content)
        media_type = "application/geo+json"

    elif output_format == "csv":
        csv_data = "device,lat,lon,last_active,height,sensor_model,dimension,value"
        if calibration_data:
            csv_data += ",calibration"
        csv_data += "\n"

        for station in stations:
            measurements = db.query(Measurement).filter(
                Measurement.station_id == station.id,
                Measurement.time_measured == station.last_active
            ).all()

            for measurement in measurements:
                values = db.query(Values).filter(Values.measurement_id == measurement.id).all()

                for value in values:
                    csv_data += f"{station.device},{station.location.lat},{station.location.lon},{station.last_active},{station.location.height},{measurement.sensor_model},{value.dimension},{value.value}"
                    if calibration_data:
                        csv_data += f',{False}'
                    csv_data += "\n"
            
            if calibration_data:
                for calibration_measurement in db.query(CalibrationMeasurement).filter(
                    CalibrationMeasurement.station_id == station.id,
                    CalibrationMeasurement.time_measured == station.last_active
                ):
                    calibration_values = db.query(Values).filter(Values.calibration_measurement_id == calibration_measurement.id).all()
                    for value in calibration_values:
                        csv_data += f"{station.device},{station.location.lat},{station.location.lon},{station.last_active},{station.location.height},{measurement.sensor_model},{value.dimension},{value.value},{True}\n"

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
    """
    Submit station status updates.
    
    Creates or updates a station and records status messages. Status messages
    can indicate station health, connectivity, or operational state.
    
    **Request Body:**
    - **station**: Station metadata (device, firmware, apikey, time, location)
    - **status_list**: Array of status messages, each containing:
      - **time**: Timestamp of the status
      - **level**: Status level (integer, typically 1=info, 2=warning, 3=error)
      - **message**: Status message text
    
    **Response:**
    ```json
    {
      "status": "success"
    }
    ```
    
    **Errors:**
    - 401: Invalid API key (if station exists with different API key)
    - 422: Validation error
    """

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
    """
    Submit measurement data from a station.
    
    Creates or updates a station and records sensor measurements. If the station
    doesn't exist, it will be created. Measurements are linked to the station
    and location.
    
    **Request Body:**
    - **station**: Station metadata including:
      - **device**: Station device ID (unique identifier)
      - **firmware**: Firmware version
      - **apikey**: API key for authentication
      - **time**: Measurement timestamp
      - **location**: Geographic location (lat, lon, height)
      - **source**: Data source (1=Luftdaten.at, 2=TTN LoRaWAN, 3=sensor.community)
      - **calibration_mode**: If true, stores as calibration measurements
    - **sensors**: Dictionary mapping sensor IDs to sensor data:
      - **type**: Sensor model ID (e.g., 13 for SDS011)
      - **data**: Dictionary mapping dimension IDs to values (e.g., {2: 10.5, 3: 15.2})
    
    **Response:**
    ```json
    {
      "status": "success"
    }
    ```
    
    **Errors:**
    - 401: Invalid API key (if station exists with different API key)
    - 422: Measurement already exists in database (duplicate time_measured + sensor_model)
    """

    MeasurementClass = Measurement

    if station.calibration_mode:
        MeasurementClass = CalibrationMeasurement

    db_station = get_or_create_station(
        db = db,
        station = station
    )

    # Empfangszeit des Requests erfassen
    time_received = datetime.now(timezone.utc)

    # Durch alle Sensoren iterieren
    for sensor_id, sensor_data in sensors.root.items():
        # Prüfen, ob bereits eine Messung mit dem gleichen time_measured und sensor_model existiert
        existing_measurement = db.query(MeasurementClass).filter(
            MeasurementClass.station_id == db_station.id,
            MeasurementClass.time_measured == station.time,
            MeasurementClass.sensor_model == sensor_data.type
        ).first()

        if existing_measurement:
            raise HTTPException(
                status_code=422,
                detail="Measurement already in Database"
            )

        # Wenn keine bestehende Messung gefunden wurde, füge eine neue hinzu
        db_measurement = MeasurementClass(
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
            db_value = None 
            if station.calibration_mode:
                db_value = Values(
                    dimension=dimension,
                    value=value,
                    calibration_measurement_id=db_measurement.id
                )
            else:
                db_value = Values(
                    dimension=dimension,
                    value=value,
                    measurement_id=db_measurement.id
                )

            db.add(db_value)
        
    db_station.last_active = max(db_station.last_active.replace(tzinfo=timezone.utc), station.time)

    db.commit()

    return {"status": "success"}


@router.get("/topn", response_class=Response, tags=["station"])
async def get_topn_stations_by_dim(
    n: int = Query(..., description="Number of stations to return (limit).", ge=1),
    dimension: int = Query(..., description="Dimension ID to compare (e.g., 2=PM1.0, 3=PM2.5, 5=PM10)."),
    order: Order = Query(Order.MIN, description="Order by minimum ('min') or maximum ('max') value."),
    output_format: OutputFormat = Query(OutputFormat.CSV, description="Output format: 'csv' or 'json'. Default is 'csv'."),
    db: Session = Depends(get_db)
):
    """
    Get top N stations by dimension value.
    
    Returns the stations with the highest or lowest values for a specific dimension
    (e.g., PM2.5, temperature). Only includes active stations (where last_active
    matches time_measured) and applies dimension-specific filter thresholds.
    
    **Parameters:**
    - **n**: Number of stations to return (required, minimum 1)
    - **dimension**: Dimension ID to compare (required)
      - Common dimensions: 2=PM1.0, 3=PM2.5, 5=PM10, 7=Temperature
    - **order**: 'min' to get lowest values, 'max' to get highest values (default: 'min')
    - **output_format**: 'csv' or 'json' (default: 'csv')
    
    **Response Formats:**
    
    **CSV** (default):
    - Columns: device, time_measured, dimension, value
    
    **JSON**:
    - Array of objects with device, time_measured, dimension, value, and optional location
    
    **Example CSV Response:**
    ```
    device,time_measured,dimension,value
    station_123,2024-01-01T12:00,3,15.2
    station_456,2024-01-01T12:00,3,18.5
    ```
    """

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
        return Response(content=standard_output_to_json(q.all(), db), media_type="application/json")


@router.get("/historical", response_class=Response, tags=["station"])
async def get_historical_station_data(
    station_ids: str = Query("", description="Comma-separated list of station device IDs. Empty string returns all stations."),
    start: str = Query(None, description="Start time in ISO format: YYYY-MM-DDThh:mm+xx:xx. If not provided, returns all available data."),
    end: str = Query(None, description="End time in ISO format: YYYY-MM-DDThh:mm+xx:xx, or 'current' for latest measurements. If not provided, returns all available data."),
    precision: Precision = Query(Precision.MAX, description="Time precision for aggregation: 'all' (max), 'hour', 'day', 'week', 'month', 'year'. Default is 'all'."),
    city_slugs: str = Query(None, description="Comma-separated list of city slugs to filter by. If not provided, all cities are included."),
    output_format: OutputFormat = Query(OutputFormat.CSV, description="Output format: 'csv' or 'json'. Default is 'csv'."),
    include_location: bool = Query(False, description="If True, includes location coordinates in JSON response (only applies to JSON format)."),
    db: Session = Depends(get_db)
):
    """
    Get historical measurement data with time aggregation.
    
    Returns aggregated measurement data over a time range with optional filtering
    by stations, cities, and time precision. When end='current', returns only the
    most recent measurements with outlier filtering applied.
    
    **Parameters:**
    - **station_ids**: Comma-separated station device IDs (empty = all stations)
    - **start**: Start time in ISO format (optional)
    - **end**: End time in ISO format, or 'current' for latest measurements (optional)
    - **precision**: Time aggregation precision:
      - 'all': No aggregation (maximum precision)
      - 'hour': Aggregate by hour
      - 'day': Aggregate by day
      - 'week': Aggregate by week
      - 'month': Aggregate by month
      - 'year': Aggregate by year
    - **city_slugs**: Comma-separated city slugs to filter by (optional)
    - **output_format**: 'csv' or 'json' (default: 'csv')
    - **include_location**: Include location in JSON response (default: False)
    
    **Special Behavior:**
    - When end='current': Returns only measurements from the last 20 minutes,
      applies outlier filtering using percentile-based method (0.5% on each side)
    
    **Response Formats:**
    
    **CSV** (default):
    - Columns: device, time_measured, dimension, value
    - Time format depends on precision setting
    
    **JSON**:
    - Array of objects grouped by device and time
    - Each object contains device, time_measured, values array
    - If include_location=true: adds location object with lat, lon, height
    
    **Example JSON Response:**
    ```json
    [
      {
        "device": "station_123",
        "time_measured": "2024-01-01T12:00",
        "values": [
          {"dimension": 2, "value": 10.5},
          {"dimension": 3, "value": 15.2}
        ]
      }
    ]
    ```
    
    **Errors:**
    - 400: Invalid date format
    """
    # Konvertiere die Liste von station_devices in eine Liste
    devices = station_ids.split(",") if station_ids else []
    cities = city_slugs.split(",") if city_slugs else [] 

    # Konvertiere start und end in datetime-Objekte
    try:
        start_date = datetime.fromisoformat(start) if start else None
        end_date = datetime.fromisoformat(end) if end else None
    except ValueError:
        if end != 'current':
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
    data_list = []
    if end == "current":
        start = datetime.now(tz=timezone.utc) - timedelta(minutes=CURRENT_TIME_RANGE_MINUTES)

        #q = q.filter(truncated_time >= Station.last_active)
        #data = q.all()

        data = db.execute(text("""select s.device, m.time_measured, v.dimension, avg(v.value) from stations as s 
inner join measurements m on m.station_id = s.id
inner join values v on v.measurement_id = m.id
where s.last_active = m.time_measured
group by s.id, s.device, m.time_measured, v.dimension;""")).all()

        # filter outlier
        dim_group = defaultdict(list)
        low = {}
        high = {}

        for _, _, dim, val in data:
            dim_group[dim].append(val)

        for dim, val_list in dim_group.items():
            a = np.array(val_list)
            low[dim] = np.percentile(a, 100 * (0.01 / 2))
            high[dim] = np.percentile(a, 100 * (1 - (0.01 / 2))) 

        # set all the values to none if the time exceedes the time range
        data_list = [
            (
                device,
                time,
                dim,
                val if time.replace(tzinfo=timezone.utc) >= start and low[dim] < val < high[dim]
                else None
            ) for (device, time, dim, val) in data
        ]
    else:
        if start_date is not None:
            q = q.filter(truncated_time >= start_date)
        if end_date is not None:
            q = q.filter(truncated_time <= end_date)
        data_list = q.all()

    if output_format == 'csv':
        return Response(content=standard_output_to_csv(data_list), media_type="text/csv")
    elif output_format == 'json':
        return Response(content=standard_output_to_json(data_list, db, include_location=include_location), media_type="application/json")


@router.get("/all", response_class=Response, tags=["station"])
async def get_all_stations(
    output_format: str = Query(default="csv", enum=["json", "csv"], description="Output format: 'csv' or 'json'. Default is 'csv'."),
    db: Session = Depends(get_db)
):
    """
    Get all registered stations with metadata.
    
    Returns a list of all stations in the database with their device IDs, last active
    timestamps, location coordinates, and measurement counts.
    
    **Parameters:**
    - **output_format**: 'csv' or 'json' (default: 'csv')
    
    **Response Formats:**
    
    **CSV** (default):
    - Columns: id, last_active, location_lat, location_lon, measurements_count
    - Includes Content-Disposition header for file download
    
    **JSON**:
    - Array of station objects with:
      - **id**: Station device ID
      - **last_active**: ISO format timestamp
      - **location**: Object with lat, lon (may be None)
      - **measurements_count**: Number of measurements for this station
    
    **Example JSON Response:**
    ```json
    [
      {
        "id": "station_123",
        "last_active": "2024-01-01T12:00:00",
        "location": {
          "lat": 48.2082,
          "lon": 16.3738
        },
        "measurements_count": 1500
      }
    ]
    ```
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
        # Convert datetime objects to ISO format strings for JSON serialization
        json_result = []
        for station_data in result:
            json_station = {
                "id": station_data["id"],
                "last_active": station_data["last_active"].isoformat() if station_data["last_active"] else None,
                "location": station_data["location"],
                "measurements_count": station_data["measurements_count"]
            }
            json_result.append(json_station)
        return Response(content=json.dumps(json_result), media_type="application/json")
    
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