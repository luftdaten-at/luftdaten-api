import io
import pandas as pd
import os
from tqdm import tqdm
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import create_engine
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from models import *
from enums import SensorModel, Dimension
from utils import float_default


DOWNLOAD_FOLDER = "sensor_community_archive/csv"
LOG_FILE = "sensor_community_archive/log.txt"
PROGRESS_FILE = "sensor_community_archive/progress.txt"

log_file = None

# INIT DB
# Umgebungsvariablen auslesen
DB_USER = os.getenv("POSTGRES_USER", "")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "")
DB_NAME = os.getenv("POSTGRES_DB", "")

# Erstellen der korrekten DATABASE_URL mit f-String
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}"
engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

# GLOBALS to reduce queries
location_to_device = {}
sensor_model_name_to_num = {v.lower(): k for k, v in SensorModel._names.items()}


def log(*l):
    """
    simple logging 
    """
    print(' '.join(str(x) for x in l), file=log_file)


def import_sensor_community_archive_from_csv(csv_file_path: str):
    """
    sensor_id;sensor_type;location;lat;lon;timestamp;pressure;altitude;pressure_sealevel;temperature
    """
    df = pd.read_csv(csv_file_path, sep=";")

    out_file_measurements = open(f'{csv_file_path}_measurements_out.sql', 'w')
    out_file_values = open(f'{csv_file_path}_values_out.sql', 'w')

    current_measurement_id = 1
    current_value_id = 1

    for row in df.iterrows():
        # check if sensor_id in databaseflo
        idx, data = row

        time_measured = datetime.fromisoformat(data['timestamp'])
        sensor_model = sensor_model_name_to_num.get(data['sensor_type'].lower(), None)
        lat = float(data['lat'])
        lon = float(data['lon'])

        if (lat, lon) not in location_to_device or sensor_model is None:
            return
        
        station_id, loc_id = location_to_device[lat, lon]

        # create measurement
        time_received = datetime.now(tz=timezone.utc)

        measurement = '\t'.join(str(x) for x in [
            current_measurement_id, 
            time_received.strftime("%Y-%m-%d %H:%M:%S.%f"),
            time_measured.strftime("%Y-%m-%d %H:%M:%S.%f"),
            sensor_model,
            loc_id,
            station_id
        ])

        print(measurement, file = out_file_measurements)

        current_measurement_id += 1

        # create values
        for key in data.keys()[6:]:
            d = Dimension.get_dimension_from_sensor_community_name_import(key)
            v = float_default(data[key])
            if d is None or v is None:
                continue
                
            value = '\t'.join(str(x) for x in [
                current_value_id,
                d,
                v,
                current_measurement_id - 1,
                r'\N'
            ])
            current_value_id += 1

            print(value, file = out_file_values)


# multi thread
def main():
    global location_to_device

    db = db_session()
    data = db.query(Station.id, Location.id, Location.lat, Location.lon).join(Location).all()
    for p in data:
        location_to_device[p[2:]] = p[:2]

    # List all files in the download folder
    files = [
        os.path.join(DOWNLOAD_FOLDER, filename)
        for filename in os.listdir(DOWNLOAD_FOLDER)
        if os.path.isfile(os.path.join(DOWNLOAD_FOLDER, filename))
    ]

    # Progress tracking with tqdm
    with open(PROGRESS_FILE, "w") as progress_file:
        with tqdm(total=len(files), desc="Import CSV files", unit="Files", file=progress_file) as pbar:
            # ThreadPoolExecutor for parallel processing
            with ThreadPoolExecutor() as executor:
                # Define a function to update the progress bar after each task
                def process_file(file_path):
                    import_sensor_community_archive_from_csv(file_path)
                    pbar.update(1)

                # Submit all tasks to the executor
                for file_path in files:
                    executor.submit(process_file, file_path)


if __name__ == "__main__":
    log_file = open(LOG_FILE, 'w')
    main()
    log_file.close()