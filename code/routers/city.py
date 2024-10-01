from fastapi import APIRouter, Depends, Response, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import get_db
from models import Station, Measurement, Values
from schemas import StationDataCreate, SensorsCreate
from utils import get_or_create_location, download_csv
import json

router = APIRouter()


# @router.get("/v1/city/current/", response_class=Response)
# async def get_current_station_data(
#     city: str = None
# ):
#     data = ""
#     return Response(content=data, media_type="application/json")