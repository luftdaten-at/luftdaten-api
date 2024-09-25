from pydantic import BaseModel, RootModel
from typing import Dict, Optional
from datetime import datetime


class ValueCreate(BaseModel):
    dimension: int
    value: float


class LocationCreate(BaseModel):
    lat: float
    lon: float
    height: float | None = None


class StationDataCreate(BaseModel):
    time: datetime
    device: str
    location: LocationCreate


class SensorDataCreate(BaseModel):
    type: int  # Sensor type (z.B. 1 oder 6)
    data: Dict[int, float]  # Dictionary der Daten (z.B., {2: 5.0, 3: 6.0, ...})


class SensorsCreate(RootModel[Dict[int, SensorDataCreate]]):
    pass