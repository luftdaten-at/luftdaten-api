"""
Geocoding utilities for location management.

This module handles reverse geocoding and location creation/retrieval
using Nominatim geocoding service.
"""

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from models import City, Country, Location
import logging
from schemas import CityAdminSet
from .response_cache import get_cities_cache

# Initialize TimezoneFinder
tf = TimezoneFinder()

NOMINATIM_KWARGS = {
    "user_agent": "api.luftdaten.at",
    "domain": "nominatim.dataplexity.eu",
    "scheme": "https",
}

LOCALITY_KEYS = (
    "city",
    "town",
    "village",
    "municipality",
    "borough",
    "suburb",
    "locality",
    "hamlet",
    "county",
)


def _locality_from_address(address: dict) -> str | None:
    """Return the best available locality name from a Nominatim address dict."""
    for key in LOCALITY_KEYS:
        value = address.get(key)
        if value:
            return value
    return None


def reverse_geocode(lat, lon):
    """
    Perform reverse geocoding to get city, country, and country code from coordinates.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Tuple of (city_name, country_name, country_code) or (None, None, None) if not found
    """
    geolocator = Nominatim(**NOMINATIM_KWARGS)
    location = geolocator.reverse((lat, lon), exactly_one=True)

    if location and "address" in location.raw:
        address = location.raw["address"]
        city = _locality_from_address(address)
        country = address.get("country", None)
        country_code = address.get("country_code", None)
        return city, country, country_code

    return None, None, None


def _city_coords(geolocator: Nominatim, city_name: str, lat: float, lon: float) -> tuple[float, float]:
    """Forward-geocode city name; fall back to station coordinates if lookup fails."""
    result = geolocator.geocode(city_name)
    if result is not None:
        return result.latitude, result.longitude
    return float(lat), float(lon)


async def _get_or_create_country(
    db: AsyncSession, country_name: str, country_code: str | None
) -> Country:
    r = await db.execute(select(Country).where(Country.name == country_name))
    country = r.scalar_one_or_none()
    if country is not None:
        return country
    try:
        country = Country(name=country_name, code=country_code)
        db.add(country)
        await db.commit()
        logging.debug(f"Neues Land erstellt: {country}")
        return country
    except Exception as e:
        logging.error(f"Fehler beim Erstellen des Landes '{country_name}': {e}")
        await db.rollback()
        raise


async def _get_or_create_city(
    db: AsyncSession,
    geolocator: Nominatim,
    city_name: str,
    country: Country,
    lat: float,
    lon: float,
) -> City:
    r = await db.execute(
        select(City).where(City.name == city_name, City.country_id == country.id)
    )
    city = r.scalar_one_or_none()
    if city is not None:
        return city
    try:
        timezone_str = tf.timezone_at(lng=float(lon), lat=float(lat))
        clat, clon = _city_coords(geolocator, city_name, lat, lon)
        city = City(name=city_name, country_id=country.id, tz=timezone_str, lat=clat, lon=clon)
        db.add(city)
        await db.commit()
        logging.debug(f"Neue Stadt erstellt: {city}")

        cache = get_cities_cache()
        cache.invalidate("cities_all")
        return city
    except Exception as e:
        logging.error(f"Fehler beim Erstellen der Stadt '{city_name}': {e}")
        await db.rollback()
        raise


async def _persist_location(
    db: AsyncSession,
    location: Location | None,
    lat: float,
    lon: float,
    height: float,
    city_id: int | None,
    country_id: int | None,
) -> Location:
    if location:
        logging.debug(f"Aktualisiere bestehende Location mit ID {location.id}")
        location.city_id = city_id
        location.country_id = country_id
        try:
            await db.commit()
            logging.debug(f"Location aktualisiert: {location}")
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Location: {e}")
            await db.rollback()
            raise
        return location

    try:
        location = Location(
            lat=lat,
            lon=lon,
            height=height,
            city_id=city_id,
            country_id=country_id,
        )
        db.add(location)
        await db.commit()
        logging.debug(f"Neue Location erstellt: {location}")
    except Exception as e:
        logging.error(f"Fehler beim Erstellen der Location: {e}")
        await db.rollback()
        raise
    return location


async def get_or_create_location(db: AsyncSession, lat: float, lon: float, height: float):
    """
    Get existing location or create a new one with geocoding.

    If a location with the same coordinates exists, it is returned.
    If it doesn't exist or lacks city/country information, reverse geocoding
    is performed to enrich the location data.

    Args:
        db: Database session
        lat: Latitude
        lon: Longitude
        height: Height above sea level

    Returns:
        Location object

    Raises:
        Exception: If geocoding fails or database operations fail
    """
    r = await db.execute(
        select(Location)
        .where(Location.lat == lat, Location.lon == lon, Location.height == height)
        .options(selectinload(Location.city), selectinload(Location.country))
    )
    location = r.scalar_one_or_none()

    if location:
        if location.city and location.country:
            return location

    try:
        city_name, country_name, country_code = reverse_geocode(lat, lon)
    except Exception as e:
        logging.error(f"Fehler bei reverse_geocode: {e}")
        raise

    if not country_name:
        logging.warning(
            "reverse_geocode lieferte kein Land für lat=%s lon=%s; Location ohne Stadt/Land",
            lat,
            lon,
        )
        return await _persist_location(db, location, lat, lon, height, None, None)

    country = await _get_or_create_country(db, country_name, country_code)

    city_id = None
    if city_name:
        geolocator = Nominatim(**NOMINATIM_KWARGS)
        city = await _get_or_create_city(db, geolocator, city_name, country, lat, lon)
        city_id = city.id
    else:
        logging.warning(
            "reverse_geocode lieferte keine Stadt für lat=%s lon=%s; Location nur mit Land %s",
            lat,
            lon,
            country_name,
        )

    return await _persist_location(db, location, lat, lon, height, city_id, country.id)


async def update_city_admin(db: AsyncSession, body: CityAdminSet) -> None:
    """Update an existing city by current slug (admin-only caller must be enforced by router)."""
    r = await db.execute(select(City).where(City.slug == body.slug))
    db_city = r.scalar_one_or_none()
    if db_city is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="City not found",
        )

    code = body.country_code.strip().upper()
    r = await db.execute(select(Country).where(Country.code == code))
    country = r.scalar_one_or_none()
    if country is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Country not found",
        )

    new_slug = slugify(body.name)
    db_city.name = body.name
    db_city.slug = new_slug
    db_city.tz = body.tz
    db_city.lat = body.lat
    db_city.lon = body.lon
    db_city.country_id = country.id

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="City slug already exists",
        ) from None
