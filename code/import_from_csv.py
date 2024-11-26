import io
import pandas as pd
import os
from datetime import datetime
from database import get_db
from models import *
from enums import SensorModel, Dimension


DOWNLOAD_FOLDER = "sensor_community_archive/csv"


def import_sensor_community_archive_from_csv(csv_file_path: str):
    """
    sensor_id;sensor_type;location;lat;lon;timestamp;pressure;altitude;pressure_sealevel;temperature
    """
    db = next(get_db())
    df = pd.read_csv(csv_file_path, encoding='utf8', sep=";")

    for row in df.iterrows():
        # check if sensor_id in database
        idx, data = row
        device = str(data['sensor_id'])
        time_measured = datetime.fromisoformat(data['timestamp'])
        sensor_model = {v: k for k, v in SensorModel._names.items()}.get(data['sensor_type'], None)
        db_station = db.query(Station).filter(Station.device == device).first()

        if not db_station or not sensor_model:
            continue

        m = (
            db.query(Measurement)
            .filter(
                Measurement.station_id == db_station.id,
                Measurement.time_measured == time_measured,
                Measurement.sensor_model == sensor_model
            )
            .first()
        )

        # if measurement is already present skip
        if m:
            continue

        db_measurement = Measurement(
            sensor_model=sensor_model,
            station_id=db_station.id,
            time_measured=time_measured,
            time_received=None,
            location_id=db_station.location_id
        )

        db.add(db_measurement)
        db.commit()
        db.refresh(db_measurement)

        for dim_name, val in list(data.items())[6:]:
            dim = Dimension.get_dimension_from_sensor_community_name(dim_name)
            try:
                val = float(val)
            except ValueError:
                print(f"Value is not a float: {val}")
                continue
            if not dim:
                continue
            if val == float('nan'):
                continue

            db_value = Values(
                dimension=dim,
                value=float(val),
                measurement_id=db_measurement.id
            )
            db.add(db_value)

        db.commit()


def main():
    # List all files in the download folder and process them
    for filename in os.listdir(DOWNLOAD_FOLDER):
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        
        # Ensure it's a file (not a directory)
        if os.path.isfile(file_path):
            # Read the file content as a string
            import_sensor_community_archive_from_csv(file_path)


if __name__ == "__main__":
    main()
