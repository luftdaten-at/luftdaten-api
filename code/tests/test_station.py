import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from models import Station, Location, Measurement, Values, CalibrationMeasurement, Country, City
from db_testing import TestSyncSessionLocal
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import csv
import io
from unittest.mock import patch, MagicMock

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
        city_id=city.id,
        country_id=country.id
    )
    db.add(location)
    db.commit()
    db.refresh(location)

    station = Station(
        device="test_station_1",
        location_id=location.id,
        last_active=datetime.now(timezone.utc),
        firmware="1.0"
    )
    db.add(station)
    db.commit()
    db.refresh(station)

    measurement = Measurement(
        station_id=station.id,
        location_id=location.id,
        time_measured=station.last_active,
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

    calibration_measurement = CalibrationMeasurement(
        station_id=station.id,
        location_id=location.id,
        time_measured=station.last_active,
        sensor_model=SensorModel.SDS011
    )
    db.add(calibration_measurement)
    db.commit()
    db.refresh(calibration_measurement)

    calibration_values = [
        Values(calibration_measurement_id=calibration_measurement.id, dimension=Dimension.PM1_0, value=9.8),
        Values(calibration_measurement_id=calibration_measurement.id, dimension=Dimension.PM2_5, value=4.9)
    ]
    for value in calibration_values:
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
            "values": values,
            "calibration_measurement": calibration_measurement,
            "calibration_values": calibration_values
        }
    finally:
        db.close()


class TestStationRouter:

    def test_get_current_station_data_no_data(self):
        response = client.get("/v1/station/current")
        assert response.status_code == 404
        assert response.json() == {"detail": "No stations found"}

    def test_get_current_station_data_with_data(self, sample_data):
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
        response = client.get("/v1/station/current?output_format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) > 1

        header = lines[0].split(',')
        expected_header = ["device", "lat", "lon", "last_active", "height", "sensor_model", "dimension", "value"]
        for field in expected_header:
            assert field in header

    def test_get_current_station_data_with_calibration(self, sample_data):
        response = client.get("/v1/station/current?calibration_data=true")
        assert response.status_code == 200

        data = response.json()
        feature = data["features"][0]
        assert "calibration_sensors" in feature["properties"]
        assert len(feature["properties"]["calibration_sensors"]) > 0

    def test_get_current_station_data_specific_stations(self, sample_data):
        response = client.get("/v1/station/current?station_ids=test_station_1")
        assert response.status_code == 200

        data = response.json()
        assert len(data["features"]) == 1
        assert data["features"][0]["properties"]["device"] == "test_station_1"

    def test_get_current_station_data_inactive_stations(self, sample_data):
        db = sample_data["_db"]
        vienna_tz = ZoneInfo("Europe/Vienna")
        old_time = datetime.now(vienna_tz) - timedelta(hours=2)
        old_time_utc = old_time.astimezone(timezone.utc).replace(tzinfo=None)

        sample_data["station"].last_active = old_time_utc
        sample_data["measurement"].time_measured = old_time_utc
        db.commit()

        response = client.get("/v1/station/current")
        assert response.status_code == 404
        assert response.json() == {"detail": "No stations found"}

    def test_get_current_station_data_cache_headers_geojson(self, sample_data):
        response = client.get("/v1/station/current")
        assert response.status_code == 200
        cc = response.headers.get("cache-control", "")
        assert "public" in cc
        assert "max-age=60" in cc
        assert "etag" in response.headers

    def test_get_current_station_data_cache_headers_csv(self, sample_data):
        response = client.get("/v1/station/current?output_format=csv")
        assert response.status_code == 200
        assert "max-age=60" in response.headers.get("cache-control", "")
        assert "etag" in response.headers

    def test_get_current_station_data_304_if_none_match(self, sample_data):
        r1 = client.get("/v1/station/current")
        assert r1.status_code == 200
        etag = r1.headers["etag"]
        r2 = client.get("/v1/station/current", headers={"If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.content == b""

    def test_get_station_info_not_found(self):
        response = client.get("/v1/station/info?station_id=nonexistent")
        assert response.status_code == 404
        assert response.json() == {"detail": "Station not found"}

    def test_get_station_info_found(self, sample_data):
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
        response = client.get("/v1/station/calibration")
        assert response.status_code == 200
        assert response.text.strip() == ""

    def test_get_calibration_data_with_data(self, sample_data):
        response = client.get("/v1/station/calibration")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        csv_content = response.text
        assert "test_station_1" in csv_content
        assert "13" in csv_content

    def test_get_calibration_data_specific_stations(self, sample_data):
        response = client.get("/v1/station/calibration?station_ids=test_station_1")
        assert response.status_code == 200
        assert "test_station_1" in response.text

    def test_get_calibration_data_no_data_flag(self, sample_data):
        response = client.get("/v1/station/calibration?data=false")
        assert response.status_code == 200
        lines = response.text.strip().split('\n')
        assert len(lines) == 1
        assert "test_station_1" in response.text

    def test_post_station_data_success(self):
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

        response = client.post("/v1/station/data", json={"station": station_data, "sensors": sensors})
        assert response.status_code == 200
        assert response.json() == {"status": "success"}

        # Trailing slash must hit the handler directly (no 307); use another device to avoid duplicate measurement
        station_data_slash = {**station_data, "device": "test_device_trailing_slash"}
        response_slash = client.post(
            "/v1/station/data/", json={"station": station_data_slash, "sensors": sensors}
        )
        assert response_slash.status_code == 200
        assert response_slash.json() == {"status": "success"}

        db = TestSyncSessionLocal()
        try:
            r = db.execute(select(Station).where(Station.device == "test_device_123"))
            station = r.scalar_one_or_none()
            assert station is not None
            assert station.device == "test_device_123"
        finally:
            db.close()

    def test_post_station_status_success(self):
        mock_tf = MagicMock()
        mock_tf.timezone_at.return_value = 'Europe/Vienna'
        with patch('utils.geocoding.reverse_geocode') as mock_reverse_geocode, \
             patch('utils.geocoding.Nominatim') as mock_nominatim, \
             patch('utils.geocoding.tf', mock_tf):
            mock_reverse_geocode.return_value = ('Vienna', 'Austria', 'at')

            mock_geocoder = MagicMock()
            mock_geocoder.geocode.return_value = (None, (48.2082, 16.3738))
            mock_nominatim.return_value = mock_geocoder

            station_data = {
                "device": "test_device_123",
                "firmware": "1.0",
                "apikey": "testapikey123",
                "time": "2024-04-29T08:25:20.766Z",
                "location": {
                    "lat": 48.2082,
                    "lon": 16.3738,
                    "height": 100.5
                }
            }
            status_list = [{
                "time": "2024-04-29T08:25:20.766Z",
                "level": 1,
                "message": "online"
            }]

            response = client.post("/v1/station/status", json={"station": station_data, "status_list": status_list})
            assert response.status_code == 200
            assert response.json() == {"status": "success"}

            station_status_slash = {**station_data, "device": "test_device_status_slash"}
            response_slash = client.post(
                "/v1/station/status/",
                json={"station": station_status_slash, "status_list": status_list},
            )
            assert response_slash.status_code == 200
            assert response_slash.json() == {"status": "success"}

    def test_get_all_stations_no_data(self):
        response = client.get("/v1/station/all")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        lines = response.text.strip().split('\n')
        assert len(lines) == 1

    def test_get_all_stations_with_data(self, sample_data):
        response = client.get("/v1/station/all")
        assert response.status_code == 200

        csv_content = response.text
        lines = csv_content.strip().split('\n')
        assert len(lines) == 2

        header = [field.strip('\r') for field in lines[0].split(',')]
        expected_header = ["id", "last_active", "location_lat", "location_lon", "measurements_count"]
        for field in expected_header:
            assert field in header

        assert "test_station_1" in csv_content

    def test_get_all_stations_json_format(self, sample_data):
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
        response = client.get("/v1/station/topn?n=5&dimension=1&order=min&output_format=csv")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        lines = response.text.strip().split('\n')
        assert len(lines) > 0

    def test_get_historical_station_data(self, sample_data):
        response = client.get("/v1/station/historical?station_ids=test_station_1&output_format=csv")
        assert response.status_code == 200
        lines = response.text.strip().split('\n')
        assert len(lines) > 0

    def test_get_historical_station_data_current(self, sample_data):
        response = client.get(
            "/v1/station/historical?station_ids=test_station_1&end=current&output_format=csv"
        )
        assert response.status_code == 200
        assert "test_station_1" in response.text

    def test_get_historical_station_data_missing_station_ids(self, sample_data):
        response = client.get("/v1/station/historical?output_format=csv")
        assert response.status_code == 422

    def test_get_historical_station_data_empty_station_ids(self, sample_data):
        response = client.get("/v1/station/historical?station_ids=&output_format=csv")
        assert response.status_code == 422
        assert "device ID" in response.json()["detail"]

        response = client.get("/v1/station/historical?station_ids=,,,&output_format=csv")
        assert response.status_code == 422

    def test_get_historical_station_data_invalid_date(self, sample_data):
        response = client.get(
            "/v1/station/historical?station_ids=test_station_1&start=invalid-date&output_format=csv"
        )
        assert response.status_code == 400
        assert "Invalid date format" in response.json()["detail"]

    def test_get_current_station_data_all_old_endpoint(self, sample_data):
        response = client.get("/v1/station/current/all")
        assert response.status_code == 200
        lines = response.text.strip().split('\n')
        assert len(lines) > 0

    def test_get_station_history_old_endpoint(self, sample_data):
        response = client.get("/v1/station/history")
        assert response.status_code == 200
