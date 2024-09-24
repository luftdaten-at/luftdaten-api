from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime


class MeasurementCreate(BaseModel):
    dim: int
    val: float


class LocationCreate(BaseModel):
    lat: float
    lon: float
    height: float


class StationDataCreate(BaseModel):
    time: datetime
    device: str
    location: LocationCreate


class SensorDataCreate(BaseModel):
    sensors: Dict[str, MeasurementCreate]