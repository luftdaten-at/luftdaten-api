import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from models import Station, Measurement, Values, Location
from datetime import datetime, timezone
from utils import get_or_create_location, float_default, as_naive_utc, max_as_naive_utc
from enums import Dimension, SensorModel


async def sensor_community_import_grouped_by_location(db: AsyncSession, data: dict, source: int):
    for row in data:
        if row['location']['country'] != 'AT':
            continue

        lat = float_default(row['location']['latitude'])
        lon = float_default(row['location']['longitude'])
        height = float_default(row['location']['altitude'])

        loc = await get_or_create_location(db, lat, lon, height)

        r = await db.execute(select(Station).where(Station.location_id == loc.id))
        station = r.scalar_one_or_none()

        # Feed uses ``YYYY-MM-DD HH:MM:SS`` with no offset; values align with server UTC (see Sensor.Community / feinstaub-api).
        naive_utc_wall = datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S")
        timestamp = as_naive_utc(naive_utc_wall.replace(tzinfo=timezone.utc))

        if not station:
            station = Station(
                device=f'{loc.id}SC',
                firmware=None,
                apikey=None,
                location_id=loc.id,
                last_active=timestamp,
                source=source
            )

        station.last_active = max_as_naive_utc(station.last_active, timestamp)

        db.add(station)
        await db.commit()

        sensor_model = {v: k for k, v in SensorModel._names.items()}.get(row["sensor"]["sensor_type"]["name"], None)

        r = await db.execute(
            select(Measurement).where(
                Measurement.station_id == station.id,
                Measurement.time_measured == station.last_active,
                Measurement.sensor_model == sensor_model
            )
        )
        measurement = r.scalar_one_or_none()

        if not measurement:
            measurement = Measurement(
                sensor_model=sensor_model,
                station_id=station.id,
                time_measured=station.last_active,
                time_received=as_naive_utc(datetime.now(tz=timezone.utc)),
                location_id=loc.id
            )
            db.add(measurement)
            await db.flush()

            for val in row['sensordatavalues']:
                d = Dimension.get_dimension_from_sensor_community_name_import(val['value_type'])
                v = float_default(val['value'])
                if d is None or v is None:
                    continue
                value = Values(
                    dimension=d,
                    value=v,
                    measurement_id=measurement.id
                )
                db.add(value)
            await db.commit()

    logging.info("Finished import task")


async def process_and_import_data(db: AsyncSession, data, source):
    for entry_index, entry in enumerate(data):
        logging.debug(f"Verarbeite Eintrag {entry_index}: {entry}")

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

            logging.debug(f"Sensor Type: {sensor_type}, Wert: {value}, Typ von Wert: {type(value)}")

            dimension = Dimension.get_dimension_from_sensor_community_name_import(sensor_type)

            logging.debug(f"Dimension für Sensor Type '{sensor_type}': {dimension}")

            if dimension:
                sensor_model = {v: k for k, v in SensorModel._names.items()}.get(entry["sensor"]["sensor_type"]["name"], None)
                if not sensor_model:
                    continue
                sensors.setdefault(str(entry["sensor"]["id"]), {
                    "type": sensor_model,
                    "data": {}
                })

                try:
                    value_converted = float(value)
                    logging.debug(f"Konvertierter Wert: {value_converted}, Typ: {type(value_converted)}")
                except ValueError as e:
                    logging.error(f"Fehler bei der Konvertierung von Wert '{value}' zu float: {e}")
                    continue

                sensors[str(entry["sensor"]["id"])]["data"][str(dimension)] = value_converted

        logging.debug(f"Sensors Data: {sensors}")

        await import_station_data(db, station_data, sensors)


async def import_station_data(db: AsyncSession, station_data, sensors):
    """Generic ingest: ``time`` is normalized with ``as_naive_utc`` (naive = UTC wall clock)."""
    logging.debug(f"Importiere Stationsdaten: {station_data}")
    logging.debug(f"Sensordaten: {sensors}")

    t_raw = station_data["time"]
    if isinstance(t_raw, str):
        t_raw = datetime.fromisoformat(t_raw.replace("Z", "+00:00"))
    measured = as_naive_utc(t_raw)
    station_data = {**station_data, "time": measured}

    time_received = as_naive_utc(datetime.now(timezone.utc))
    logging.debug(f"Zeit des Empfangs: {time_received}")

    r = await db.execute(
        select(Station)
        .where(Station.device == station_data['device'])
        .options(selectinload(Station.location))
    )
    db_station = r.scalar_one_or_none()
    logging.debug(f"Datenbankstation gefunden: {db_station}")

    if db_station is None:
        logging.debug("Station existiert nicht, erstelle neue Station und Standort.")
        new_location = Location(
            lat=float(station_data['location']['lat']),
            lon=float(station_data['location']['lon']),
            height=float(station_data['location']['height'])
        )
        db.add(new_location)
        await db.flush()
        logging.debug(f"Neue Location erstellt: {new_location}")

        db_station = Station(
            device=station_data['device'],
            firmware=station_data['firmware'],
            apikey=station_data['apikey'],
            location_id=new_location.id,
            last_active=station_data['time'],
            source=station_data.get('source', 1)
        )
        db.add(db_station)
        await db.commit()
        logging.debug(f"Neue Station erstellt: {db_station}")
    else:
        logging.debug("Station existiert bereits, prüfe auf Aktualisierungen.")
        if db_station.apikey != station_data['apikey']:
            logging.error("Ungültiger API-Schlüssel.")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        updated = False

        if db_station.location is None or (
            db_station.location.lat != station_data['location']['lat'] or
            db_station.location.lon != station_data['location']['lon'] or
            db_station.location.height != float(station_data['location']['height'])
        ):
            logging.debug("Standort hat sich geändert, aktualisiere Standort.")
            new_location = await get_or_create_location(
                db, station_data['location']['lat'], station_data['location']['lon'],
                float(station_data['location']['height'])
            )
            db_station.location_id = new_location.id
            updated = True

        if db_station.firmware != station_data['firmware']:
            logging.debug("Firmware hat sich geändert, aktualisiere Firmware.")
            db_station.firmware = station_data['firmware']
            updated = True

        if updated:
            await db.commit()
            logging.debug("Station wurde aktualisiert.")

    for sensor_id, sensor_data in sensors.items():
        logging.debug(f"Verarbeite Sensor-ID: {sensor_id}, Sensordaten: {sensor_data}")

        r = await db.execute(
            select(Measurement).where(
                Measurement.station_id == db_station.id,
                Measurement.time_measured == station_data['time'],
                Measurement.sensor_model == sensor_data['type']
            )
        )
        existing_measurement = r.scalar_one_or_none()

        if existing_measurement:
            logging.error("Messung bereits in der Datenbank vorhanden.")
            raise HTTPException(
                status_code=422,
                detail="Measurement already in Database"
            )

        db_measurement = Measurement(
            sensor_model=sensor_data['type'],
            station_id=db_station.id,
            time_measured=station_data['time'],
            time_received=time_received,
            location_id=db_station.location_id
        )
        db.add(db_measurement)
        await db.flush()
        logging.debug(f"Neue Messung erstellt: {db_measurement}")

        for dimension, value in sensor_data['data'].items():
            logging.debug(f"Füge Wert hinzu - Dimension: {dimension}, Wert: {value}, Typ von Wert: {type(value)}")

            db_value = Values(
                dimension=dimension,
                value=value,
                measurement_id=db_measurement.id
            )
            db.add(db_value)

    await db.commit()
    logging.debug("Alle Daten wurden erfolgreich in die Datenbank geschrieben.")

    return {"status": "success"}
