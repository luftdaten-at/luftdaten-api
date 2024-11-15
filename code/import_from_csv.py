import io
import pandas as pd
from database import get_db
from models import *

def import_sensor_community_archive_from_csv(csv: str):
    """
    sensor_id;sensor_type;location;lat;lon;timestamp;pressure;altitude;pressure_sealevel;temperature
    """
    db = next(get_db())
    df = pd.read_csv(io.BytesIO(csv.encode()), encoding='utf8', sep=";")

    station_id_map = {
        t.device: t
        for t in
        db.query(Station)
        .filter(Station.source == 3)
        .all()
    }

    print(station_id_map.keys())

    for row in df.iterrows():
        # check if sensor_id in database
        idx, data = row
        station_id = data['sensor_id']
        time_measured = data['timestamp']
        sensor_model = data['sensor_type']

        #print(station_id in station_id_map)

        if station_id not in station_id_map or sensor_model not in SensorModel._names.values():
            continue

        sensor_model = {v: k for k, v in SensorModel._names.items()}[sensor_model]

        m = (
            db.query(Measurement)
            .filter(
                Measurement.station_id == station_id,
                Measurement.time_measured == time_measured,
                Measurement.sensor_model == sensor_model
            )
            .first()
        )

        if m:
            continue

        db_measurement = Measurement(
            sensor_model=sensor_model,
            station_id=station_id,
            time_measured=time_measured,
            time_received=None,
            location_id=station_id_map[station_id].location_id
        )

        print(f'Import measurment: {db_measurement}')

        db.add(db_measurement)
        db.commit()
        db.refresh(db_measurement)

        for dim_name, val in data.item()[6:]:
            dim = Dimension.get_dimension_from_sensor_community_name(dim_name)
            if not dim:
                continue
            db_value = Values(
                dimension=dim,
                value=val,
                measurement_id=db_measurement.id
            )
            print(f'Import Value: {db_value}')
            db.add(db_value)

        db.commit()