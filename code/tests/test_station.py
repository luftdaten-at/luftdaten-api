# tests/test_station.py
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import get_db
from app.models import Station
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

# Konfiguriere eine Testdatenbank (in-memory SQLite)
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# TestClient für FastAPI-App erstellen
client = TestClient(app)

# Eine Abhängigkeit überschreiben, um die Testdatenbank zu verwenden
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
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_get_station_no_data():
    response = client.get("/v1/station/current")
    assert response.status_code == 404
    assert response.json() == {"detail": "No stations found"}

def test_create_station():
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

    # Teste, ob die Station tatsächlich in der Datenbank erstellt wurde
    db = next(override_get_db())
    station = db.query(Station).filter_by(device="test_device_123").first()
    assert station is not None
    assert station.device == "test_device_123"