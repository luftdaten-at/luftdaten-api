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

DROP TABLE IF EXISTS id_mapping;
CREATE TEMP TABLE id_mapping (
    old_id INT,
    new_id INT
);

-- Insert the measurements and capture the returning ids
WITH id_mapping AS (
    INSERT INTO measurements (time_received, time_measured, sensor_model, location_id, station_id)
    SELECT time_received, time_measured, sensor_model, loc_id, station_id
    FROM tmp_measurement
    RETURNING id AS new_id, tmp_measurement.id AS old_id
)

-- Now insert the results from the WITH clause into the id_mapping table
INSERT INTO id_mapping (new_id, old_id)
SELECT new_id, old_id
FROM id_mapping;


-- not working
/*
INSERT INTO measurements (time_received, time_measured, sensor_model, loc_id, station_id)
SELECT time_received, time_measured, sensor_model, loc_id, station_id
FROM tmp_measurement
RETURNING id AS new_id, old_id;
*/


-- Drop and recreate tmp_values table with foreign key constraints
DROP TABLE IF EXISTS tmp_values;

CREATE TEMP TABLE tmp_values (
    id SERIAL PRIMARY KEY,
    dimension INT,
    value double precision,
    measurement_id INT NULL,
    calibration_measurement_id INT NULL,
    CONSTRAINT fk_measurement_id FOREIGN KEY (measurement_id) REFERENCES tmp_measurement(id) ON DELETE SET NULL,
    CONSTRAINT fk_calibration_measurement_id FOREIGN KEY (calibration_measurement_id) REFERENCES tmp_measurement(id) ON DELETE SET NULL
);

-- Import data into tmp_values table
COPY tmp_values (id, dimension, value, measurement_id, calibration_measurement_id)
FROM '/sql/all_values.csv'
WITH (FORMAT csv, DELIMITER E'\t', NULL '\N', HEADER false);


INSERT INTO values (dimension, value, measurement_id, calibration_measurement_id)
SELECT v.dimension, v.value, m.new_id, v.calibration_measurement_id
FROM tmp_values v
JOIN id_mapping m ON v.measurement_id = m.old_id;
