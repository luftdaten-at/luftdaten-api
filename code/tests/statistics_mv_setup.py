"""Create statistics materialized views for integration tests (no Alembic in test DB)."""

from sqlalchemy import text
from sqlalchemy.engine import Engine

_STATISTICS_MVS = (
    "statistics_endpoint_snapshot",
    "measurements_timeframe_summary",
    "stations_by_source_summary",
    "status_by_level_summary",
    "calibration_sensors_summary",
    "sensor_models_summary",
    "dimension_statistics_summary",
    "top_cities_summary",
    "stations_by_country_summary",
    "active_stations_summary",
    "statistics_summary",
)

_CREATE_STATISTICS_MVS = """
CREATE MATERIALIZED VIEW IF NOT EXISTS statistics_summary AS
SELECT
    (SELECT COUNT(*) FROM countries) AS total_countries,
    (SELECT COUNT(*) FROM cities) AS total_cities,
    (SELECT COUNT(*) FROM locations) AS total_locations,
    (SELECT COUNT(*) FROM stations) AS total_stations,
    (SELECT COUNT(*) FROM measurements) AS total_measurements,
    (SELECT COUNT(*) FROM calibration_measurements) AS total_calibration_measurements,
    (SELECT COUNT(*) FROM values) AS total_values,
    (SELECT COUNT(*) FROM "stationStatus") AS total_station_statuses,
    (SELECT MIN(time_measured) FROM measurements) AS earliest_measurement,
    (SELECT MAX(time_measured) FROM measurements) AS latest_measurement,
    NOW() AS last_refresh;

CREATE MATERIALIZED VIEW IF NOT EXISTS active_stations_summary AS
SELECT
    COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '1 hour' THEN id END) AS last_hour,
    COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '24 hours' THEN id END) AS last_24_hours,
    COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '7 days' THEN id END) AS last_7_days,
    COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '30 days' THEN id END) AS last_30_days,
    NOW() AS last_refresh
FROM stations
WHERE last_active IS NOT NULL;

CREATE MATERIALIZED VIEW IF NOT EXISTS stations_by_country_summary AS
SELECT c.name AS country_name, COUNT(DISTINCT s.id) AS station_count
FROM countries c
JOIN cities ci ON c.id = ci.country_id
JOIN locations l ON ci.id = l.city_id
JOIN stations s ON l.id = s.location_id
GROUP BY c.name;

CREATE MATERIALIZED VIEW IF NOT EXISTS top_cities_summary AS
SELECT ci.name AS city_name, c.name AS country_name, COUNT(DISTINCT s.id) AS station_count
FROM cities ci
JOIN countries c ON ci.country_id = c.id
JOIN locations l ON ci.id = l.city_id
JOIN stations s ON l.id = s.location_id
GROUP BY ci.name, c.name
ORDER BY COUNT(DISTINCT s.id) DESC
LIMIT 10;

CREATE MATERIALIZED VIEW IF NOT EXISTS dimension_statistics_summary AS
SELECT
    dimension,
    COUNT(id) AS value_count,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value
FROM values
WHERE value IS NOT NULL AND value = value
GROUP BY dimension;

CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_models_summary AS
SELECT sensor_model, COUNT(DISTINCT id) AS count
FROM measurements
GROUP BY sensor_model;

CREATE MATERIALIZED VIEW IF NOT EXISTS calibration_sensors_summary AS
SELECT sensor_model, COUNT(DISTINCT id) AS count
FROM calibration_measurements
GROUP BY sensor_model;

CREATE MATERIALIZED VIEW IF NOT EXISTS status_by_level_summary AS
SELECT level, COUNT(id) AS count
FROM "stationStatus"
GROUP BY level;

CREATE MATERIALIZED VIEW IF NOT EXISTS stations_by_source_summary AS
SELECT source, COUNT(id) AS count
FROM stations
GROUP BY source;

CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_timeframe_summary AS
SELECT
    COUNT(CASE WHEN time_measured >= NOW() - INTERVAL '24 hours' THEN id END) AS last_24h,
    COUNT(CASE WHEN time_measured >= NOW() - INTERVAL '7 days' THEN id END) AS last_7d,
    COUNT(CASE WHEN time_measured >= NOW() - INTERVAL '30 days' THEN id END) AS last_30d,
    NOW() AS last_refresh
FROM measurements;
"""

_REFRESH_MVS = (
    "statistics_summary",
    "active_stations_summary",
    "stations_by_country_summary",
    "top_cities_summary",
    "dimension_statistics_summary",
    "sensor_models_summary",
    "calibration_sensors_summary",
    "status_by_level_summary",
    "stations_by_source_summary",
    "measurements_timeframe_summary",
)


def ensure_statistics_materialized_views(engine: Engine) -> None:
    with engine.connect() as conn:
        for stmt in _CREATE_STATISTICS_MVS.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(text(stmt))
        conn.commit()
        for mv in _REFRESH_MVS:
            conn.execute(text(f"REFRESH MATERIALIZED VIEW {mv}"))
        conn.commit()


def drop_statistics_materialized_views(engine: Engine) -> None:
    with engine.connect() as conn:
        for mv in _STATISTICS_MVS:
            conn.execute(text(f"DROP MATERIALIZED VIEW IF EXISTS {mv} CASCADE"))
        conn.commit()
