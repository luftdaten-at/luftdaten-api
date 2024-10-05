import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

import logging
import pytest
import asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from main import app
from database import get_db, Base
from models import Station, Location, Measurement, Values, City, Country  # Importiere alle Modelle

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Konfiguriere eine Testdatenbank (PostgreSQL)
SQLALCHEMY_DATABASE_URL = "postgresql://test_user:test_password@db_test/test_database"
engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# TestClient für FastAPI-App erstellen
client = TestClient(app)

# Überschreibe die Abhängigkeit, um die Testdatenbank zu verwenden
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Vor jedem Test die Datenbanktabellen neu erstellen
@pytest.fixture(scope="function", autouse=True)
def setup_database():
    logging.debug("Setting up the database.")
    Base.metadata.create_all(bind=engine)
    yield
    logging.debug("Tearing down the database.")
    Base.metadata.drop_all(bind=engine)
    logging.debug("Database teardown complete.")

@pytest.mark.asyncio
async def test_get_station_no_data():
    response = await client.get("/v1/station/current")
    assert response.status_code == 404
    assert response.json() == {"detail": "No stations found"}

    # Schließe den EventLoop
    await asyncio.get_event_loop().shutdown_asyncgens()
    asyncio.get_event_loop().stop()

def test_create_station_without_source():
    """
    Testet die Erstellung einer Station, wenn das Feld 'source' nicht mitgesendet wird.
    Es sollte der Standardwert '1' gesetzt werden.
    """
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
        "1": { "type": 1, "data": { "2": 5.0, "3": 6.0 }}
    }

    response = client.post("/v1/station/data/", json={"station": station_data, "sensors": sensors})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    # Teste, ob die Station tatsächlich in der Datenbank erstellt wurde und der Standardwert für 'source' gesetzt wurde
    db = next(override_get_db())
    station = db.query(Station).filter_by(device="test_device_123").first()
    assert station is not None
    assert station.device == "test_device_123"
    assert station.source == 1  # Standardwert für 'source' sollte 1 sein

@pytest.mark.asyncio
async def test_create_station_with_source():
    """
    Testet die Erstellung einer Station mit einem angegebenen 'source'-Wert.
    """
    station_data = {
        "device": "test_device_456",
        "location": {
            "lat": 48.2082,
            "lon": 16.3738,
            "height": 100.5
        },
        "time": "2024-04-29T08:25:20.766Z",
        "firmware": "1.0",
        "apikey": "testapikey456",
        "source": 2  # Explicitly set source
    }

    sensors = {
        "1": { "type": 1, "data": { "2": 5.0, "3": 6.0 }}
    }

    response = await client.post("/v1/station/data/", json={"station": station_data, "sensors": sensors})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    await asyncio.get_event_loop().shutdown_asyncgens()
    asyncio.get_event_loop().stop()

    # Teste, ob die Station tatsächlich in der Datenbank erstellt wurde und der 'source'-Wert korrekt gesetzt wurde
    db = next(override_get_db())
    station = db.query(Station).filter_by(device="test_device_456").first()
    assert station is not None
    assert station.device == "test_device_456"
    assert station.source == 2