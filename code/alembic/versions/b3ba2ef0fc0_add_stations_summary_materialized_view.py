"""Add stations summary materialized view

Revision ID: b3ba2ef0fc0
Revises: f2edce7f694
Create Date: 2025-01-11 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3ba2ef0fc0'
down_revision: Union[str, None] = 'f2edce7f694'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create materialized view for /stations/all endpoint optimization (Phase 2).
    This view pre-computes station metadata with measurement counts to eliminate
    the N+1 query problem.
    """
    
    # Stations Summary Materialized View
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS stations_summary AS
        SELECT 
            s.id as station_id,
            s.device,
            s.last_active,
            s.location_id,
            l.lat as location_lat,
            l.lon as location_lon,
            l.height as location_height,
            COUNT(m.id) as measurements_count,
            NOW() as last_refresh
        FROM stations s
        LEFT JOIN locations l ON s.location_id = l.id
        LEFT JOIN measurements m ON m.station_id = s.id
        GROUP BY s.id, s.device, s.last_active, s.location_id, l.lat, l.lon, l.height
    """)
    
    # Create unique index for CONCURRENTLY refresh
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_stations_summary_station_id ON stations_summary(station_id)")
    
    # Additional indexes for query optimization
    op.execute("CREATE INDEX IF NOT EXISTS idx_stations_summary_device ON stations_summary(device)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_stations_summary_last_active ON stations_summary(last_active)")
    
    # Create refresh function
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_stations_summary()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY stations_summary;
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade() -> None:
    """
    Remove materialized view and refresh function.
    """
    op.execute("DROP FUNCTION IF EXISTS refresh_stations_summary() CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS stations_summary CASCADE")
