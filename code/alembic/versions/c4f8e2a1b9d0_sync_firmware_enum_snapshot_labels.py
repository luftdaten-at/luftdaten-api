"""Sync statistics_endpoint_snapshot enum labels with firmware sensors

Revision ID: c4f8e2a1b9d0
Revises: b8e4a1c0f2d3
Create Date: 2026-06-04

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c4f8e2a1b9d0"
down_revision: Union[str, None] = "b8e4a1c0f2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Enum label maps kept in sync with code/enums.py (Source, SensorModel, Dimension)
_SNAPSHOT_SELECT = r"""
CREATE MATERIALIZED VIEW statistics_endpoint_snapshot AS
SELECT
    1 AS id,
    jsonb_build_object(
        'totals', jsonb_build_object(
            'countries', (SELECT total_countries FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'cities', (SELECT total_cities FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'locations', (SELECT total_locations FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'stations', (SELECT total_stations FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'measurements', (SELECT total_measurements FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'calibration_measurements', (SELECT total_calibration_measurements FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'values', (SELECT total_values FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'station_statuses', (SELECT total_station_statuses FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1)
        ),
        'active_stations', jsonb_build_object(
            'last_hour', COALESCE((SELECT last_hour FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'last_24_hours', COALESCE((SELECT last_24_hours FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'last_7_days', COALESCE((SELECT last_7_days FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'last_30_days', COALESCE((SELECT last_30_days FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0)
        ),
        'data_coverage', jsonb_build_object(
            'earliest_measurement', to_jsonb((SELECT earliest_measurement FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1)),
            'latest_measurement', to_jsonb((SELECT latest_measurement FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1)),
            'measurements_last_24h', COALESCE((SELECT last_24h FROM measurements_timeframe_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'measurements_last_7d', COALESCE((SELECT last_7d FROM measurements_timeframe_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'measurements_last_30d', COALESCE((SELECT last_30d FROM measurements_timeframe_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0)
        ),
        'distribution', jsonb_build_object(
            'stations_by_source', COALESCE((
                SELECT jsonb_object_agg(src_label, cnt)
                FROM (
                    SELECT
                        CASE source
                            WHEN 1 THEN 'Luftdaten.at'
                            WHEN 2 THEN 'Luftdaten.at TTN LoRaWAN'
                            WHEN 3 THEN 'sensor.community'
                            ELSE 'Unknown'
                        END AS src_label,
                        count AS cnt
                    FROM stations_by_source_summary
                    WHERE count > 0
                ) sbs
            ), '{}'::jsonb),
            'stations_by_country', COALESCE((
                SELECT jsonb_object_agg(country_name, station_count)
                FROM stations_by_country_summary
            ), '{}'::jsonb),
            'top_cities', COALESCE((
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'city', city_name,
                        'country', country_name,
                        'station_count', station_count
                    )
                    ORDER BY station_count DESC
                )
                FROM top_cities_summary
            ), '[]'::jsonb),
            'sensor_models', COALESCE((
                SELECT jsonb_object_agg(
                    CASE sensor_model
                        WHEN 1 THEN 'SEN5X'
                        WHEN 2 THEN 'BMP280'
                        WHEN 3 THEN 'BME280'
                        WHEN 4 THEN 'BME680'
                        WHEN 5 THEN 'SCD4X'
                        WHEN 6 THEN 'AHT20'
                        WHEN 7 THEN 'SHT30'
                        WHEN 8 THEN 'SHT31'
                        WHEN 9 THEN 'AGS02MA'
                        WHEN 10 THEN 'SHT4X'
                        WHEN 11 THEN 'SGP40'
                        WHEN 12 THEN 'DHT22'
                        WHEN 13 THEN 'SDS011'
                        WHEN 14 THEN 'SHT35'
                        WHEN 15 THEN 'SPS30'
                        WHEN 16 THEN 'PMS5003'
                        WHEN 17 THEN 'PMS7003'
                        WHEN 18 THEN 'VIRTUAL_SENSOR'
                        WHEN 19 THEN 'LTR390'
                        WHEN 20 THEN 'BMP388'
                        WHEN 21 THEN 'BMP390'
                        WHEN 22 THEN 'lsm6ds'
                        WHEN 23 THEN 'SEN66'
                        WHEN 24 THEN 'MLX90640'
                        WHEN 25 THEN 'TSL_2591'
                        WHEN 26 THEN 'SEN63C'
                        WHEN 27 THEN 'SEN62'
                        WHEN 28 THEN 'BMP581'
                        WHEN 29 THEN 'SHTC3'
                        ELSE 'Unknown Sensor'
                    END,
                    count
                )
                FROM sensor_models_summary
                WHERE count > 0
            ), '{}'::jsonb),
            'calibration_sensors', COALESCE((
                SELECT jsonb_object_agg(
                    CASE sensor_model
                        WHEN 1 THEN 'SEN5X'
                        WHEN 2 THEN 'BMP280'
                        WHEN 3 THEN 'BME280'
                        WHEN 4 THEN 'BME680'
                        WHEN 5 THEN 'SCD4X'
                        WHEN 6 THEN 'AHT20'
                        WHEN 7 THEN 'SHT30'
                        WHEN 8 THEN 'SHT31'
                        WHEN 9 THEN 'AGS02MA'
                        WHEN 10 THEN 'SHT4X'
                        WHEN 11 THEN 'SGP40'
                        WHEN 12 THEN 'DHT22'
                        WHEN 13 THEN 'SDS011'
                        WHEN 14 THEN 'SHT35'
                        WHEN 15 THEN 'SPS30'
                        WHEN 16 THEN 'PMS5003'
                        WHEN 17 THEN 'PMS7003'
                        WHEN 18 THEN 'VIRTUAL_SENSOR'
                        WHEN 19 THEN 'LTR390'
                        WHEN 20 THEN 'BMP388'
                        WHEN 21 THEN 'BMP390'
                        WHEN 22 THEN 'lsm6ds'
                        WHEN 23 THEN 'SEN66'
                        WHEN 24 THEN 'MLX90640'
                        WHEN 25 THEN 'TSL_2591'
                        WHEN 26 THEN 'SEN63C'
                        WHEN 27 THEN 'SEN62'
                        WHEN 28 THEN 'BMP581'
                        WHEN 29 THEN 'SHTC3'
                        ELSE 'Unknown Sensor'
                    END,
                    count
                )
                FROM calibration_sensors_summary
                WHERE count > 0
            ), '{}'::jsonb),
            'status_by_level', COALESCE((
                SELECT jsonb_object_agg('level_' || level::text, count)
                FROM status_by_level_summary
            ), '{}'::jsonb)
        ),
        'dimensions', COALESCE((
            SELECT jsonb_agg(obj ORDER BY ord DESC)
            FROM (
                SELECT
                    value_count AS ord,
                    jsonb_build_object(
                        'dimension_id', dimension,
                        'dimension_name', CASE dimension
                            WHEN 1 THEN 'PM0.1'
                            WHEN 2 THEN 'PM1.0'
                            WHEN 3 THEN 'PM2.5'
                            WHEN 4 THEN 'PM4.0'
                            WHEN 5 THEN 'PM10.0'
                            WHEN 6 THEN 'Humidity'
                            WHEN 7 THEN 'Temperature'
                            WHEN 8 THEN 'VOC Index'
                            WHEN 9 THEN 'NOx Index'
                            WHEN 10 THEN 'Pressure'
                            WHEN 11 THEN 'CO2'
                            WHEN 12 THEN 'Ozone (O3)'
                            WHEN 13 THEN 'Air Quality Index (AQI)'
                            WHEN 14 THEN 'Gas Resistance'
                            WHEN 15 THEN 'Total VOC'
                            WHEN 16 THEN 'Nitrogen Dioxide (NO2)'
                            WHEN 17 THEN 'SGP40 Raw Gas'
                            WHEN 18 THEN 'SGP40 Adjusted Gas'
                            WHEN 19 THEN 'Adjusted Temperature Air Cube'
                            WHEN 20 THEN 'UVS'
                            WHEN 21 THEN 'Light'
                            WHEN 22 THEN 'Altitude'
                            WHEN 23 THEN 'UV Index'
                            WHEN 24 THEN 'Lux'
                            WHEN 25 THEN 'acceleration X'
                            WHEN 26 THEN 'acceleration Y'
                            WHEN 27 THEN 'acceleration Z'
                            WHEN 28 THEN 'gyro X'
                            WHEN 29 THEN 'gyro Y'
                            WHEN 30 THEN 'gyro Z'
                            WHEN 31 THEN 'Thermal Image'
                            ELSE 'Unknown'
                        END,
                        'unit', CASE dimension
                            WHEN 1 THEN 'µg/m³'
                            WHEN 2 THEN 'µg/m³'
                            WHEN 3 THEN 'µg/m³'
                            WHEN 4 THEN 'µg/m³'
                            WHEN 5 THEN 'µg/m³'
                            WHEN 6 THEN '%'
                            WHEN 7 THEN '°C'
                            WHEN 8 THEN 'Index'
                            WHEN 9 THEN 'Index'
                            WHEN 10 THEN 'hPa'
                            WHEN 11 THEN 'ppm'
                            WHEN 12 THEN 'ppb'
                            WHEN 13 THEN 'Index'
                            WHEN 14 THEN 'Ω'
                            WHEN 15 THEN 'ppb'
                            WHEN 16 THEN 'ppb'
                            WHEN 17 THEN 'Ω'
                            WHEN 18 THEN 'Ω'
                            WHEN 19 THEN '°C'
                            WHEN 23 THEN 'UV Index'
                            WHEN 24 THEN 'lx'
                            WHEN 25 THEN 'm/s²'
                            WHEN 26 THEN 'm/s²'
                            WHEN 27 THEN 'm/s²'
                            WHEN 28 THEN 'radians/s'
                            WHEN 29 THEN 'radians/s'
                            WHEN 30 THEN 'radians/s'
                            ELSE 'Unknown'
                        END,
                        'value_count', value_count,
                        'average_value', CASE
                            WHEN avg_value IS NULL OR avg_value != avg_value THEN NULL
                            ELSE to_jsonb(avg_value::double precision)
                        END,
                        'min_value', CASE
                            WHEN min_value IS NULL OR min_value != min_value THEN NULL
                            ELSE to_jsonb(min_value::double precision)
                        END,
                        'max_value', CASE
                            WHEN max_value IS NULL OR max_value != max_value THEN NULL
                            ELSE to_jsonb(max_value::double precision)
                        END
                    ) AS obj
                FROM dimension_statistics_summary
            ) dimsub
        ), '[]'::jsonb)
    ) AS payload
"""


# Previous snapshot definition (SensorModel 1-17, Dimension 1-18 only)
_PREVIOUS_SNAPSHOT_SELECT = r"""
CREATE MATERIALIZED VIEW statistics_endpoint_snapshot AS
SELECT
    1 AS id,
    jsonb_build_object(
        'totals', jsonb_build_object(
            'countries', (SELECT total_countries FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'cities', (SELECT total_cities FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'locations', (SELECT total_locations FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'stations', (SELECT total_stations FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'measurements', (SELECT total_measurements FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'calibration_measurements', (SELECT total_calibration_measurements FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'values', (SELECT total_values FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1),
            'station_statuses', (SELECT total_station_statuses FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1)
        ),
        'active_stations', jsonb_build_object(
            'last_hour', COALESCE((SELECT last_hour FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'last_24_hours', COALESCE((SELECT last_24_hours FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'last_7_days', COALESCE((SELECT last_7_days FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'last_30_days', COALESCE((SELECT last_30_days FROM active_stations_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0)
        ),
        'data_coverage', jsonb_build_object(
            'earliest_measurement', to_jsonb((SELECT earliest_measurement FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1)),
            'latest_measurement', to_jsonb((SELECT latest_measurement FROM statistics_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1)),
            'measurements_last_24h', COALESCE((SELECT last_24h FROM measurements_timeframe_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'measurements_last_7d', COALESCE((SELECT last_7d FROM measurements_timeframe_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0),
            'measurements_last_30d', COALESCE((SELECT last_30d FROM measurements_timeframe_summary ORDER BY last_refresh DESC NULLS LAST LIMIT 1), 0)
        ),
        'distribution', jsonb_build_object(
            'stations_by_source', COALESCE((
                SELECT jsonb_object_agg(src_label, cnt)
                FROM (
                    SELECT
                        CASE source
                            WHEN 1 THEN 'Luftdaten.at'
                            WHEN 2 THEN 'Luftdaten.at TTN LoRaWAN'
                            WHEN 3 THEN 'sensor.community'
                            ELSE 'Unknown'
                        END AS src_label,
                        count AS cnt
                    FROM stations_by_source_summary
                    WHERE count > 0
                ) sbs
            ), '{}'::jsonb),
            'stations_by_country', COALESCE((
                SELECT jsonb_object_agg(country_name, station_count)
                FROM stations_by_country_summary
            ), '{}'::jsonb),
            'top_cities', COALESCE((
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'city', city_name,
                        'country', country_name,
                        'station_count', station_count
                    )
                    ORDER BY station_count DESC
                )
                FROM top_cities_summary
            ), '[]'::jsonb),
            'sensor_models', COALESCE((
                SELECT jsonb_object_agg(
                    CASE sensor_model
                        WHEN 1 THEN 'SEN5X'
                        WHEN 2 THEN 'BMP280'
                        WHEN 3 THEN 'BME280'
                        WHEN 4 THEN 'BME680'
                        WHEN 5 THEN 'SCD4X'
                        WHEN 6 THEN 'AHT20'
                        WHEN 7 THEN 'SHT30'
                        WHEN 8 THEN 'SHT31'
                        WHEN 9 THEN 'AGS02MA'
                        WHEN 10 THEN 'SHT4X'
                        WHEN 11 THEN 'SGP40'
                        WHEN 12 THEN 'DHT22'
                        WHEN 13 THEN 'SDS011'
                        WHEN 14 THEN 'SHT35'
                        WHEN 15 THEN 'SPS30'
                        WHEN 16 THEN 'PMS5003'
                        WHEN 17 THEN 'PMS7003'
                        ELSE 'Unknown Sensor'
                    END,
                    count
                )
                FROM sensor_models_summary
                WHERE count > 0
            ), '{}'::jsonb),
            'calibration_sensors', COALESCE((
                SELECT jsonb_object_agg(
                    CASE sensor_model
                        WHEN 1 THEN 'SEN5X'
                        WHEN 2 THEN 'BMP280'
                        WHEN 3 THEN 'BME280'
                        WHEN 4 THEN 'BME680'
                        WHEN 5 THEN 'SCD4X'
                        WHEN 6 THEN 'AHT20'
                        WHEN 7 THEN 'SHT30'
                        WHEN 8 THEN 'SHT31'
                        WHEN 9 THEN 'AGS02MA'
                        WHEN 10 THEN 'SHT4X'
                        WHEN 11 THEN 'SGP40'
                        WHEN 12 THEN 'DHT22'
                        WHEN 13 THEN 'SDS011'
                        WHEN 14 THEN 'SHT35'
                        WHEN 15 THEN 'SPS30'
                        WHEN 16 THEN 'PMS5003'
                        WHEN 17 THEN 'PMS7003'
                        ELSE 'Unknown Sensor'
                    END,
                    count
                )
                FROM calibration_sensors_summary
                WHERE count > 0
            ), '{}'::jsonb),
            'status_by_level', COALESCE((
                SELECT jsonb_object_agg('level_' || level::text, count)
                FROM status_by_level_summary
            ), '{}'::jsonb)
        ),
        'dimensions', COALESCE((
            SELECT jsonb_agg(obj ORDER BY ord DESC)
            FROM (
                SELECT
                    value_count AS ord,
                    jsonb_build_object(
                        'dimension_id', dimension,
                        'dimension_name', CASE dimension
                            WHEN 1 THEN 'PM0.1'
                            WHEN 2 THEN 'PM1.0'
                            WHEN 3 THEN 'PM2.5'
                            WHEN 4 THEN 'PM4.0'
                            WHEN 5 THEN 'PM10.0'
                            WHEN 6 THEN 'Humidity'
                            WHEN 7 THEN 'Temperature'
                            WHEN 8 THEN 'VOC Index'
                            WHEN 9 THEN 'NOx Index'
                            WHEN 10 THEN 'Pressure'
                            WHEN 11 THEN 'CO2'
                            WHEN 12 THEN 'Ozone (O3)'
                            WHEN 13 THEN 'Air Quality Index (AQI)'
                            WHEN 14 THEN 'Gas Resistance'
                            WHEN 15 THEN 'Total VOC'
                            WHEN 16 THEN 'Nitrogen Dioxide (NO2)'
                            WHEN 17 THEN 'SGP40 Raw Gas'
                            WHEN 18 THEN 'SGP40 Adjusted Gas'
                            ELSE 'Unknown'
                        END,
                        'unit', CASE dimension
                            WHEN 1 THEN 'µg/m³'
                            WHEN 2 THEN 'µg/m³'
                            WHEN 3 THEN 'µg/m³'
                            WHEN 4 THEN 'µg/m³'
                            WHEN 5 THEN 'µg/m³'
                            WHEN 6 THEN '%'
                            WHEN 7 THEN '°C'
                            WHEN 8 THEN 'Index'
                            WHEN 9 THEN 'Index'
                            WHEN 10 THEN 'hPa'
                            WHEN 11 THEN 'ppm'
                            WHEN 12 THEN 'ppb'
                            WHEN 13 THEN 'Index'
                            WHEN 14 THEN 'Ω'
                            WHEN 15 THEN 'ppb'
                            WHEN 16 THEN 'ppb'
                            WHEN 17 THEN 'Ω'
                            WHEN 18 THEN 'Ω'
                            ELSE 'Unknown'
                        END,
                        'value_count', value_count,
                        'average_value', CASE
                            WHEN avg_value IS NULL OR avg_value != avg_value THEN NULL
                            ELSE to_jsonb(avg_value::double precision)
                        END,
                        'min_value', CASE
                            WHEN min_value IS NULL OR min_value != min_value THEN NULL
                            ELSE to_jsonb(min_value::double precision)
                        END,
                        'max_value', CASE
                            WHEN max_value IS NULL OR max_value != max_value THEN NULL
                            ELSE to_jsonb(max_value::double precision)
                        END
                    ) AS obj
                FROM dimension_statistics_summary
            ) dimsub
        ), '[]'::jsonb)
    ) AS payload
"""


def upgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS statistics_endpoint_snapshot CASCADE")
    op.execute(_SNAPSHOT_SELECT.strip())
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_statistics_endpoint_snapshot_id "
        "ON statistics_endpoint_snapshot (id)"
    )
    op.execute("REFRESH MATERIALIZED VIEW statistics_endpoint_snapshot")


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS statistics_endpoint_snapshot CASCADE")
    op.execute(_PREVIOUS_SNAPSHOT_SELECT.strip())
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_statistics_endpoint_snapshot_id "
        "ON statistics_endpoint_snapshot (id)"
    )
    op.execute("REFRESH MATERIALIZED VIEW statistics_endpoint_snapshot")
