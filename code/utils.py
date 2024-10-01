import requests
from geopy.geocoders import Nominatim
from sqlalchemy.orm import Session
from models import City, Country, Location


# Funktion für CSV Loading
def download_csv(url: str):
    response = requests.get(url)
    response.raise_for_status()
    return response.text

# Funktion für Reverse Geocoding
def reverse_geocode(lat, lon):
    geolocator = Nominatim(user_agent="your_app_name")
    location = geolocator.reverse((lat, lon), exactly_one=True)
    
    if location and 'address' in location.raw:
        address = location.raw['address']
        city = address.get('city', None) or address.get('town', None) or address.get('village', None)
        country = address.get('country', None)
        country_code = address.get('country_code', None)
        return city, country, country_code
    
    return None, None, None

# Funktion, um eine Location zu erstellen oder eine vorhandene zu verwenden
def get_or_create_location(db: Session, lat: float, lon: float, height: float):
    # Geocoding durchführen, um Stadt und Land zu erhalten
    city_name, country_name, country_code = reverse_geocode(lat, lon)

    # Überprüfe, ob das Land bereits in der Datenbank existiert
    country = db.query(Country).filter_by(name=country_name).first()
    if country is None:
        # Neues Land anlegen, wenn es noch nicht existiert
        country = Country(name=country_name, code=country_code)
        db.add(country)
        db.commit()
        db.refresh(country)

    # Überprüfe, ob die Stadt bereits in der Datenbank existiert
    city = db.query(City).filter_by(name=city_name, country_id=country.id).first()
    if city is None:
        # Neue Stadt anlegen, wenn sie noch nicht existiert
        city = City(name=city_name, country_id=country.id)
        db.add(city)
        db.commit()
        db.refresh(city)

    # Überprüfe, ob die Location bereits in der Datenbank existiert
    location = db.query(Location).filter_by(lat=lat, lon=lon, height=height, city_id=city.id, country_id=country.id).first()
    if location is None:
        # Neue Location anlegen, wenn sie noch nicht existiert
        location = Location(lat=lat, lon=lon, height=height, city_id=city.id, country_id=country.id)
        db.add(location)
        db.commit()
        db.refresh(location)

    return location