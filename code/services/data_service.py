from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Station, Measurement, Values, Location
from datetime import datetime
from utils import get_or_create_location

async def process_and_import_data(db: Session, data, source):
    for entry in data:
        # Filtere nur die Einträge mit dem Land "AT" (Österreich)
        if entry["location"].get("country") != "AT":
            continue

        station_data = {
            "device": entry["sensor"]["id"],
            "location": {
                "lat": entry["location"]["latitude"],
                "lon": entry["location"]["longitude"],
                "height": entry["location"]["altitude"]
            },
            "time": entry["timestamp"],
            "firmware": None,
            "apikey": None,
            "source": source
        }

        sensors = {}
        for sensordata in entry["sensordatavalues"]:
            sensor_type = sensordata["value_type"]
            value = sensordata["value"]

            # Dimension Mapping (wie vorher gezeigt)
            dimension = None
            if sensor_type == "temperature":
                dimension = 7  # Beispiel: Temperatur
            elif sensor_type == "humidity":
                dimension = 6  # Beispiel: Luftfeuchtigkeit
            elif sensor_type == "P0":
                dimension = 2  # Beispiel: PM1
            elif sensor_type == "P1":
                dimension = 5  # Beispiel: PM10
            elif sensor_type == "P2":
                dimension = 3  # Beispiel: PM2.5
            elif sensor_type == "P4":
                dimension = 4  # Beispiel: PM4
            elif sensor_type == "pressure":
                dimension = 8  # Beispiel: Druck

            if dimension:
                sensors.setdefault(str(entry["sensor"]["id"]), {
                    "type": entry["sensor"]["sensor_type"]["id"],
                    "data": {}
                })
                sensors[str(entry["sensor"]["id"])]["data"][str(dimension)] = value

        # Speichere Daten in der Datenbank
        await import_station_data(db, station_data, sensors)

async def import_station_data(db: Session, station_data, sensors):
    """
    Funktion zum Importieren von Stations- und Sensordaten in die Datenbank.
    :param db: Die Datenbanksession.
    :param station_data: Die Stationsdaten (z.B. Gerät, Firmware, Standort).
    :param sensors: Die Sensordaten, die mit der Station verknüpft sind.
    """

    # Empfangszeit des Requests erfassen
    time_received = datetime.now()

    # Prüfen, ob die Station bereits existiert
    db_station = db.query(Station).filter(Station.device == station_data['device']).first()

    if db_station is None:
        # Neue Station und neue Location anlegen
        new_location = Location(
            lat=station_data['location']['lat'],
            lon=station_data['location']['lon'],
            height=float(station_data['location']['height'])
        )
        db.add(new_location)
        db.commit()
        db.refresh(new_location)

        # Neue Station anlegen
        db_station = Station(
            device=station_data['device'],
            firmware=station_data['firmware'],
            apikey=station_data['apikey'],
            location_id=new_location.id,
            last_active=station_data['time'],
            source=station_data.get('source', 1)  # Verwende den Standardwert 1, wenn 'source' nicht vorhanden ist
        )
        db.add(db_station)
        db.commit()
        db.refresh(db_station)
    else:
        # Station existiert, API-Schlüssel überprüfen
        if db_station.apikey != station_data['apikey']:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        updated = False

        # Überprüfen, ob Location aktualisiert werden muss
        if db_station.location is None or (
            db_station.location.lat != station_data['location']['lat'] or 
            db_station.location.lon != station_data['location']['lon'] or
            db_station.location.height != float(station_data['location']['height'])
        ):
            new_location = get_or_create_location(db, station_data['location']['lat'], station_data['location']['lon'], float(station_data['location']['height']))
            db_station.location_id = new_location.id
            updated = True

        if db_station.firmware != station_data['firmware']:
            db_station.firmware = station_data['firmware']
            updated = True

        if updated:
            db.commit()

    # Durch alle Sensoren iterieren
    for sensor_id, sensor_data in sensors.items():
        # Prüfen, ob bereits eine Messung mit dem gleichen time_measured und sensor_model existiert
        existing_measurement = db.query(Measurement).filter(
            Measurement.station_id == db_station.id,
            Measurement.time_measured == station_data['time'],
            Measurement.sensor_model == sensor_data['type']
        ).first()

        if existing_measurement:
            raise HTTPException(
                status_code=422,
                detail="Measurement already in Database"
            )

        # Wenn keine bestehende Messung gefunden wurde, füge eine neue hinzu
        db_measurement = Measurement(
            sensor_model=sensor_data['type'],
            station_id=db_station.id,
            time_measured=station_data['time'],
            time_received=time_received,
            location_id=db_station.location_id  # Verknüpfe die Messung mit der neuen Location
        )
        db.add(db_measurement)
        db.commit()
        db.refresh(db_measurement)

        # Werte (dimension, value) für die Messung hinzufügen
        for dimension, value in sensor_data['data'].items():
            db_value = Values(
                dimension=dimension,
                value=value,
                measurement_id=db_measurement.id
            )
            db.add(db_value)

    db.commit()

    return {"status": "success"}