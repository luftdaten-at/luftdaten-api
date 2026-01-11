"""
Geocoding utilities for location management.

This module handles reverse geocoding and location creation/retrieval
using Nominatim geocoding service.
"""

from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from sqlalchemy.orm import Session
from models import City, Country, Location
import logging

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


def get_or_create_location(db: Session, lat: float, lon: float, height: float):
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
    location = db.query(Location).filter_by(lat=lat, lon=lon, height=height).first()

    if location:
        # Check if location already has city and country
        if location.city and location.country:
            return location

    # Perform reverse geocoding (only if location doesn't exist or city/country are missing)
    try:
        city_name, country_name, country_code = reverse_geocode(lat, lon)
    except Exception as e:
        logging.error(f"Fehler bei reverse_geocode: {e}")
        raise

    # Check if country already exists in database
    country = db.query(Country).filter_by(name=country_name).first()
    if country is None:
        try:
            country = Country(name=country_name, code=country_code)
            db.add(country)
            db.commit()
            db.refresh(country)
            logging.debug(f"Neues Land erstellt: {country}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen des Landes '{country_name}': {e}")
            db.rollback()
            raise

    # Check if city already exists in database
    city = db.query(City).filter_by(name=city_name, country_id=country.id).first()
    if city is None:
        try:
            timezone_str = tf.timezone_at(lng=float(lon), lat=float(lat))

            clat, clon = Nominatim(user_agent="api.luftdaten.at", domain="nominatim.dataplexity.eu", scheme="https").geocode(city_name)[1]
            city = City(name=city_name, country_id=country.id, tz=timezone_str, lat=clat, lon=clon)
            db.add(city)
            db.commit()
            db.refresh(city)
            logging.debug(f"Neue Stadt erstellt: {city}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen der Stadt '{city_name}': {e}")
            db.rollback()
            raise

    if location:
        # Update existing location with city and country
        logging.debug(f"Aktualisiere bestehende Location mit ID {location.id}")
        location.city_id = city.id
        location.country_id = country.id
        try:
            db.commit()
            logging.debug(f"Location aktualisiert: {location}")
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Location: {e}")
            db.rollback()
            raise
    else:
        # Create new location since it doesn't exist
        try:
            location = Location(
                lat=lat,
                lon=lon,
                height=height,
                city_id=city.id,
                country_id=country.id
            )
            db.add(location)
            db.commit()
            db.refresh(location)
            logging.debug(f"Neue Location erstellt: {location}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen der Location: {e}")
            db.rollback()
            raise

    return location
