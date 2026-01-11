"""Ensure stations/all endpoint indexes

Revision ID: f2edce7f694
Revises: cb023e559c7
Create Date: 2025-01-11 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2edce7f694'
down_revision: Union[str, None] = 'cb023e559c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Ensure all required indexes exist for the /stations/all endpoint (Phase 1).
    
    Most indexes were already created in the statistics indexes migration (4e691bbe683),
    but this migration ensures they exist and documents them specifically for the 
    stations/all endpoint optimization.
    
    Indexes needed for /stations/all:
    - idx_measurements_station_id: For fast measurement count queries (N+1 optimization)
    - idx_stations_location_id: For efficient station-location joins
    - idx_stations_device: For station lookups by device ID (if not already exists from model)
    - idx_stations_last_active: For time-based filtering (if needed in future)
    
    All indexes use IF NOT EXISTS to avoid errors if they already exist.
    """
    
    # A. Measurement Station ID Index
    # Already exists from statistics indexes migration, but ensure it exists
    op.create_index(
        'idx_measurements_station_id',
        'measurements',
        ['station_id'],
        if_not_exists=True
    )
    
    # B. Station Location Relationship Index
    # Already exists from statistics indexes migration, but ensure it exists
    op.create_index(
        'idx_stations_location_id',
        'stations',
        ['location_id'],
        if_not_exists=True
    )
    
    # C. Station Device Index
    # The Station model has index=True on device column, but we ensure a named index exists
    # This helps with query planning and documentation
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_stations_device 
        ON stations(device)
    """)
    
    # D. Station Last Active Index
    # Already exists from statistics indexes migration (with partial index for NOT NULL),
    # but ensure the general index exists for completeness
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_stations_last_active 
        ON stations(last_active) 
        WHERE last_active IS NOT NULL
    """)


def downgrade() -> None:
    """
    Remove indexes created in upgrade.
    
    Note: We only remove indexes if they don't conflict with other migrations.
    Since most indexes are shared with the statistics endpoint, we use IF EXISTS
    to avoid errors if they're still needed by other parts of the application.
    """
    # Only remove idx_stations_device if it was created here
    # Other indexes are shared with statistics endpoint and should not be dropped
    op.execute("DROP INDEX IF EXISTS idx_stations_device")
