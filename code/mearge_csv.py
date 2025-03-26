'''
lists all the sql files with out in the name
mearges them into 1 file

this is a pair
2024-11-28_sps30_sensor_86760.csv_measurements_out.sql
(id, time_received, time_measured, sensor_model, loc_id, station_id)

2024-11-28_sps30_sensor_86760.csv_values_out.sql
(id, dimension, value, measurement_id, calibration_measurement_id)
'''

import os
from collections import defaultdict
from tqdm import tqdm

DOWNLOAD_FOLDER = "sensor_community_archive/csv"
ALL_MEASUREMENTS = "sensor_community_archive/csv/all_measurements.csv"
ALL_VALUES = "sensor_community_archive/csv/all_values.csv"
PROGRESS_FILE = "sensor_community_archive/progress.txt"

def main():
    pairs = defaultdict(list)

    for file_name in os.listdir(DOWNLOAD_FOLDER):
        if 'out' in file_name and len(file_name.split('.')) == 3:
            pairs[file_name.split('.')[0]].append(os.path.join(DOWNLOAD_FOLDER, file_name))

    l = []
    for k, v in pairs.items():
        assert len(v) == 2
        l.append(tuple(sorted(v)))

    measurements_file = open(ALL_MEASUREMENTS, 'w')
    values_file = open(ALL_VALUES, 'w')

    measurement_pk_offset = 0
    value_pk_offset = 0

    for m, v in tqdm(l, file=open(PROGRESS_FILE, 'w')):
        max_measurement_pk = 0
        max_value_pk = 0
        for row in open(m, 'r'):
            idx, *rest = row.strip().split('\t')

            max_measurement_pk = max(max_measurement_pk, int(idx))

            idx = int(idx) + measurement_pk_offset
            print('\t'.join([str(idx)] + rest), file=measurements_file)
        
        for row in open(v, 'r'):
            data = row.strip().split('\t')

            max_value_pk = max(max_value_pk, int(data[0]))

            data[0] = str(int(data[0]) + value_pk_offset)
            data[3] = str(int(data[3]) + measurement_pk_offset)

            print('\t'.join(data), file=values_file)
        
        measurement_pk_offset += max_measurement_pk
        value_pk_offset += max_value_pk
