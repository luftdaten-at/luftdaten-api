import sys
import os

# Add the parent directory to the path so we can import modules
# This must be done BEFORE any imports from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base
from models import (
    City, Country, Station, Location, Measurement, Values,
    CalibrationMeasurement, StationStatus
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone, timedelta
from enums import SensorModel, Dimension, Source

# Configure test database
SQLALCHEMY_DATABASE_URL = "postgresql://test_user:test_password@db_test/test_database"

engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    # Drop all tables, ignoring errors if tables don't exist
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        # Ignore errors during teardown (e.g., tables already dropped)
        pass

@pytest.fixture
def sample_statistics_data():
    """Create comprehensive sample data for statistics testing"""
    db = next(override_get_db())
    
    # Create countries
    country1 = Country(name="Austria", code="AT")
    country2 = Country(name="Germany", code="DE")
    db.add(country1)
    db.add(country2)
    db.commit()
    db.refresh(country1)
    db.refresh(country2)
    
    # Create cities
    city1 = City(
        name="Vienna",
        country_id=country1.id,
        tz="Europe/Vienna",
        lat=48.2082,
        lon=16.3738
    )
    city2 = City(
        name="Berlin",
        country_id=country2.id,
        tz="Europe/Berlin",
        lat=52.5200,
        lon=13.4050
    )
    db.add(city1)
    db.add(city2)
    db.commit()
    db.refresh(city1)
    db.refresh(city2)
    
    # Create locations
    location1 = Location(
        lat=48.2082,
        lon=16.3738,
        height=100.0,
        city_id=city1.id,
        country_id=country1.id
    )
    location2 = Location(
        lat=52.5200,
        lon=13.4050,
        height=50.0,
        city_id=city2.id,
        country_id=country2.id
    )
    db.add(location1)
    db.add(location2)
    db.commit()
    db.refresh(location1)
    db.refresh(location2)
    
    # Create stations with different sources and last_active times
    now = datetime.now(timezone.utc)
    station1 = Station(
        device="station_1",
        location_id=location1.id,
        last_active=now - timedelta(minutes=30),  # Active in last hour
        firmware="1.0",
        source=Source.LD
    )
    station2 = Station(
        device="station_2",
        location_id=location1.id,
        last_active=now - timedelta(hours=12),  # Active in last 24h
        firmware="2.0",
        source=Source.SC
    )
    station3 = Station(
        device="station_3",
        location_id=location2.id,
        last_active=now - timedelta(days=3),  # Active in last 7d
        firmware="1.5",
        source=Source.LDTTN
    )
    station4 = Station(
        device="station_4",
        location_id=location2.id,
        last_active=now - timedelta(days=40),  # Not active in last 30d
        firmware="1.0",
        source=Source.LD
    )
    db.add(station1)
    db.add(station2)
    db.add(station3)
    db.add(station4)
    db.commit()
    db.refresh(station1)
    db.refresh(station2)
    db.refresh(station3)
    db.refresh(station4)
    
    # Create measurements with different timestamps
    measurement1 = Measurement(
        station_id=station1.id,
        location_id=location1.id,
        time_measured=now - timedelta(hours=2),
        time_received=now - timedelta(hours=2),
        sensor_model=SensorModel.SDS011
    )
    measurement2 = Measurement(
        station_id=station2.id,
        location_id=location1.id,
        time_measured=now - timedelta(hours=10),
        time_received=now - timedelta(hours=10),
        sensor_model=SensorModel.BME280
    )
    measurement3 = Measurement(
        station_id=station3.id,
        location_id=location2.id,
        time_measured=now - timedelta(days=2),
        time_received=now - timedelta(days=2),
        sensor_model=SensorModel.SDS011
    )
    measurement4 = Measurement(
        station_id=station1.id,
        location_id=location1.id,
        time_measured=now - timedelta(days=5),
        time_received=now - timedelta(days=5),
        sensor_model=SensorModel.SDS011
    )
    # Old measurement (outside 30 days)
    measurement5 = Measurement(
        station_id=station4.id,
        location_id=location2.id,
        time_measured=now - timedelta(days=40),
        time_received=now - timedelta(days=40),
        sensor_model=SensorModel.BME280
    )
    db.add(measurement1)
    db.add(measurement2)
    db.add(measurement3)
    db.add(measurement4)
    db.add(measurement5)
    db.commit()
    db.refresh(measurement1)
    db.refresh(measurement2)
    db.refresh(measurement3)
    db.refresh(measurement4)
    db.refresh(measurement5)
    
    # Create values for measurements
    values1 = [
        Values(measurement_id=measurement1.id, dimension=Dimension.PM2_5, value=15.5),
        Values(measurement_id=measurement1.id, dimension=Dimension.PM10_0, value=20.3),
        Values(measurement_id=measurement1.id, dimension=Dimension.TEMPERATURE, value=22.0),
    ]
    values2 = [
        Values(measurement_id=measurement2.id, dimension=Dimension.PM2_5, value=12.0),
        Values(measurement_id=measurement2.id, dimension=Dimension.HUMIDITY, value=65.0),
    ]
    values3 = [
        Values(measurement_id=measurement3.id, dimension=Dimension.PM2_5, value=18.0),
    ]
    values4 = [
        Values(measurement_id=measurement4.id, dimension=Dimension.PM2_5, value=10.0),
    ]
    values5 = [
        Values(measurement_id=measurement5.id, dimension=Dimension.TEMPERATURE, value=15.0),
    ]
    
    for value in values1 + values2 + values3 + values4 + values5:
        db.add(value)
    db.commit()
    
    # Create calibration measurement
    calibration_measurement = CalibrationMeasurement(
        station_id=station1.id,
        location_id=location1.id,
        time_measured=now - timedelta(hours=1),
        time_received=now - timedelta(hours=1),
        sensor_model=SensorModel.SDS011
    )
    db.add(calibration_measurement)
    db.commit()
    db.refresh(calibration_measurement)
    
    calibration_value = Values(
        calibration_measurement_id=calibration_measurement.id,
        dimension=Dimension.PM2_5,
        value=14.5
    )
    db.add(calibration_value)
    db.commit()
    
    # Create station statuses
    status1 = StationStatus(
        station_id=station1.id,
        timestamp=now - timedelta(hours=1),
        level=1,
        message="online"
    )
    status2 = StationStatus(
        station_id=station2.id,
        timestamp=now - timedelta(hours=2),
        level=2,
        message="warning"
    )
    status3 = StationStatus(
        station_id=station1.id,
        timestamp=now - timedelta(hours=3),
        level=1,
        message="online"
    )
    db.add(status1)
    db.add(status2)
    db.add(status3)
    db.commit()
    
    return {
        "countries": [country1, country2],
        "cities": [city1, city2],
        "locations": [location1, location2],
        "stations": [station1, station2, station3, station4],
        "measurements": [measurement1, measurement2, measurement3, measurement4, measurement5],
        "values": values1 + values2 + values3 + values4 + values5,
        "calibration_measurement": calibration_measurement,
        "statuses": [status1, status2, status3]
    }

class TestStatisticsRouter:
    
    def test_get_statistics_no_data(self):
        """Test statistics endpoint with no data"""
        response = client.get("/v1/statistics/")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check structure
        assert "timestamp" in data
        assert "totals" in data
        assert "active_stations" in data
        assert "data_coverage" in data
        assert "distribution" in data
        assert "dimensions" in data
        
        # Check totals are all zero
        totals = data["totals"]
        assert totals["countries"] == 0
        assert totals["cities"] == 0
        assert totals["locations"] == 0
        assert totals["stations"] == 0
        assert totals["measurements"] == 0
        assert totals["calibration_measurements"] == 0
        assert totals["values"] == 0
        assert totals["station_statuses"] == 0
        
        # Check active stations are all zero
        active = data["active_stations"]
        assert active["last_hour"] == 0
        assert active["last_24_hours"] == 0
        assert active["last_7_days"] == 0
        assert active["last_30_days"] == 0
        
        # Check data coverage
        coverage = data["data_coverage"]
        assert coverage["earliest_measurement"] is None
        assert coverage["latest_measurement"] is None
        
        # Check dimensions is empty list
        assert data["dimensions"] == []
    
    def test_get_statistics_with_data(self, sample_statistics_data):
        """Test statistics endpoint with sample data"""
        response = client.get("/v1/statistics/")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check totals
        totals = data["totals"]
        assert totals["countries"] == 2
        assert totals["cities"] == 2
        assert totals["locations"] == 2
        assert totals["stations"] == 4
        assert totals["measurements"] == 5
        assert totals["calibration_measurements"] == 1
        assert totals["values"] == 8  # 3 + 2 + 1 + 1 + 1
        assert totals["station_statuses"] == 3
        
        # Check active stations
        active = data["active_stations"]
        assert active["last_hour"] == 1  # station_1
        assert active["last_24_hours"] == 2  # station_1, station_2
        assert active["last_7_days"] == 3  # station_1, station_2, station_3
        assert active["last_30_days"] == 3  # station_1, station_2, station_3 (station_4 is 40 days old)
        
        # Check data coverage
        coverage = data["data_coverage"]
        assert coverage["earliest_measurement"] is not None
        assert coverage["latest_measurement"] is not None
        assert coverage["measurements_last_24h"] == 2  # measurement1, measurement2
        assert coverage["measurements_last_7d"] == 4  # measurement1-4
        assert coverage["measurements_last_30d"] == 4  # measurement1-4
        
        # Check distribution
        distribution = data["distribution"]
        
        # Stations by source
        assert "Luftdaten.at" in distribution["stations_by_source"]
        assert distribution["stations_by_source"]["Luftdaten.at"] == 2
        assert distribution["stations_by_source"]["sensor.community"] == 1
        assert distribution["stations_by_source"]["Luftdaten.at TTN LoRaWAN"] == 1
        
        # Stations by country
        assert "Austria" in distribution["stations_by_country"]
        assert distribution["stations_by_country"]["Austria"] == 2
        assert "Germany" in distribution["stations_by_country"]
        assert distribution["stations_by_country"]["Germany"] == 2
        
        # Top cities
        assert len(distribution["top_cities"]) > 0
        top_cities = distribution["top_cities"]
        # Should have Vienna and Berlin
        city_names = [city["city"] for city in top_cities]
        assert "Vienna" in city_names or "Berlin" in city_names
        
        # Sensor models
        assert "SDS011" in distribution["sensor_models"]
        assert distribution["sensor_models"]["SDS011"] == 3
        assert "BME280" in distribution["sensor_models"]
        assert distribution["sensor_models"]["BME280"] == 2
        
        # Calibration sensors
        assert "SDS011" in distribution["calibration_sensors"]
        assert distribution["calibration_sensors"]["SDS011"] == 1
        
        # Status by level
        assert "level_1" in distribution["status_by_level"]
        assert distribution["status_by_level"]["level_1"] == 2
        assert "level_2" in distribution["status_by_level"]
        assert distribution["status_by_level"]["level_2"] == 1
        
        # Check dimensions
        dimensions = data["dimensions"]
        assert len(dimensions) > 0
        
        # Find PM2_5 dimension
        pm25_dim = next((d for d in dimensions if d["dimension_id"] == Dimension.PM2_5), None)
        assert pm25_dim is not None
        assert pm25_dim["dimension_name"] == "PM2.5"
        assert pm25_dim["unit"] == "µg/m³"
        assert pm25_dim["value_count"] == 4  # 4 measurements with PM2_5
        assert pm25_dim["average_value"] is not None
        assert pm25_dim["min_value"] is not None
        assert pm25_dim["max_value"] is not None
        
        # Find TEMPERATURE dimension
        temp_dim = next((d for d in dimensions if d["dimension_id"] == Dimension.TEMPERATURE), None)
        assert temp_dim is not None
        assert temp_dim["dimension_name"] == "Temperature"
        assert temp_dim["unit"] == "°C"
        assert temp_dim["value_count"] == 2  # 2 measurements with TEMPERATURE
    
    def test_get_statistics_response_structure(self, sample_statistics_data):
        """Test that statistics response has correct structure"""
        response = client.get("/v1/statistics/")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check all required top-level keys
        required_keys = ["timestamp", "totals", "active_stations", "data_coverage", "distribution", "dimensions"]
        for key in required_keys:
            assert key in data
        
        # Check totals structure
        required_totals = [
            "countries", "cities", "locations", "stations",
            "measurements", "calibration_measurements", "values", "station_statuses"
        ]
        for key in required_totals:
            assert key in data["totals"]
            assert isinstance(data["totals"][key], int)
        
        # Check active_stations structure
        required_active = ["last_hour", "last_24_hours", "last_7_days", "last_30_days"]
        for key in required_active:
            assert key in data["active_stations"]
            assert isinstance(data["active_stations"][key], int)
        
        # Check data_coverage structure
        required_coverage = [
            "earliest_measurement", "latest_measurement",
            "measurements_last_24h", "measurements_last_7d", "measurements_last_30d"
        ]
        for key in required_coverage:
            assert key in data["data_coverage"]
        
        # Check distribution structure
        required_distribution = [
            "stations_by_source", "stations_by_country", "top_cities",
            "sensor_models", "calibration_sensors", "status_by_level"
        ]
        for key in required_distribution:
            assert key in data["distribution"]
        
        # Check dimensions structure
        if len(data["dimensions"]) > 0:
            dimension_keys = ["dimension_id", "dimension_name", "unit", "value_count"]
            for dim in data["dimensions"]:
                for key in dimension_keys:
                    assert key in dim
                # Optional keys
                if dim["value_count"] > 0:
                    assert "average_value" in dim
                    assert "min_value" in dim
                    assert "max_value" in dim
    
    def test_get_statistics_timestamp_format(self, sample_statistics_data):
        """Test that timestamp is in ISO format"""
        response = client.get("/v1/statistics/")
        assert response.status_code == 200
        
        data = response.json()
        timestamp = data["timestamp"]
        
        # Should be valid ISO format
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Should be recent (within last minute)
        parsed_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        assert abs((now - parsed_time).total_seconds()) < 60

