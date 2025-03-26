-- Drop and recreate tmp_measurement table
DROP TABLE IF EXISTS tmp_measurement;
CREATE TEMP TABLE tmp_measurement (
    id SERIAL PRIMARY KEY,
    time_received timestamp without time zone,
    time_measured timestamp without time zone,
    sensor_model INT,
    loc_id INT,
    station_id INT
);

-- Import data into tmp_measurement table
COPY tmp_measurement (id, time_received, time_measured, sensor_model, loc_id, station_id)
FROM '/sql/all_measurements.csv'
WITH (FORMAT csv, DELIMITER E'\t', HEADER false);


-- add a temp column
ALTER TABLE measurements
ADD COLUMN old_id INT;

-- Insert the measurements and capture the returning ids
INSERT INTO measurements (time_received, time_measured, sensor_model, location_id, station_id, old_id)
SELECT time_received, time_measured, sensor_model, loc_id, station_id, id
FROM tmp_measurement;


-- Drop and recreate tmp_values table with foreign key constraints
DROP TABLE IF EXISTS tmp_values;
CREATE TEMP TABLE tmp_values (
    id SERIAL PRIMARY KEY,
    dimension INT,
    value double precision,
    measurement_id INT NULL,
    calibration_measurement_id INT NULL
);

-- Import data into tmp_values table
COPY tmp_values (id, dimension, value, measurement_id, calibration_measurement_id)
FROM '/sql/all_values.csv'
WITH (FORMAT csv, DELIMITER E'\t', NULL '\N', HEADER false);


INSERT INTO values (dimension, value, measurement_id, calibration_measurement_id)
SELECT v.dimension, v.value, m.id, v.calibration_measurement_id
FROM tmp_values v
JOIN measurements m ON m.old_id = v.measurement_id;
