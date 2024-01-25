from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import requests

from models.models import User


def download_csv(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
)


@app.get("/v1/station/current/all/", response_class=Response)
async def get_current_station_data():
    """
    Returns the active stations with lat, lon, PM1, PM10 and PM2.5.
    """
    csv_url = "https://dev.luftdaten.at/d/station/history/all"
    csv_data = download_csv(csv_url)
    return Response(content=csv_data, media_type="text/csv")


@app.get("/v1/station/history/", response_class=Response)
async def get_history_station_data(station_ids: str = None, smooth: str = "100", start: str = None):
    """
    Returns the values from a single station in a given time.
    """
    csv_url = f"https://dev.luftdaten.at/d/station/history?sid=${station_ids}&smooth={smooth}&from=${start}"
    csv_data = download_csv(csv_url)
    return Response(content=csv_data, media_type="text/csv")