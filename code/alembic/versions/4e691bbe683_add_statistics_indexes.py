"""Add statistics indexes

Revision ID: 4e691bbe683
Revises: fc8c3d3efd58
Create Date: 2025-01-11 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e691bbe683'
down_revision: Union[str, None] = 'fc8c3d3efd58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add indexes for statistics endpoint optimization (Phase 1).
    These indexes will significantly improve query performance for:
    - Time-based filtering (last_active, time_measured)
    - Join operations (foreign keys)
    - Aggregation queries (dimension, sensor_model, source, level)
    """
    
    # Time-based indexes for active stations queries
    # Partial index for last_active (only indexes non-NULL values)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_stations_last_active 
        ON stations(last_active) 
        WHERE last_active IS NOT NULL
    """)
    
    # Time-based indexes for measurement queries
    op.create_index(
        'idx_measurements_time_measured',
        'measurements',
        ['time_measured'],
        if_not_exists=True
    )
    
    # Composite index for time-based measurements with station
    op.create_index(
        'idx_measurements_time_station',
        'measurements',
        ['time_measured', 'station_id'],
        if_not_exists=True
    )
    
    # Foreign key indexes for join operations
    op.create_index(
        'idx_locations_city_id',
        'locations',
        ['city_id'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_locations_country_id',
        'locations',
        ['country_id'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_stations_location_id',
        'stations',
        ['location_id'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_stations_source',
        'stations',
        ['source'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_measurements_station_id',
        'measurements',
        ['station_id'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_measurements_location_id',
        'measurements',
        ['location_id'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_values_measurement_id',
        'values',
        ['measurement_id'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_values_calibration_measurement_id',
        'values',
        ['calibration_measurement_id'],
        if_not_exists=True
    )
    
    # Dimension and value indexes
    op.create_index(
        'idx_values_dimension',
        'values',
        ['dimension'],
        if_not_exists=True
    )
    
    # Partial index for dimension statistics (filters out NULL and 'nan')
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_values_dimension_value 
        ON values(dimension, value) 
        WHERE value IS NOT NULL AND value != 'nan'
    """)
    
    # Sensor model indexes
    op.create_index(
        'idx_measurements_sensor_model',
        'measurements',
        ['sensor_model'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_calibration_measurements_sensor_model',
        'calibration_measurements',
        ['sensor_model'],
        if_not_exists=True
    )
    
    # Station status indexes
    op.create_index(
        'idx_station_status_level',
        'stationStatus',
        ['level'],
        if_not_exists=True
    )
    
    op.create_index(
        'idx_station_status_station_id',
        'stationStatus',
        ['station_id'],
        if_not_exists=True
    )


def downgrade() -> None:
    """
    Remove all indexes created in upgrade.
    """
    op.drop_index('idx_station_status_station_id', table_name='stationStatus', if_exists=True)
    op.drop_index('idx_station_status_level', table_name='stationStatus', if_exists=True)
    op.drop_index('idx_calibration_measurements_sensor_model', table_name='calibration_measurements', if_exists=True)
    op.drop_index('idx_measurements_sensor_model', table_name='measurements', if_exists=True)
    op.execute('DROP INDEX IF EXISTS idx_values_dimension_value')
    op.drop_index('idx_values_dimension', table_name='values', if_exists=True)
    op.drop_index('idx_values_calibration_measurement_id', table_name='values', if_exists=True)
    op.drop_index('idx_values_measurement_id', table_name='values', if_exists=True)
    op.drop_index('idx_measurements_location_id', table_name='measurements', if_exists=True)
    op.drop_index('idx_measurements_station_id', table_name='measurements', if_exists=True)
    op.drop_index('idx_stations_source', table_name='stations', if_exists=True)
    op.drop_index('idx_stations_location_id', table_name='stations', if_exists=True)
    op.drop_index('idx_locations_country_id', table_name='locations', if_exists=True)
    op.drop_index('idx_locations_city_id', table_name='locations', if_exists=True)
    op.drop_index('idx_measurements_time_station', table_name='measurements', if_exists=True)
    op.drop_index('idx_measurements_time_measured', table_name='measurements', if_exists=True)
    op.drop_index('idx_stations_last_active', table_name='stations', if_exists=True)
