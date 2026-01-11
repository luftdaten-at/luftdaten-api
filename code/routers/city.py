import json
import numpy as np
from geopy.geocoders import Nominatim
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from database import get_db
from sqlalchemy import func, or_, distinct, and_
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from models import City, Country, Station, Measurement, Values, Location
from enums import Dimension


router = APIRouter()


@router.get("/all", tags=["city"])
async def get_all_cities(db: Session = Depends(get_db)):
    """
    Get all cities in the database.
    
    Returns a list of all cities with their names, slugs, and associated country information.
    Cities are locations where air quality monitoring stations are deployed.
    
    **Response:**
    JSON object containing an array of cities:
    - **id**: City database ID
    - **name**: City name
    - **slug**: URL-friendly city identifier
    - **country**: Object containing country name and slug
    
    **Example Response:**
    ```json
    {
      "cities": [
        {
          "id": 1,
          "name": "Vienna",
          "slug": "vienna",
          "country": {
            "name": "Austria",
            "slug": "austria"
          }
        }
      ]
    }
    ```
    
    **Errors:**
    - 404: No cities found in database
    """
    cities = db.query(City, Country).join(Country, City.country_id == Country.id).all()

    if not cities:
        raise HTTPException(status_code=404, detail="No cities found")

    response = {
        "cities": [
            {
                "id": city.id,
                "name": city.name,
                "slug": city.slug,
                "country": {
                    "name": country.name,
                    "slug": country.slug
                }
            } 
            for city, country in cities
        ]
    }
    return response


@router.get("/current", tags=["city", "current"])
async def get_average_measurements_by_city(
    city_slug: str = Query(..., description="The slug (URL-friendly identifier) of the city to get average measurements for. Use /city/all to get available city slugs."),
    db: Session = Depends(get_db)
):
    """
    Get current average air quality measurements for a city.
    
    Returns aggregated air quality data for all active stations in a city.
    Measurements are averaged from the last hour, with outlier filtering using
    percentile-based method (alpha/2 on each side, default alpha=0.1).
    
    **Parameters:**
    - **city_slug**: City slug identifier (required)
      - Use `/city/all` endpoint to get available city slugs
    
    **Response Format:**
    - GeoJSON Feature with Point geometry
    - Properties include:
      - **name**: City name
      - **city_slug**: City identifier
      - **country**: Country name
      - **timezone**: City timezone
      - **time**: Current time in city timezone (ISO format)
      - **station_count**: Number of stations in the city
      - **values**: Array of aggregated measurements:
        - **dimension**: Dimension ID (e.g., 2=PM1.0, 3=PM2.5)
        - **value**: Averaged value (outliers filtered)
        - **value_count**: Number of individual values used
        - **station_count**: Number of stations contributing
    
    **Data Processing:**
    1. Only measurements from the last hour are included
    2. NaN values are filtered out
    3. Outliers are removed using percentile filtering (alpha=0.1)
    4. Remaining values are averaged per dimension
    
    **Example Response:**
    ```json
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [16.3738, 48.2082]
      },
      "properties": {
        "name": "Vienna",
        "city_slug": "vienna",
        "country": "Austria",
        "timezone": "Europe/Vienna",
        "time": "2024-01-01T13:00:00+01:00",
        "station_count": 5,
        "values": [
          {
            "dimension": 2,
            "value": 10.5,
            "value_count": 15,
            "station_count": 3
          },
          {
            "dimension": 3,
            "value": 15.2,
            "value_count": 15,
            "station_count": 3
          }
        ]
      }
    }
    ```
    
    **Errors:**
    - 404: City not found
    - Note: If city coordinates are missing, they will be geocoded automatically
    """
    db_city = db.query(City).filter(City.slug == city_slug).first()

    if not db_city:
        raise HTTPException(status_code=404, detail="City not found")

    if not all([db_city.lat, db_city.lon]):
        lat, lon = Nominatim(user_agent="api.luftdaten.at", domain="nominatim.dataplexity.eu", scheme="https").geocode(city_slug)[1]
        db_city.lat = lat
        db_city.lon = lon
        db.commit()
    

    # only select the measurements from the last hour
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1)

    q = (
        db.query(
            Values.dimension,
            func.array_agg(Values.value),
            func.count(Values.id), 
            func.count(distinct(Station.id)),
        )
        .select_from(Values)
        .join(Measurement)
        .join(Location)
        .join(City)
        .join(Station, Station.id == Measurement.station_id)
        .filter(City.slug == city_slug)
        .filter(Values.value != 'nan')
        .filter(Measurement.time_measured >= start)
        .group_by(Values.dimension)
    )

    print(len(q.all()))

    station_count = db.query(Station).join(Location).join(City).filter(City.slug == city_slug).count()

    # filter outlier with Quartiles
    data = []
    for dim, val_list, val_count, s_cnt in q.all():
        a = np.array(val_list)

        l = np.percentile(a, 100 * (Dimension.ALPHA / 2))
        r = np.percentile(a, 100 * (1 - (Dimension.ALPHA / 2)))

        b = a[(a >= l) & (a <= r)]

        # Only compute mean if array is not empty to avoid numpy warnings
        if len(b) > 0:
            data.append((dim, np.mean(b), val_count, s_cnt))

    j = {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [db_city.lon, db_city.lat],
        },
        "properties": {
            "name": db_city.name,
            "city_slug": db_city.slug,
            "country": db_city.country.name,
            "timezone": db_city.tz,
            "time": datetime.now(ZoneInfo(db_city.tz)).replace(second=0, microsecond=0).isoformat(),
            "station_count": station_count,
            "values":[{
                "dimension": dim, 
                "value": val,
                "value_count": val_count,
                "station_count": s_cnt
            } for dim, val, val_count, s_cnt in data],
        }
    }

    return Response(content=json.dumps(j), media_type="application/geo+json")


# @router.get("/currentold", tags=["city", "current"])
# async def get_average_measurements_by_city_old(
#     city_slug: str = Query(..., description="The name of the city to get the average measurements for."),
#     db: Session = Depends(get_db)
# ):
#     # Suche die Stadt in der Datenbank
#     city = db.query(City).filter(City.slug == city_slug).first()

#     if not city:
#         raise HTTPException(status_code=404, detail="City not found")

#     # Überprüfe, ob city.tz gesetzt ist
#     if city.tz is None:
#         # Fallback auf eine Standard-Zeitzone, z.B. 'Europe/Vienna'
#         timezone = ZoneInfo('Europe/Vienna')
#     else:
#         # Nutze die Zeitzone der Stadt
#         timezone = ZoneInfo(city.tz)

#     # Finde alle Stationen, die mit dieser Stadt verknüpft sind
#     stations = db.query(Station).filter(Station.location.has(city_id=city.id)).all()

#     if not stations:
#         raise HTTPException(status_code=404, detail="No stations found in this city")

#     # Erstelle eine Liste, um die letzten Messwerte jeder Station zu speichern
#     last_measurements = []

#     for station in stations:
#         # Finde die letzte Messung für die Station (nach time_measured)
#         last_measurement = db.query(Measurement).filter(
#             Measurement.station_id == station.id
#         ).order_by(desc(Measurement.time_measured)).first()

#         if last_measurement:
#             # Füge alle Werte (dimension, value) der letzten Messung hinzu
#             values = db.query(Values).filter(Values.measurement_id == last_measurement.id).all()
#             last_measurements.extend(values)

#     if not last_measurements:
#         raise HTTPException(status_code=404, detail="No measurements found for stations in this city")

#     # Berechne den Durchschnitt der letzten Messwerte pro Dimension
#     avg_measurements = db.query(
#         Values.dimension,
#         func.avg(Values.value).label("avg_value")
#     ).filter(Values.id.in_([value.id for value in last_measurements]))\
#      .group_by(Values.dimension)\
#      .all()

#     # Bereite die Antwort im GeoJSON-Format vor
#     response = {
#         "city": city.name,
#         "time": datetime.now(timezone).isoformat(),
#         "values": [
#             {
#                 "dimension": dimension,
#                 "name": Dimension.get_name(dimension),
#                 "average": f"{avg_value:.2f}",
#                 "unit": Dimension.get_unit(dimension)
#             }
#             for dimension, avg_value in avg_measurements
#         ]
#     }

#     return response