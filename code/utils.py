import requests
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from sqlalchemy.orm import Session
from models import City, Country, Location
import logging

# Initialisiere TimezoneFinder
tf = TimezoneFinder()

# Funktion für CSV Loading
def download_csv(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

# Funktion für Reverse Geocoding
def reverse_geocode(lat, lon):
    geolocator = Nominatim(user_agent="api.luftdaten.at")
    location = geolocator.reverse((lat, lon), exactly_one=True)
    
    if location and 'address' in location.raw:
        address = location.raw['address']
        city = address.get('city', None) or address.get('town', None) or address.get('village', None)
        country = address.get('country', None)
        country_code = address.get('country_code', None)
        return city, country, country_code
    
    return None, None, None

def get_or_create_location(db: Session, lat: float, lon: float, height: float):
    location = db.query(Location).filter_by(lat=lat, lon=lon, height=height).first()

    if location:
        # Überprüfen, ob die zugehörige Stadt und das Land vorhanden sind
        if location.city and location.country:
            logging.debug(f"Location hat bereits Stadt ({location.city.name}) und Land ({location.country.name}).")
            return location

    # Reverse Geocoding durchführen (nur wenn Location nicht existiert oder Stadt/Land fehlen)
    try:
        city_name, country_name, country_code = reverse_geocode(lat, lon)
    except Exception as e:
        logging.error(f"Fehler bei reverse_geocode: {e}")
        raise

    # Überprüfe, ob das Land bereits in der Datenbank existiert
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

    # Überprüfe, ob die Stadt bereits in der Datenbank existiert
    city = db.query(City).filter_by(name=city_name, country_id=country.id).first()
    if city is None:
        try:
            timezone_str = tf.timezone_at(lng=float(lon), lat=float(lat))
            city = City(name=city_name, country_id=country.id, tz=timezone_str)
            db.add(city)
            db.commit()
            db.refresh(city)
            logging.debug(f"Neue Stadt erstellt: {city}")
        except Exception as e:
            logging.error(f"Fehler beim Erstellen der Stadt '{city_name}': {e}")
            db.rollback()
            raise

    if location:
        # Aktualisiere die bestehende Location mit Stadt und Land
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
        # Neue Location anlegen, da sie nicht existiert
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