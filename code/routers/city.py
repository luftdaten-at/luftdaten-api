import json
import logging
import numpy as np
from geopy.geocoders import Nominatim
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from dependencies import get_blacklist, verify_admin_api_key
from sqlalchemy import func, distinct, select, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database import get_db
from utils.helpers import as_naive_utc, format_datetime_vienna_iso
from datetime import datetime, timezone, timedelta
from models import City, Country, Station, Measurement, Values, Location
from enums import Dimension
from schemas import CityAdminSet
from utils import update_city_admin
from utils.response_cache import get_cities_cache


router = APIRouter()


@router.get("/all", tags=["city"])
async def get_all_cities(db: AsyncSession = Depends(get_db)):
    """
    Get all cities in the database.

    Returns a list of all cities with their names, slugs, location coordinates, and associated country information.
    Cities are locations where air quality monitoring stations are deployed.
    """
    cache = get_cities_cache()
    cache_key = "cities_all"
    cached_response = cache.get(cache_key)

    if cached_response:
        logging.getLogger(__name__).debug(f"Cache hit for {cache_key}")
        return Response(content=cached_response, media_type="application/json")

    logging.getLogger(__name__).debug(f"Cache miss for {cache_key}")

    r = await db.execute(
        select(City, Country)
        .join(Country, City.country_id == Country.id)
    )
    cities = r.all()

    if not cities:
        raise HTTPException(status_code=404, detail="No cities found")

    response = {
        "cities": [
            {
                "id": city.id,
                "name": city.name,
                "slug": city.slug,
                "location": {
                    "latitude": city.lat,
                    "longitude": city.lon
                } if city.lat is not None and city.lon is not None else None,
                "country": {
                    "name": country.name,
                    "slug": country.slug
                }
            }
            for city, country in cities
        ]
    }

    response_content = json.dumps(response).encode('utf-8')
    cache.set(cache_key, response_content)

    return Response(content=response_content, media_type="application/json")


@router.get("/current", tags=["city", "current"])
async def get_average_measurements_by_city(
    city_slug: str = Query(..., description="The slug (URL-friendly identifier) of the city to get average measurements for. Use /city/all to get available city slugs."),
    db: AsyncSession = Depends(get_db),
    blacklist: frozenset[str] = Depends(get_blacklist),
):
    """
    Get current average air quality measurements for a city.
    """
    r = await db.execute(
        select(City)
        .where(City.slug == city_slug)
        .options(selectinload(City.country))
    )
    db_city = r.scalar_one_or_none()

    if not db_city:
        raise HTTPException(status_code=404, detail="City not found")

    if not all([db_city.lat, db_city.lon]):
        lat, lon = Nominatim(user_agent="api.luftdaten.at", domain="nominatim.dataplexity.eu", scheme="https").geocode(city_slug)[1]
        db_city.lat = lat
        db_city.lon = lon
        await db.commit()

        cache = get_cities_cache()
        cache.invalidate("cities_all")

    now = datetime.now(timezone.utc)
    start = as_naive_utc(now - timedelta(hours=1))

    stmt = (
        select(
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
        .where(City.slug == city_slug)
        .where(cast(Values.value, String) != 'nan')
        .where(Measurement.time_measured >= start)
        .group_by(Values.dimension)
    )
    if blacklist:
        stmt = stmt.where(~Station.device.in_(blacklist))

    r = await db.execute(stmt)
    q_rows = r.all()

    cnt_stmt = (
        select(func.count())
        .select_from(Station)
        .join(Location)
        .join(City)
        .where(City.slug == city_slug)
    )
    if blacklist:
        cnt_stmt = cnt_stmt.where(~Station.device.in_(blacklist))
    r = await db.execute(cnt_stmt)
    station_count = r.scalar() or 0

    data = []
    for dim, val_list, val_count, s_cnt in q_rows:
        a = np.array(val_list)

        l = np.percentile(a, 100 * (Dimension.ALPHA / 2))
        r_p = np.percentile(a, 100 * (1 - (Dimension.ALPHA / 2)))

        b = a[(a >= l) & (a <= r_p)]

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
            "time": format_datetime_vienna_iso(
                datetime.now(timezone.utc).replace(second=0, microsecond=0)
            ),
            "station_count": station_count,
            "values": [{
                "dimension": dim,
                "value": val,
                "value_count": val_count,
                "station_count": s_cnt
            } for dim, val, val_count, s_cnt in data],
        }
    }

    return Response(content=json.dumps(j), media_type="application/geo+json")


@router.post("/admin", tags=["city"])
@router.post("/admin/", tags=["city"], include_in_schema=False)
async def admin_update_city(
    body: CityAdminSet,
    db: AsyncSession = Depends(get_db),
    _admin: None = Depends(verify_admin_api_key),
):
    """
    Admin-only: update an existing city by current ``slug`` (set ``Authorization: Bearer <ADMIN_API_KEY>``).
    The new ``slug`` is generated from ``name`` (slugify), matching ``City`` creation behavior.
    """
    await update_city_admin(db, body)
    get_cities_cache().invalidate("cities_all")
    return {"status": "success"}
