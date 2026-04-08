import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from models import City, Country, Station, Location, Measurement, Values
from db_testing import TestSyncSessionLocal
from utils.response_cache import get_cities_cache
from datetime import datetime, timezone, timedelta
from enums import SensorModel, Dimension

client = TestClient(app)


@pytest.fixture
def sample_data():
    db = TestSyncSessionLocal()
    country = Country(name="Austria", code="AT")
    db.add(country)
    db.commit()
    db.refresh(country)

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

    location = Location(
        lat=48.2082,
        lon=16.3738,
        height=100.0,
        city_id=city.id
    )
    db.add(location)
    db.commit()
    db.refresh(location)

    measurement_time = datetime.now(timezone.utc)
    station = Station(
        device="test_station_1",
        location_id=location.id,
        last_active=measurement_time
    )
    db.add(station)
    db.commit()
    db.refresh(station)

    measurement = Measurement(
        station_id=station.id,
        location_id=location.id,
        time_measured=measurement_time,
        sensor_model=SensorModel.SDS011
    )
    db.add(measurement)
    db.commit()
    db.refresh(measurement)

    values = [
        Values(measurement_id=measurement.id, dimension=Dimension.PM1_0, value=10.5),
        Values(measurement_id=measurement.id, dimension=Dimension.PM2_5, value=5.2),
        Values(measurement_id=measurement.id, dimension=Dimension.TEMPERATURE, value=22.0)
    ]
    for value in values:
        db.add(value)
    db.commit()

    try:
        yield {
            "_db": db,
            "country": country,
            "city": city,
            "location": location,
            "station": station,
            "measurement": measurement,
            "values": values
        }
    finally:
        db.close()


class TestCityRouter:

    def test_get_all_cities_no_data(self):
        response = client.get("/v1/city/all")
        assert response.status_code == 404
        assert response.json() == {"detail": "No cities found"}

    def test_get_all_cities_with_data(self, sample_data):
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
        db = sample_data["_db"]

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

        get_cities_cache().invalidate("cities_all")

        response = client.get("/v1/city/all")
        assert response.status_code == 200

        data = response.json()
        assert len(data["cities"]) == 2

        city_names = [c["name"] for c in data["cities"]]
        assert "Vienna" in city_names
        assert "Berlin" in city_names

    def test_get_current_measurements_city_not_found(self):
        response = client.get("/v1/city/current?city_slug=nonexistent")
        assert response.status_code == 404
        assert response.json() == {"detail": "City not found"}

    def test_get_current_measurements_city_found_no_stations(self, sample_data):
        db = sample_data["_db"]
        db.delete(sample_data["station"])
        db.commit()

        response = client.get("/v1/city/current?city_slug=vienna")
        assert response.status_code == 200

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

        values = data["properties"]["values"]
        assert len(values) > 0

        for value in values:
            assert "dimension" in value
            assert "value" in value
            assert "value_count" in value
            assert "station_count" in value

    def test_get_current_measurements_city_without_coordinates(self, sample_data):
        db = sample_data["_db"]
        sample_data["city"].lat = None
        sample_data["city"].lon = None
        db.commit()

        response = client.get("/v1/city/current?city_slug=vienna")

    def test_get_current_measurements_old_data(self, sample_data):
        db = sample_data["_db"]
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        sample_data["station"].last_active = old_time
        sample_data["measurement"].time_measured = old_time
        db.commit()

        response = client.get("/v1/city/current?city_slug=vienna")
        assert response.status_code == 200

        data = response.json()
        assert len(data["properties"]["values"]) == 0

    def test_get_current_measurements_multiple_stations(self, sample_data):
        db = sample_data["_db"]
        location_id = sample_data["location"].id

        measurement_time2 = datetime.now(timezone.utc)
        station2 = Station(
            device="test_station_2",
            location_id=location_id,
            last_active=measurement_time2
        )
        db.add(station2)
        db.commit()
        db.refresh(station2)

        measurement2 = Measurement(
            station_id=station2.id,
            location_id=location_id,
            time_measured=measurement_time2,
            sensor_model=SensorModel.SDS011
        )
        db.add(measurement2)
        db.commit()
        db.refresh(measurement2)

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

        values = data["properties"]["values"]
        assert len(values) > 0
