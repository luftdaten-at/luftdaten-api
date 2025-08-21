import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base
from models import Station, Location, Measurement, Values, City, Country, CalibrationMeasurement
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone, timedelta
import json
import csv
import io

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
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def sample_data():
    """Create sample data for testing"""
    db = next(override_get_db())
    
    # Create country
    country = Country(name="Austria", slug="austria")
    db.add(country)
    db.commit()
    db.refresh(country)
    
    # Create city
    city = City(
        name="Vienna", 
        slug="vienna", 
        country_id=country.id,
        lat=48.2082,
        lon=16.3738,
        tz="Europe/Vienna"
    )
    db.add(city)
    db.commit()
    db.refresh(city)
    
    # Create location
    location = Location(
        lat=48.2082,
        lon=16.3738,
        height=100.0,
        city_id=city.id
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    
    # Create station
    station = Station(
        device="test_station_1",
        location_id=location.id,
        last_active=datetime.now(timezone.utc),
        firmware="1.0"
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    
    # Create measurement
    measurement = Measurement(
        station_id=station.id,
        time_measured=station.last_active,
        sensor_model="SDS011"
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    
    # Create values
    values = [
        Values(measurement_id=measurement.id, dimension="P1", value=10.5),
        Values(measurement_id=measurement.id, dimension="P2", value=5.2),
        Values(measurement_id=measurement.id, dimension="temperature", value=22.0)
    ]
    for value in values:
        db.add(value)
    db.commit()
    
    # Create calibration measurement
    calibration_measurement = CalibrationMeasurement(
        station_id=station.id,
        time_measured=station.last_active,
        sensor_model="SDS011"
    )
    db.add(calibration_measurement)
    db.commit()
    db.refresh(calibration_measurement)
    
    # Create calibration values
    calibration_values = [
        Values(calibration_measurement_id=calibration_measurement.id, dimension="P1", value=9.8),
        Values(calibration_measurement_id=calibration_measurement.id, dimension="P2", value=4.9)
    ]
    for value in calibration_values:
        db.add(value)
    db.commit()
    
    return {
        "country": country,
        "city": city,
        "location": location,
        "station": station,
        "measurement": measurement,
        "values": values,
        "calibration_measurement": calibration_measurement,
        "calibration_values": calibration_values
    }

class TestStationRouter:
    
    def test_get_current_station_data_no_data(self):
        """Test getting current station data when no data exists"""
        response = client.get("/v1/station/current")
        assert response.status_code == 404
        assert response.json() == {"detail": "No stations found"}
    
    def test_get_current_station_data_with_data(self, sample_data):
        """Test getting current station data with sample data"""
        response = client.get("/v1/station/current")
        assert response.status_code == 200
        
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == 1
        
        feature = data["features"][0]
        assert feature["type"] == "Feature"
        assert feature["geometry"]["type"] == "Point"
        assert feature["geometry"]["coordinates"] == [16.3738, 48.2082]
        assert feature["properties"]["device"] == "test_station_1"
        assert feature["properties"]["height"] == 100.0
        assert "sensors" in feature["properties"]
        assert len(feature["properties"]["sensors"]) > 0
    
    def test_get_current_station_data_csv_format(self, sample_data):
        """Test getting current station data in CSV format"""
        response = client.get("/v1/station/current?output_format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        # Parse CSV content
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) > 1  # Header + at least one data row
        
        # Check header
        header = lines[0].split(',')
        expected_header = ["device", "lat", "lon", "last_active", "height", "sensor_model", "dimension", "value"]
        for field in expected_header:
            assert field in header
    
    def test_get_current_station_data_with_calibration(self, sample_data):
        """Test getting current station data with calibration data"""
        response = client.get("/v1/station/current?calibration_data=true")
        assert response.status_code == 200
        
        data = response.json()
        feature = data["features"][0]
        assert "calibration_sensors" in feature["properties"]
        assert len(feature["properties"]["calibration_sensors"]) > 0
    
    def test_get_current_station_data_specific_stations(self, sample_data):
        """Test getting current station data for specific station IDs"""
        response = client.get("/v1/station/current?station_ids=test_station_1")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["device"] == "test_station_1"
    
    def test_get_current_station_data_inactive_stations(self, sample_data):
        """Test getting current station data with inactive stations (outside last_active window)"""
        db = next(override_get_db())
        
        # Make station inactive by setting last_active to old time
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        sample_data["station"].last_active = old_time
        sample_data["measurement"].time_measured = old_time
        db.commit()
        
        response = client.get("/v1/station/current")
        assert response.status_code == 404
        assert response.json() == {"detail": "No stations found"}
    
    def test_get_station_info_not_found(self):
        """Test getting station info for non-existent station"""
        response = client.get("/v1/station/info?station_id=nonexistent")
        assert response.status_code == 404
        assert response.json() == {"detail": "Station not found"}
    
    def test_get_station_info_found(self, sample_data):
        """Test getting station info for existing station"""
        response = client.get("/v1/station/info?station_id=test_station_1")
        assert response.status_code == 200
        
        data = response.json()
        assert "station" in data
        assert "sensors" in data
        
        station_info = data["station"]
        assert station_info["device"] == "test_station_1"
        assert station_info["firmware"] == "1.0"
        assert "location" in station_info
        assert station_info["location"]["lat"] == 48.2082
        assert station_info["location"]["lon"] == 16.3738
        assert station_info["location"]["height"] == 100.0
    
    def test_get_calibration_data_no_stations(self):
        """Test getting calibration data when no stations exist"""
        response = client.get("/v1/station/calibration")
        assert response.status_code == 200
        assert response.text.strip() == ""  # Empty CSV
    
    def test_get_calibration_data_with_data(self, sample_data):
        """Test getting calibration data with sample data"""
        response = client.get("/v1/station/calibration")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) > 0
        
        # Check that calibration data is present
        assert "test_station_1" in csv_content
        assert "SDS011" in csv_content
    
    def test_get_calibration_data_specific_stations(self, sample_data):
        """Test getting calibration data for specific stations"""
        response = client.get("/v1/station/calibration?station_ids=test_station_1")
        assert response.status_code == 200
        
        csv_content = response.text
        assert "test_station_1" in csv_content
    
    def test_get_calibration_data_no_data_flag(self, sample_data):
        """Test getting calibration data with data=false flag"""
        response = client.get("/v1/station/calibration?data=false")
        assert response.status_code == 200
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) == 1  # Only station IDs
        assert "test_station_1" in csv_content
    
    def test_post_station_data_success(self):
        """Test posting station data successfully"""
        station_data = {
            "device": "test_device_123",
            "location": {
                "lat": 48.2082,
                "lon": 16.3738,
                "height": 100.5
            },
            "time": "2024-04-29T08:25:20.766Z",
            "firmware": "1.0",
            "apikey": "testapikey123"
        }

        sensors = {
            "1": {"type": 1, "data": {"2": 5.0, "3": 6.0}}
        }

        response = client.post("/v1/station/data/", json={"station": station_data, "sensors": sensors})
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        # Verify station was created in database
        db = next(override_get_db())
        station = db.query(Station).filter_by(device="test_device_123").first()
        assert station is not None
        assert station.device == "test_device_123"
    
    def test_post_station_status_success(self):
        """Test posting station status successfully"""
        status_data = {
            "device": "test_device_123",
            "status": "online",
            "time": "2024-04-29T08:25:20.766Z"
        }

        response = client.post("/v1/station/status", json=status_data)
        assert response.status_code == 200
        assert response.json() == {"status": "success"}
    
    def test_get_all_stations_no_data(self):
        """Test getting all stations when no data exists"""
        response = client.get("/v1/station/all")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) == 1  # Only header
    
    def test_get_all_stations_with_data(self, sample_data):
        """Test getting all stations with sample data"""
        response = client.get("/v1/station/all")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) == 2  # Header + data row
        
        # Check header
        header = lines[0].split(',')
        expected_header = ["id", "last_active", "location_lat", "location_lon", "measurements_count"]
        for field in expected_header:
            assert field in header
        
        # Check data row contains station info
        assert "test_station_1" in csv_content
    
    def test_get_all_stations_json_format(self, sample_data):
        """Test getting all stations in JSON format"""
        response = client.get("/v1/station/all?output_format=json")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        
        station_data = data[0]
        assert station_data["id"] == "test_station_1"
        assert "last_active" in station_data
        assert "location" in station_data
        assert "measurements_count" in station_data
    
    def test_get_topn_stations(self, sample_data):
        """Test getting top N stations by dimension"""
        response = client.get("/v1/station/topn?n=5&dimension=1&order=min&output_format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) > 0
    
    def test_get_historical_station_data(self, sample_data):
        """Test getting historical station data"""
        response = client.get("/v1/station/historical?station_ids=test_station_1&output_format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) > 0
    
    def test_get_historical_station_data_current(self, sample_data):
        """Test getting historical station data with end=current"""
        response = client.get("/v1/station/historical?end=current&output_format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
    
    def test_get_historical_station_data_invalid_date(self, sample_data):
        """Test getting historical station data with invalid date format"""
        response = client.get("/v1/station/historical?start=invalid-date&output_format=csv")
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]
    
    def test_get_current_station_data_all_old_endpoint(self, sample_data):
        """Test the old /current/all endpoint for compatibility"""
        response = client.get("/v1/station/current/all")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        
        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) > 0
    
    def test_get_station_history_old_endpoint(self, sample_data):
        """Test the old /history endpoint for compatibility"""
        response = client.get("/v1/station/history")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"