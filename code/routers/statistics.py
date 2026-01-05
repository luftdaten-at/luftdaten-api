from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, and_
from database import get_db
from datetime import datetime, timezone, timedelta
from models import (
    Country, City, Location, Station, Measurement, 
    CalibrationMeasurement, Values, StationStatus
)
from enums import Source, SensorModel, Dimension

router = APIRouter()


@router.get("/", tags=["statistics"])
async def get_statistics(db: Session = Depends(get_db)):
    """
    Get comprehensive statistics about the database.
    Returns counts, distributions, and data coverage information.
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
    active_stations_1h = db.query(func.count(distinct(Station.id))).filter(
        Station.last_active >= one_hour_ago
    ).scalar() or 0
    
    active_stations_24h = db.query(func.count(distinct(Station.id))).filter(
        Station.last_active >= one_day_ago
    ).scalar() or 0
    
    active_stations_7d = db.query(func.count(distinct(Station.id))).filter(
        Station.last_active >= seven_days_ago
    ).scalar() or 0
    
    active_stations_30d = db.query(func.count(distinct(Station.id))).filter(
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
    stations_by_country = db.query(
        Country.name,
        func.count(distinct(Station.id)).label('station_count')
    ).join(City).join(Location).join(Station).group_by(Country.name).all()
    
    stations_by_country_dict = {
        country: count for country, count in stations_by_country
    }
    
    # Top cities by station count
    top_cities = db.query(
        City.name,
        Country.name.label('country'),
        func.count(distinct(Station.id)).label('station_count')
    ).join(Country).join(Location).join(Station).group_by(
        City.name, Country.name
    ).order_by(func.count(distinct(Station.id)).desc()).limit(10).all()
    
    top_cities_list = [
        {
            "city": city,
            "country": country,
            "station_count": count
        }
        for city, country, count in top_cities
    ]
    
    # Sensor models distribution
    sensor_models_dist = db.query(
        Measurement.sensor_model,
        func.count(distinct(Measurement.id)).label('count')
    ).group_by(Measurement.sensor_model).all()
    
    sensor_models_dict = {}
    for sensor_id, count in sensor_models_dist:
        sensor_name = SensorModel.get_sensor_name(sensor_id)
        sensor_models_dict[sensor_name] = count
    
    # Dimensions distribution
    dimensions_dist = db.query(
        Values.dimension,
        func.count(Values.id).label('count'),
        func.avg(Values.value).label('avg_value'),
        func.min(Values.value).label('min_value'),
        func.max(Values.value).label('max_value')
    ).group_by(Values.dimension).all()
    
    dimensions_list = []
    for dim_id, count, avg_val, min_val, max_val in dimensions_dist:
        dimensions_list.append({
            "dimension_id": dim_id,
            "dimension_name": Dimension.get_name(dim_id),
            "unit": Dimension.get_unit(dim_id),
            "value_count": count,
            "average_value": float(avg_val) if avg_val is not None else None,
            "min_value": float(min_val) if min_val is not None else None,
            "max_value": float(max_val) if max_val is not None else None
        })
    
    # Sort dimensions by count
    dimensions_list.sort(key=lambda x: x['value_count'], reverse=True)
    
    # Calibration measurements distribution
    calibration_by_sensor = db.query(
        CalibrationMeasurement.sensor_model,
        func.count(distinct(CalibrationMeasurement.id)).label('count')
    ).group_by(CalibrationMeasurement.sensor_model).all()
    
    calibration_sensors_dict = {}
    for sensor_id, count in calibration_by_sensor:
        sensor_name = SensorModel.get_sensor_name(sensor_id)
        calibration_sensors_dict[sensor_name] = count
    
    # Station status distribution
    status_by_level = db.query(
        StationStatus.level,
        func.count(StationStatus.id).label('count')
    ).group_by(StationStatus.level).all()
    
    status_by_level_dict = {
        f"level_{level}": count for level, count in status_by_level
    }
    
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

