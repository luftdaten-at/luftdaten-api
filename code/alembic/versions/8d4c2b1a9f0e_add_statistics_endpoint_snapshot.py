"""Add statistics_endpoint_snapshot materialized view

Single-row jsonb snapshot of /statistics payload, built from existing statistics MVs.
Revision ID: 8d4c2b1a9f0e
Revises: b3ba2ef0fc0, e2dda8ce7cd2 (merge)
Create Date: 2026-04-10

"""
from typing import Sequence, Union, Tuple

from alembic import op

revision: str = "8d4c2b1a9f0e"
down_revision: Union[str, Tuple[str, ...], None] = ("b3ba2ef0fc0", "e2dda8ce7cd2")
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


_REFRESH_FN_BODY = r"""
CREATE OR REPLACE FUNCTION refresh_statistics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY statistics_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY active_stations_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY stations_by_country_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY top_cities_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dimension_statistics_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY sensor_models_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY calibration_sensors_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY status_by_level_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY stations_by_source_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY measurements_timeframe_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY statistics_endpoint_snapshot;
END;
$$ LANGUAGE plpgsql;
"""


_REFRESH_FN_PRE_SNAPSHOT = r"""
CREATE OR REPLACE FUNCTION refresh_statistics_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY statistics_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY active_stations_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY stations_by_country_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY top_cities_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY dimension_statistics_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY sensor_models_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY calibration_sensors_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY status_by_level_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY stations_by_source_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY measurements_timeframe_summary;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.execute(_SNAPSHOT_SELECT.strip())
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_statistics_endpoint_snapshot_id "
        "ON statistics_endpoint_snapshot (id)"
    )
    op.execute(_REFRESH_FN_BODY.strip())


def downgrade() -> None:
    op.execute(_REFRESH_FN_PRE_SNAPSHOT.strip())
    op.execute("DROP MATERIALIZED VIEW IF EXISTS statistics_endpoint_snapshot CASCADE")
