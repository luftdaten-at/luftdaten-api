import requests
import json
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder
from sqlalchemy.orm import Session
from fastapi import HTTPException
from itertools import groupby
from models import City, Country, Location, Station
import logging
from schemas import StationDataCreate

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

            clat, clon = Nominatim(user_agent="api.luftdaten.at").geocode(city_name)[1]
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

def get_or_create_station(db: Session, station: StationDataCreate):
    # Prüfen, ob die Station bereits existiert
    db_station = db.query(Station).filter(Station.device == station.device).first()

    if db_station is None:
        # Neue Station und neue Location anlegen
        new_location = Location(
            lat=station.location.lat,
            lon=station.location.lon,
            height=float(station.location.height)
        )
        db.add(new_location)
        db.commit()
        db.refresh(new_location)

        # Neue Station anlegen und das source-Feld überprüfen (Standardwert ist 1)
        db_station = Station(
            device=station.device,
            firmware=station.firmware,
            apikey=station.apikey,
            location_id=new_location.id,
            last_active=station.time,
            source=station.source if station.source is not None else 1
        )
        db.add(db_station)
        db.commit()
        db.refresh(db_station)
    else:
        # Station existiert, API-Schlüssel überprüfen
        if db_station.apikey != station.apikey:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        updated = False

        # Überprüfen, ob Location aktualisiert werden muss
        if db_station.location is None or (
            db_station.location.lat != station.location.lat or 
            db_station.location.lon != station.location.lon or
            db_station.location.height != float(station.location.height)
        ):
            new_location = get_or_create_location(db, station.location.lat, station.location.lon, float(station.location.height))
            db_station.location_id = new_location.id
            updated = True

        if db_station.firmware != station.firmware:
            db_station.firmware = station.firmware
            updated = True

        if updated:
            db.commit()

    return db_station

def standard_output_to_csv(data) -> str:
    """
    data: list[(
                Station.device,
                Measurement.time_measured,
                Values.dimension,
                Values.value
           )]
    ret: str -> csv: device,time_measured,dimension,value\n
    """

    csv_data = "device,time_measured,dimension,value\n"
    for device, time, dim, val in data:
        csv_data += f"{device},{time.strftime("%Y-%m-%dT%H:%M")},{dim},{val}\n"
    return csv_data

def standard_output_to_json(data):
    """
    data: list[(
                Station.device,
                Measurement.time_measured,
                Values.dimension,
                Values.value
           )]
    ret: str -> json example:
    [
        {
                "device": "75509",
                "time_measured": "2024-11-29T08:18",
                "values": [
                {
                    "dimension": 7,
                    "value": 28.32
                }
        },
    ]
    """

    groups = groupby(data, lambda x: (x[0], x[1]))
    json_data = [
        {
            "device": device,
            "time_measured": time.strftime("%Y-%m-%dT%H:%M"),
            "values": [
                {
                    "dimension": dim,
                    "value": val
                } 
                for (_, _, dim, val) in data
            ]
        }
        for ((device, time), data) in groups
    ]

    return json.dumps(json_data)


def float_default(x, default = None):
    '''
    trys to convert x to float
    if not possible returns default
    '''
    try:
        return float(x)
    except:
        return default
