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


def reverse_geocode(lat, lon):
    """
    Perform reverse geocoding to get city, country, and country code from coordinates.

    Args:
        lat: Latitude
        lon: Longitude

    Returns:
        Tuple of (city_name, country_name, country_code) or (None, None, None) if not found
    """
    geolocator = Nominatim(user_agent="api.luftdaten.at", domain="nominatim.dataplexity.eu", scheme="https")
    location = geolocator.reverse((lat, lon), exactly_one=True)

    if location and 'address' in location.raw:
        address = location.raw['address']
        city = address.get('city', None) or address.get('town', None) or address.get('village', None)
        country = address.get('country', None)
        country_code = address.get('country_code', None)
        return city, country, country_code

    return None, None, None


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

    r = await db.execute(select(Country).where(Country.name == country_name))
    country = r.scalar_one_or_none()
    if country is None:
        try:
            country = Country(name=country_name, code=country_code)
            db.add(country)
            await db.commit()
            logging.debug(f"Neues Land erstellt: {country}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen des Landes '{country_name}': {e}")
            await db.rollback()
            raise

    r = await db.execute(
        select(City).where(City.name == city_name, City.country_id == country.id)
    )
    city = r.scalar_one_or_none()
    if city is None:
        try:
            timezone_str = tf.timezone_at(lng=float(lon), lat=float(lat))

            clat, clon = Nominatim(user_agent="api.luftdaten.at", domain="nominatim.dataplexity.eu", scheme="https").geocode(city_name)[1]
            city = City(name=city_name, country_id=country.id, tz=timezone_str, lat=clat, lon=clon)
            db.add(city)
            await db.commit()
            logging.debug(f"Neue Stadt erstellt: {city}")

            cache = get_cities_cache()
            cache.invalidate("cities_all")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen der Stadt '{city_name}': {e}")
            await db.rollback()
            raise

    if location:
        logging.debug(f"Aktualisiere bestehende Location mit ID {location.id}")
        location.city_id = city.id
        location.country_id = country.id
        try:
            await db.commit()
            logging.debug(f"Location aktualisiert: {location}")
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Location: {e}")
            await db.rollback()
            raise
    else:
        try:
            location = Location(
                lat=lat,
                lon=lon,
                height=height,
                city_id=city.id,
                country_id=country.id
            )
            db.add(location)
            await db.commit()
            logging.debug(f"Neue Location erstellt: {location}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen der Location: {e}")
            await db.rollback()
            raise

    return location


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
