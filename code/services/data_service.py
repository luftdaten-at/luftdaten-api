import logging  # Importieren des Logging-Moduls
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Station, Measurement, Values, Location
from datetime import datetime, timezone
from utils import get_or_create_location, float_default
from enums import Dimension, SensorModel


def sensor_community_import_grouped_by_location(db: Session, data: dict, source: int):
    for row in data:
        # skip if not in austria
        if row['location']['country'] != 'AT':
            continue

        lat = float_default(row['location']['latitude'])
        lon = float_default(row['location']['longitude'])
        height = float_default(row['location']['altitude'])

        # find location
        loc = get_or_create_location(db, lat, lon, height)
        
        # find station based on location
        station = db.query(Station).filter(
            Station.location == loc
        ).first()

        timestamp = datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

        # create if not exists
        if not station:
            # create station
            station = Station(
                # take sensor id as device name
                device = f'{loc.id}SC',
                firmware = None,
                apikey = None,
                location_id = loc.id,
                last_active = timestamp,
                source = source
            )

        # update last_active
        station.last_active = max(station.last_active.replace(tzinfo=timezone.utc), timestamp)

        db.add(station)
        db.commit()
        db.refresh(station)

        sensor_model = {v:k for k,v in SensorModel._names.items()}.get(row["sensor"]["sensor_type"]["name"], None)

        # add measurements
        measurement = db.query(Measurement).filter(
            Measurement.station_id == station.id,
            Measurement.time_measured == station.last_active,
            Measurement.sensor_model == sensor_model
        ).first()


        if not measurement:
            measurement = Measurement(
                sensor_model = sensor_model,
                station_id = station.id,
                time_measured = station.last_active,
                time_received = datetime.now(tz=timezone.utc),
                location_id = loc.id
            )
            db.add(measurement)
            db.commit()
            db.refresh(measurement)

            # only add values if the measurement is not yet present
            for val in row['sensordatavalues']:
                d = Dimension.get_dimension_from_sensor_community_name_import(val['value_type'])
                v = float_default(val['value'])
                if d is None or v is None:
                    continue
                value = Values(
                    dimension = d,
                    value = v,
                    measurement_id = measurement.id
                )
                db.add(value)
            db.commit()

    logging.info(f"Finished import task")

def process_and_import_data(db: Session, data, source):
    for entry_index, entry in enumerate(data):
        logging.debug(f"Verarbeite Eintrag {entry_index}: {entry}")

        # Filtere nur die Einträge mit dem Land "AT" (Österreich)
        country = entry["location"].get("country")
        if country != "AT":
             logging.debug("Eintrag nicht aus Österreich, wird übersprungen.")
             continue

        station_data = {
            "device": str(entry["sensor"]["id"]),
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
        for sensordata_index, sensordata in enumerate(entry["sensordatavalues"]):
            logging.debug(f"Verarbeite Sensordaten {sensordata_index}: {sensordata}")
            sensor_type = sensordata["value_type"]
            value = sensordata["value"]

            # Geben Sie den Typ und Wert von 'value' aus
            logging.debug(f"Sensor Type: {sensor_type}, Wert: {value}, Typ von Wert: {type(value)}")

            # Dimension Mapping (wie vorher gezeigt)
            dimension = Dimension.get_dimension_from_sensor_community_name_import(sensor_type)

            logging.debug(f"Dimension für Sensor Type '{sensor_type}': {dimension}")

            if dimension:
                sensor_model = {v:k for k,v in SensorModel._names.items()}.get(entry["sensor"]["sensor_type"]["name"], None)
                if not sensor_model:
                    continue
                sensors.setdefault(str(entry["sensor"]["id"]), {
                    # TODO: take name and translate to ID
                    "type": sensor_model,
                    "data": {}
                })

                # Konvertieren Sie 'value' zu float und loggen Sie den neuen Typ
                try:
                    value_converted = float(value)
                    logging.debug(f"Konvertierter Wert: {value_converted}, Typ: {type(value_converted)}")
                except ValueError as e:
                    logging.error(f"Fehler bei der Konvertierung von Wert '{value}' zu float: {e}")
                    continue  # Überspringen Sie diesen Wert, wenn die Konvertierung fehlschlägt

                sensors[str(entry["sensor"]["id"])]["data"][str(dimension)] = value_converted

        logging.debug(f"Sensors Data: {sensors}")

        # Speichere Daten in der Datenbank
        import_station_data(db, station_data, sensors)

def import_station_data(db: Session, station_data, sensors):
    logging.debug(f"Importiere Stationsdaten: {station_data}")
    logging.debug(f"Sensordaten: {sensors}")

    # Empfangszeit des Requests erfassen
    time_received = datetime.now(timezone.utc)
    logging.debug(f"Zeit des Empfangs: {time_received}")

    # Prüfen, ob die Station bereits existiert
    db_station = db.query(Station).filter(Station.device == station_data['device']).first()
    logging.debug(f"Datenbankstation gefunden: {db_station}")

    if db_station is None:
        logging.debug("Station existiert nicht, erstelle neue Station und Standort.")
        # Neue Station und neue Location anlegen
        new_location = Location(
            lat=float(station_data['location']['lat']),
            lon=float(station_data['location']['lon']),
            height=float(station_data['location']['height'])
        )
        db.add(new_location)
        db.commit()
        db.refresh(new_location)
        logging.debug(f"Neue Location erstellt: {new_location}")

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
        logging.debug(f"Neue Station erstellt: {db_station}")
    else:
        logging.debug("Station existiert bereits, prüfe auf Aktualisierungen.")
        # Station existiert, API-Schlüssel überprüfen
        if db_station.apikey != station_data['apikey']:
            logging.error("Ungültiger API-Schlüssel.")
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
            logging.debug("Standort hat sich geändert, aktualisiere Standort.")
            new_location = get_or_create_location(db, station_data['location']['lat'], station_data['location']['lon'], float(station_data['location']['height']))
            db_station.location_id = new_location.id
            updated = True

        if db_station.firmware != station_data['firmware']:
            logging.debug("Firmware hat sich geändert, aktualisiere Firmware.")
            db_station.firmware = station_data['firmware']
            updated = True

        if updated:
            db.commit()
            logging.debug("Station wurde aktualisiert.")

    # Durch alle Sensoren iterieren
    for sensor_id, sensor_data in sensors.items():
        logging.debug(f"Verarbeite Sensor-ID: {sensor_id}, Sensordaten: {sensor_data}")

        # Prüfen, ob bereits eine Messung mit dem gleichen time_measured und sensor_model existiert
        existing_measurement = db.query(Measurement).filter(
            Measurement.station_id == db_station.id,
            Measurement.time_measured == station_data['time'],
            Measurement.sensor_model == sensor_data['type']
        ).first()

        if existing_measurement:
            logging.error("Messung bereits in der Datenbank vorhanden.")
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
        logging.debug(f"Neue Messung erstellt: {db_measurement}")

        # Werte (dimension, value) für die Messung hinzufügen
        for dimension, value in sensor_data['data'].items():
            logging.debug(f"Füge Wert hinzu - Dimension: {dimension}, Wert: {value}, Typ von Wert: {type(value)}")

            db_value = Values(
                dimension=dimension,
                value=value,
                measurement_id=db_measurement.id
            )
            db.add(db_value)

    db.commit()
    logging.debug("Alle Daten wurden erfolgreich in die Datenbank geschrieben.")

    return {"status": "success"}
