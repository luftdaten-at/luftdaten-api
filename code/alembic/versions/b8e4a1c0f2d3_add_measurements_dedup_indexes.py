"""Composite indexes for ingest duplicate lookup (station_id, time_measured, sensor_model).

Revision ID: b8e4a1c0f2d3
Revises: 7f3a9c2e1d0b
Create Date: 2026-04-20

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b8e4a1c0f2d3"
down_revision: Union[str, None] = "7f3a9c2e1d0b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_measurements_station_time_sensor",
        "measurements",
        ["station_id", "time_measured", "sensor_model"],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        "idx_calibration_measurements_station_time_sensor",
        "calibration_measurements",
        ["station_id", "time_measured", "sensor_model"],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_calibration_measurements_station_time_sensor",
        table_name="calibration_measurements",
        if_exists=True,
    )
    op.drop_index(
        "idx_measurements_station_time_sensor",
        table_name="measurements",
        if_exists=True,
    )
