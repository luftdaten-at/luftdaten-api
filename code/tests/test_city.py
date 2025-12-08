import sys
import os

# Add the parent directory to the path so we can import modules
# This must be done BEFORE any imports from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base
from models import City, Country, Station, Location, Measurement, Values
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone, timedelta
import json

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
def sample_data():
    """Create sample data for testing"""
    db = next(override_get_db())
    
    # Create country
    country = Country(name="Austria", code="AT")
    db.add(country)
    db.commit()
    db.refresh(country)
    
    # Create city
    city = City(
        name="Vienna", 
        country_id=country.id,
        tz="Europe/Vienna",
        lat=48.2082,
        lon=16.3738
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
    
    # Create station (need to set last_active for it to be considered active)
    # Use the same timestamp for both station.last_active and measurement.time_measured
    from enums import SensorModel
    measurement_time = datetime.now(timezone.utc)
    station = Station(
        device="test_station_1",
        location_id=location.id,
        last_active=measurement_time
    )
    db.add(station)
    db.commit()
    db.refresh(station)
    
    # Create measurement (using integer sensor model ID: SDS011=13)
    # Use the same time as station.last_active
    # Measurement needs location_id for the city query to work
    measurement = Measurement(
        station_id=station.id,
        location_id=location.id,
        time_measured=measurement_time,
        sensor_model=SensorModel.SDS011
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)
    
    # Create values (using integer dimension IDs: PM1_0=2, PM2_5=3, TEMPERATURE=7)
    from enums import Dimension
    values = [
        Values(measurement_id=measurement.id, dimension=Dimension.PM1_0, value=10.5),
        Values(measurement_id=measurement.id, dimension=Dimension.PM2_5, value=5.2),
        Values(measurement_id=measurement.id, dimension=Dimension.TEMPERATURE, value=22.0)
    ]
    for value in values:
        db.add(value)
    db.commit()
    
    return {
        "country": country,
        "city": city,
        "location": location,
        "station": station,
        "measurement": measurement,
        "values": values
    }

class TestCityRouter:
    
    def test_get_all_cities_no_data(self):
        """Test getting all cities when no data exists"""
        response = client.get("/v1/city/all")
        assert response.status_code == 404
        assert response.json() == {"detail": "No cities found"}
    
    def test_get_all_cities_with_data(self, sample_data):
        """Test getting all cities with sample data"""
        response = client.get("/v1/city/all")
        assert response.status_code == 200
        
        data = response.json()
        assert "cities" in data
        assert len(data["cities"]) == 1
        
        city_data = data["cities"][0]
        assert city_data["name"] == "Vienna"
        assert city_data["slug"] == "vienna"
        assert city_data["country"]["name"] == "Austria"
        assert city_data["country"]["slug"] == "austria"
    
    def test_get_all_cities_multiple_cities(self, sample_data):
        """Test getting all cities with multiple cities"""
        db = next(override_get_db())
        
        # Add another city
        country2 = Country(name="Germany", code="DE")
        db.add(country2)
        db.commit()
        db.refresh(country2)
        
        city2 = City(
            name="Berlin", 
            country_id=country2.id,
            tz="Europe/Berlin",
            lat=52.5200,
            lon=13.4050
        )
        db.add(city2)
        db.commit()
        
        response = client.get("/v1/city/all")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["cities"]) == 2
        
        city_names = [city["name"] for city in data["cities"]]
        assert "Vienna" in city_names
        assert "Berlin" in city_names
    
    def test_get_current_measurements_city_not_found(self):
        """Test getting current measurements for non-existent city"""
        response = client.get("/v1/city/current?city_slug=nonexistent")
        assert response.status_code == 404
        assert response.json() == {"detail": "City not found"}
    
    def test_get_current_measurements_city_found_no_stations(self, sample_data):
        """Test getting current measurements for city with no stations"""
        db = next(override_get_db())
        
        # Remove the station
        db.delete(sample_data["station"])
        db.commit()
        
        response = client.get("/v1/city/current?city_slug=vienna")
        assert response.status_code == 200
        
        # Should return GeoJSON with empty values array
        data = response.json()
        assert data["type"] == "Feature"
        assert data["geometry"]["type"] == "Point"
        assert data["geometry"]["coordinates"] == [16.3738, 48.2082]
        assert data["properties"]["name"] == "Vienna"
        assert data["properties"]["city_slug"] == "vienna"
        assert data["properties"]["country"] == "Austria"
        assert data["properties"]["station_count"] == 0
        assert len(data["properties"]["values"]) == 0
    
    def test_get_current_measurements_city_with_data(self, sample_data):
        """Test getting current measurements for city with data"""
        response = client.get("/v1/city/current?city_slug=vienna")
        assert response.status_code == 200
        
        data = response.json()
        assert data["type"] == "Feature"
        assert data["geometry"]["type"] == "Point"
        assert data["geometry"]["coordinates"] == [16.3738, 48.2082]
        assert data["properties"]["name"] == "Vienna"
        assert data["properties"]["city_slug"] == "vienna"
        assert data["properties"]["country"] == "Austria"
        assert data["properties"]["station_count"] == 1
        assert "time" in data["properties"]
        assert "timezone" in data["properties"]
        
        # Check that values are present
        values = data["properties"]["values"]
        assert len(values) > 0
        
        # Check that each value has required fields
        for value in values:
            assert "dimension" in value
            assert "value" in value
            assert "value_count" in value
            assert "station_count" in value
    
    def test_get_current_measurements_city_without_coordinates(self, sample_data):
        """Test getting current measurements for city without lat/lon coordinates"""
        db = next(override_get_db())
        
        # Remove coordinates from city
        sample_data["city"].lat = None
        sample_data["city"].lon = None
        db.commit()
        
        # Mock the geocoding to avoid external API calls in tests
        # This test would need to be adjusted based on how geocoding is handled
        response = client.get("/v1/city/current?city_slug=vienna")
        # The response might fail due to geocoding, but we can test the structure
        # In a real test environment, you might want to mock the geocoding service
    
    def test_get_current_measurements_old_data(self, sample_data):
        """Test getting current measurements with old data (outside 1-hour window)"""
        db = next(override_get_db())
        
        # Update measurement to be older than 1 hour
        # Query by known device name to avoid DetachedInstanceError
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        station = db.query(Station).filter(Station.device == "test_station_1").first()
        station.last_active = old_time
        # Query measurement by station_id
        measurement = db.query(Measurement).filter(Measurement.station_id == station.id).first()
        measurement.time_measured = old_time
        db.commit()
        
        response = client.get("/v1/city/current?city_slug=vienna")
        assert response.status_code == 200
        
        data = response.json()
        # Should return empty values since data is too old
        assert len(data["properties"]["values"]) == 0
    
    def test_get_current_measurements_multiple_stations(self, sample_data):
        """Test getting current measurements with multiple stations"""
        db = next(override_get_db())
        
        # Get location_id by querying by known coordinates to avoid DetachedInstanceError
        location = db.query(Location).filter(Location.lat == 48.2082, Location.lon == 16.3738).first()
        location_id = location.id
        
        # Add another station with last_active set
        measurement_time2 = datetime.now(timezone.utc)
        station2 = Station(
            device="test_station_2",
            location_id=location_id,
            last_active=measurement_time2
        )
        db.add(station2)
        db.commit()
        db.refresh(station2)
        
        # Add measurement for second station (using integer sensor model ID: SDS011=13)
        # Use the same time as station2.last_active
        # Measurement needs location_id for the city query to work
        from enums import SensorModel
        measurement2 = Measurement(
            station_id=station2.id,
            location_id=location_id,
            time_measured=measurement_time2,
            sensor_model=SensorModel.SDS011
        )
        db.add(measurement2)
        db.commit()
        db.refresh(measurement2)
        
        # Add values for second measurement
        from enums import Dimension
        values2 = [
            Values(measurement_id=measurement2.id, dimension=Dimension.PM1_0, value=15.0),
            Values(measurement_id=measurement2.id, dimension=Dimension.PM2_5, value=8.0)
        ]
        for value in values2:
            db.add(value)
        db.commit()
        
        response = client.get("/v1/city/current?city_slug=vienna")
        assert response.status_code == 200
        
        data = response.json()
        assert data["properties"]["station_count"] == 2
        
        # Should have aggregated values from both stations
        values = data["properties"]["values"]
        assert len(values) > 0
