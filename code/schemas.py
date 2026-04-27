import os

from pydantic import BaseModel, RootModel, Field
from typing import Dict, Optional
from datetime import datetime

_STATION_APIKEY_MIN_LEN = int(os.getenv("STATION_APIKEY_MIN_LENGTH", "16"))


class ValueCreate(BaseModel):
    dimension: int
    value: float


class LocationCreate(BaseModel):
    lat: float
    lon: float
    height: float | None = None


class StationDataCreate(BaseModel):
    time: datetime = Field(
        ...,
        description=(
            "Measurement time in UTC. Prefer ISO-8601 with `Z` or explicit offset (e.g. `2026-04-10T12:00:00Z`). "
            "If no timezone is given, the value is interpreted as UTC wall clock."
        ),
    )
    device: str
    firmware: str
    apikey: str
    location: LocationCreate
    source: Optional[int] = 1
    calibration_mode: Optional[bool] = False


class SensorDataCreate(BaseModel):
    type: int  # Sensor type (z.B. 1 oder 6)
    data: Dict[int, float]  # Dictionary der Daten (z.B., {2: 5.0, 3: 6.0, ...})


class SensorsCreate(RootModel[Dict[int, SensorDataCreate]]):
    pass


class StationStatusCreate(BaseModel):
    time: datetime
    level: int
    message: str


class StationApiKeyAdminSet(BaseModel):
    """Admin-only body to set ``stations.apikey`` for a device (requires ``Authorization: Bearer`` admin token)."""

    device: str = Field(..., min_length=1, description="Station device id (`stations.device`).")
    new_apikey: str = Field(
        ...,
        min_length=_STATION_APIKEY_MIN_LEN,
        max_length=512,
        description=f"New station API key (min {_STATION_APIKEY_MIN_LEN} chars; override with STATION_APIKEY_MIN_LENGTH).",
    )


class CityAdminSet(BaseModel):
    """Admin-only body to update a city record (requires Bearer admin token).

    The current ``slug`` identifies the city; the new ``slug`` is regenerated
    from ``name`` via slugify, matching ``City.__init__`` behavior.
    """

    slug: str = Field(..., min_length=1, description="Current slug of the city to update.")
    name: str = Field(..., min_length=1, max_length=255)
    tz: str = Field(..., min_length=1, description="IANA timezone, e.g. 'Europe/Vienna'.")
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    country_code: str = Field(
        ...,
        min_length=2,
        max_length=3,
        description="ISO country code (cities.country_id resolved via countries.code).",
    )
