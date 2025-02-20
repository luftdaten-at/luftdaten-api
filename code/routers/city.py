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
    # Abfrage aller Städte in der Datenbank
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
    city_slug: str = Query(..., description="The name of the city to get the average measurements for."),
    db: Session = Depends(get_db)
):
    db_city = db.query(City).filter(City.slug == city_slug).first()

    if not db_city:
        raise HTTPException(status_code=404, detail="City not found")

    if not all([db_city.lat, db_city.lon]):
        lat, lon = Nominatim(user_agent="api.luftdaten.at").geocode(city_slug)[1]
        db_city.lat = lat
        db_city.lon = lon
        db.commit()
    

    # only select the measurements from the last hour
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=1)

    LOWER, UPPER = Dimension.get_filter_threshold(Dimension.PM2_5)

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
        # filter outlier
        #.filter(or_(Values.dimension != Dimension.PM2_5, and_(LOWER <= Values.value, Values.value <= UPPER)))
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

    return Response(content=json.dumps(j), media_type="pplication/geo+json")


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