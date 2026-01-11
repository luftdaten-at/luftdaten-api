"""Add statistics materialized views

Revision ID: cb023e559c7
Revises: 4e691bbe683
Create Date: 2025-01-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb023e559c7'
down_revision: Union[str, None] = '4e691bbe683'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create materialized views for statistics endpoint optimization (Phase 2).
    These views pre-compute expensive aggregations for fast retrieval.
    """
    
    # Statistics Summary Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS statistics_summary AS
        SELECT 
            (SELECT COUNT(*) FROM countries) as total_countries,
            (SELECT COUNT(*) FROM cities) as total_cities,
            (SELECT COUNT(*) FROM locations) as total_locations,
            (SELECT COUNT(*) FROM stations) as total_stations,
            (SELECT COUNT(*) FROM measurements) as total_measurements,
            (SELECT COUNT(*) FROM calibration_measurements) as total_calibration_measurements,
            (SELECT COUNT(*) FROM values) as total_values,
            (SELECT COUNT(*) FROM "stationStatus") as total_station_statuses,
            (SELECT MIN(time_measured) FROM measurements) as earliest_measurement,
            (SELECT MAX(time_measured) FROM measurements) as latest_measurement,
            NOW() as last_refresh
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_statistics_summary_refresh ON statistics_summary(last_refresh)")
    
    # Active Stations Summary Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS active_stations_summary AS
        SELECT 
            COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '1 hour' THEN id END) as last_hour,
            COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '24 hours' THEN id END) as last_24_hours,
            COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '7 days' THEN id END) as last_7_days,
            COUNT(DISTINCT CASE WHEN last_active >= NOW() - INTERVAL '30 days' THEN id END) as last_30_days,
            NOW() as last_refresh
        FROM stations
        WHERE last_active IS NOT NULL
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_active_stations_summary_refresh ON active_stations_summary(last_refresh)")
    
    # Stations by Country Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS stations_by_country_summary AS
        SELECT 
            c.name as country_name,
            COUNT(DISTINCT s.id) as station_count
        FROM countries c
        JOIN cities ci ON c.id = ci.country_id
        JOIN locations l ON ci.id = l.city_id
        JOIN stations s ON l.id = s.location_id
        GROUP BY c.name
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stations_by_country_name ON stations_by_country_summary(country_name)")
    
    # Top Cities Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS top_cities_summary AS
        SELECT 
            ci.name as city_name,
            c.name as country_name,
            COUNT(DISTINCT s.id) as station_count
        FROM cities ci
        JOIN countries c ON ci.country_id = c.id
        JOIN locations l ON ci.id = l.city_id
        JOIN stations s ON l.id = s.location_id
        GROUP BY ci.name, c.name
        ORDER BY COUNT(DISTINCT s.id) DESC
        LIMIT 10
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_top_cities_name ON top_cities_summary(city_name, country_name)")
    
    # Dimension Statistics Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS dimension_statistics_summary AS
        SELECT 
            dimension,
            COUNT(id) as value_count,
            AVG(value) as avg_value,
            MIN(value) as min_value,
            MAX(value) as max_value
        FROM values
        WHERE value IS NOT NULL 
          AND value != 'nan'
          AND value = value
        GROUP BY dimension
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dimension_statistics_dimension ON dimension_statistics_summary(dimension)")
    
    # Sensor Models Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_models_summary AS
        SELECT 
            sensor_model,
            COUNT(DISTINCT id) as count
        FROM measurements
        GROUP BY sensor_model
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_sensor_models_sensor_model ON sensor_models_summary(sensor_model)")
    
    # Calibration Sensors Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS calibration_sensors_summary AS
        SELECT 
            sensor_model,
            COUNT(DISTINCT id) as count
        FROM calibration_measurements
        GROUP BY sensor_model
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_calibration_sensors_sensor_model ON calibration_sensors_summary(sensor_model)")
    
    # Status by Level Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS status_by_level_summary AS
        SELECT 
            level,
            COUNT(id) as count
        FROM "stationStatus"
        GROUP BY level
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_status_by_level_level ON status_by_level_summary(level)")
    
    # Stations by Source Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS stations_by_source_summary AS
        SELECT 
            source,
            COUNT(id) as count
        FROM stations
        GROUP BY source
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stations_by_source_source ON stations_by_source_summary(source)")
    
    # Measurements Timeframe Summary
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS measurements_timeframe_summary AS
        SELECT 
            COUNT(CASE WHEN time_measured >= NOW() - INTERVAL '24 hours' THEN id END) as last_24h,
            COUNT(CASE WHEN time_measured >= NOW() - INTERVAL '7 days' THEN id END) as last_7d,
            COUNT(CASE WHEN time_measured >= NOW() - INTERVAL '30 days' THEN id END) as last_30d,
            NOW() as last_refresh
        FROM measurements
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_measurements_timeframe_refresh ON measurements_timeframe_summary(last_refresh)")
    
    # Create refresh function
    # Use CONCURRENTLY for views with unique indexes to avoid locking
    op.execute("""
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
    """)


def downgrade() -> None:
    """
    Remove all materialized views and refresh function.
    """
    op.execute("DROP FUNCTION IF EXISTS refresh_statistics_views() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS measurements_timeframe_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS stations_by_source_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS status_by_level_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS calibration_sensors_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS sensor_models_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS dimension_statistics_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS top_cities_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS stations_by_country_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS active_stations_summary CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS statistics_summary CASCADE")
