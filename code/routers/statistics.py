from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, and_, text
from database import get_db
from datetime import datetime, timezone, timedelta
import math
from models import (
    Country, City, Location, Station, Measurement, 
    CalibrationMeasurement, Values, StationStatus
)
from enums import Source, SensorModel, Dimension

router = APIRouter()


@router.get("/", tags=["statistics"])
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get comprehensive database statistics and analytics.
    
    Returns detailed statistics about the database including entity counts, active
    stations, data coverage, distributions by various dimensions, and aggregated
    measurement statistics.
    
    **Response:**
    JSON object containing:
    
    - **timestamp**: Current UTC timestamp (ISO format)
    
    - **totals**: Counts of all entities:
      - **countries**: Total number of countries
      - **cities**: Total number of cities
      - **locations**: Total number of locations
      - **stations**: Total number of stations
      - **measurements**: Total number of measurements
      - **calibration_measurements**: Total calibration measurements
      - **values**: Total measurement values
      - **station_statuses**: Total status messages
    
    - **active_stations**: Counts of active stations by timeframe:
      - **last_hour**: Stations active in last hour
      - **last_24_hours**: Stations active in last 24 hours
      - **last_7_days**: Stations active in last 7 days
      - **last_30_days**: Stations active in last 30 days
    
    - **data_coverage**: Data availability information:
      - **earliest_measurement**: ISO timestamp of oldest measurement
      - **latest_measurement**: ISO timestamp of newest measurement
      - **measurements_last_24h**: Measurement count in last 24 hours
      - **measurements_last_7d**: Measurement count in last 7 days
      - **measurements_last_30d**: Measurement count in last 30 days
    
    - **distribution**: Various distribution statistics:
      - **stations_by_source**: Count of stations by data source
        (Luftdaten.at, TTN LoRaWAN, sensor.community)
      - **stations_by_country**: Count of stations per country
      - **top_cities**: Top 10 cities by station count
      - **sensor_models**: Distribution of sensor models used
      - **calibration_sensors**: Distribution of calibration sensor models
      - **status_by_level**: Count of status messages by level
    
    - **dimensions**: Array of dimension statistics (sorted by value count):
      - **dimension_id**: Dimension identifier
      - **dimension_name**: Human-readable dimension name
      - **unit**: Measurement unit (e.g., 'µg/m³', '°C')
      - **value_count**: Total number of values for this dimension
      - **average_value**: Average value (NaN values excluded)
      - **min_value**: Minimum value
      - **max_value**: Maximum value
    
    **Example Response:**
    ```json
    {
      "timestamp": "2024-01-01T12:00:00Z",
      "totals": {
        "countries": 5,
        "cities": 12,
        "locations": 45,
        "stations": 50,
        "measurements": 15000,
        "calibration_measurements": 500,
        "values": 45000,
        "station_statuses": 200
      },
      "active_stations": {
        "last_hour": 35,
        "last_24_hours": 42,
        "last_7_days": 48,
        "last_30_days": 50
      },
      "data_coverage": {
        "earliest_measurement": "2023-01-01T00:00:00Z",
        "latest_measurement": "2024-01-01T12:00:00Z",
        "measurements_last_24h": 1200,
        "measurements_last_7d": 8400,
        "measurements_last_30d": 36000
      },
      "distribution": {
        "stations_by_source": {
          "Luftdaten.at": 30,
          "sensor.community": 15,
          "Luftdaten.at TTN LoRaWAN": 5
        },
        "stations_by_country": {
          "Austria": 25,
          "Germany": 20,
          "Switzerland": 5
        },
        "top_cities": [
          {
            "city": "Vienna",
            "country": "Austria",
            "station_count": 10
          }
        ],
        "sensor_models": {
          "SDS011": 30,
          "BME280": 15,
          "SPS30": 5
        },
        "calibration_sensors": {
          "SDS011": 20
        },
        "status_by_level": {
          "level_1": 150,
          "level_2": 40,
          "level_3": 10
        }
      },
      "dimensions": [
        {
          "dimension_id": 3,
          "dimension_name": "PM2.5",
          "unit": "µg/m³",
          "value_count": 15000,
          "average_value": 15.5,
          "min_value": 2.0,
          "max_value": 85.0
        }
      ]
    }
    ```
    
    **Notes:**
    - NaN and infinity values are excluded from dimension statistics
    - Dimension statistics are sorted by value_count (descending)
    - Empty distributions (e.g., no stations for a source) are omitted
    """
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(days=1)
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    
    # Total counts
    total_countries = db.query(func.count(Country.id)).scalar() or 0
    total_cities = db.query(func.count(City.id)).scalar() or 0
    total_locations = db.query(func.count(Location.id)).scalar() or 0
    total_stations = db.query(func.count(Station.id)).scalar() or 0
    total_measurements = db.query(func.count(Measurement.id)).scalar() or 0
    total_calibration_measurements = db.query(func.count(CalibrationMeasurement.id)).scalar() or 0
    total_values = db.query(func.count(Values.id)).scalar() or 0
    total_station_statuses = db.query(func.count(StationStatus.id)).scalar() or 0
    
    # Active stations (last active within different timeframes)
    # Filter out None values for last_active
    active_stations_1h = db.query(func.count(distinct(Station.id))).filter(
        Station.last_active.isnot(None),
        Station.last_active >= one_hour_ago
    ).scalar() or 0
    
    active_stations_24h = db.query(func.count(distinct(Station.id))).filter(
        Station.last_active.isnot(None),
        Station.last_active >= one_day_ago
    ).scalar() or 0
    
    active_stations_7d = db.query(func.count(distinct(Station.id))).filter(
        Station.last_active.isnot(None),
        Station.last_active >= seven_days_ago
    ).scalar() or 0
    
    active_stations_30d = db.query(func.count(distinct(Station.id))).filter(
        Station.last_active.isnot(None),
        Station.last_active >= thirty_days_ago
    ).scalar() or 0
    
    # Data coverage (earliest and latest measurements)
    earliest_measurement = db.query(func.min(Measurement.time_measured)).scalar()
    latest_measurement = db.query(func.max(Measurement.time_measured)).scalar()
    
    # Measurements in different timeframes
    measurements_24h = db.query(func.count(Measurement.id)).filter(
        Measurement.time_measured >= one_day_ago
    ).scalar() or 0
    
    measurements_7d = db.query(func.count(Measurement.id)).filter(
        Measurement.time_measured >= seven_days_ago
    ).scalar() or 0
    
    measurements_30d = db.query(func.count(Measurement.id)).filter(
        Measurement.time_measured >= thirty_days_ago
    ).scalar() or 0
    
    # Stations by source
    stations_by_source = {}
    for source_id in [Source.LD, Source.LDTTN, Source.SC]:
        count = db.query(func.count(Station.id)).filter(
            Station.source == source_id
        ).scalar() or 0
        if count > 0:
            stations_by_source[Source.get_name(source_id)] = count
    
    # Stations by country
    # Use explicit joins with proper foreign key relationships
    try:
        stations_by_country = db.query(
            Country.name,
            func.count(distinct(Station.id)).label('station_count')
        ).join(City, Country.id == City.country_id)\
         .join(Location, City.id == Location.city_id)\
         .join(Station, Location.id == Station.location_id)\
         .group_by(Country.name)\
         .all()
        
        stations_by_country_dict = {
            country: count for country, count in stations_by_country
        }
    except Exception:
        # If join fails (e.g., no data or missing relationships), return empty dict
        stations_by_country_dict = {}
    
    # Top cities by station count
    try:
        top_cities = db.query(
            City.name,
            Country.name.label('country'),
            func.count(distinct(Station.id)).label('station_count')
        ).join(Country, City.country_id == Country.id)\
         .join(Location, City.id == Location.city_id)\
         .join(Station, Location.id == Station.location_id)\
         .group_by(City.name, Country.name)\
         .order_by(func.count(distinct(Station.id)).desc())\
         .limit(10)\
         .all()
        
        top_cities_list = [
            {
                "city": city,
                "country": country,
                "station_count": count
            }
            for city, country, count in top_cities
        ]
    except Exception:
        # If join fails (e.g., no data or missing relationships), return empty list
        top_cities_list = []
    
    top_cities_list = [
        {
            "city": city,
            "country": country,
            "station_count": count
        }
        for city, country, count in top_cities
    ]
    
    # Sensor models distribution
    try:
        sensor_models_dist = db.query(
            Measurement.sensor_model,
            func.count(distinct(Measurement.id)).label('count')
        ).group_by(Measurement.sensor_model).all()
        
        sensor_models_dict = {}
        for sensor_id, count in sensor_models_dist:
            sensor_name = SensorModel.get_sensor_name(sensor_id)
            sensor_models_dict[sensor_name] = count
    except Exception:
        sensor_models_dict = {}
    
    # Dimensions distribution
    # Filter out NaN values: in PostgreSQL, NaN != NaN, so we filter where value = value
    # Also filter out NULL and string 'nan'
    dimensions_dist = db.query(
        Values.dimension,
        func.count(Values.id).label('count'),
        func.avg(Values.value).label('avg_value'),
        func.min(Values.value).label('min_value'),
        func.max(Values.value).label('max_value')
    ).filter(
        Values.value.isnot(None),
        Values.value != 'nan'
    ).group_by(Values.dimension).all()
    
    dimensions_list = []
    for dim_id, count, avg_val, min_val, max_val in dimensions_dist:
        # Helper function to safely convert to float, handling NaN and infinity
        def safe_float(value):
            if value is None:
                return None
            try:
                fval = float(value)
                # Check for NaN or infinity (these are not JSON compliant)
                if math.isnan(fval) or math.isinf(fval):
                    return None
                return fval
            except (ValueError, TypeError):
                return None
        
        dimensions_list.append({
            "dimension_id": dim_id,
            "dimension_name": Dimension.get_name(dim_id),
            "unit": Dimension.get_unit(dim_id),
            "value_count": count,
            "average_value": safe_float(avg_val),
            "min_value": safe_float(min_val),
            "max_value": safe_float(max_val)
        })
    
    # Sort dimensions by count
    dimensions_list.sort(key=lambda x: x['value_count'], reverse=True)
    
    # Calibration measurements distribution
    try:
        calibration_by_sensor = db.query(
            CalibrationMeasurement.sensor_model,
            func.count(distinct(CalibrationMeasurement.id)).label('count')
        ).group_by(CalibrationMeasurement.sensor_model).all()
        
        calibration_sensors_dict = {}
        for sensor_id, count in calibration_by_sensor:
            sensor_name = SensorModel.get_sensor_name(sensor_id)
            calibration_sensors_dict[sensor_name] = count
    except Exception:
        calibration_sensors_dict = {}
    
    # Station status distribution
    try:
        status_by_level = db.query(
            StationStatus.level,
            func.count(StationStatus.id).label('count')
        ).group_by(StationStatus.level).all()
        
        status_by_level_dict = {
            f"level_{level}": count for level, count in status_by_level
        }
    except Exception:
        status_by_level_dict = {}
    
    # Build response
    statistics = {
        "timestamp": now.isoformat(),
        "totals": {
            "countries": total_countries,
            "cities": total_cities,
            "locations": total_locations,
            "stations": total_stations,
            "measurements": total_measurements,
            "calibration_measurements": total_calibration_measurements,
            "values": total_values,
            "station_statuses": total_station_statuses
        },
        "active_stations": {
            "last_hour": active_stations_1h,
            "last_24_hours": active_stations_24h,
            "last_7_days": active_stations_7d,
            "last_30_days": active_stations_30d
        },
        "data_coverage": {
            "earliest_measurement": earliest_measurement.isoformat() if earliest_measurement else None,
            "latest_measurement": latest_measurement.isoformat() if latest_measurement else None,
            "measurements_last_24h": measurements_24h,
            "measurements_last_7d": measurements_7d,
            "measurements_last_30d": measurements_30d
        },
        "distribution": {
            "stations_by_source": stations_by_source,
            "stations_by_country": stations_by_country_dict,
            "top_cities": top_cities_list,
            "sensor_models": sensor_models_dict,
            "calibration_sensors": calibration_sensors_dict,
            "status_by_level": status_by_level_dict
        },
        "dimensions": dimensions_list
    }
    
    return statistics

