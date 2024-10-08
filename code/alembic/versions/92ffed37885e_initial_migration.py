"""Initial migration

Revision ID: 92ffed37885e
Revises: 
Create Date: 2024-09-25 00:59:33.894082

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '92ffed37885e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('stations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('device', sa.String(), nullable=True),
    sa.Column('apikey', sa.String(), nullable=True),
    sa.Column('lat', sa.Float(), nullable=True),
    sa.Column('lon', sa.Float(), nullable=True),
    sa.Column('height', sa.Float(), nullable=True),
    sa.Column('time', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stations_device'), 'stations', ['device'], unique=True)
    op.create_index(op.f('ix_stations_id'), 'stations', ['id'], unique=False)
    op.create_table('measurements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sensor_model', sa.Integer(), nullable=True),
    sa.Column('station_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_measurements_id'), 'measurements', ['id'], unique=False)
    op.create_table('values',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('dimension', sa.Integer(), nullable=True),
    sa.Column('value', sa.Float(), nullable=True),
    sa.Column('measurement_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['measurement_id'], ['measurements.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_values_id'), 'values', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_values_id'), table_name='values')
    op.drop_table('values')
    op.drop_index(op.f('ix_measurements_id'), table_name='measurements')
    op.drop_table('measurements')
    op.drop_index(op.f('ix_stations_id'), table_name='stations')
    op.drop_index(op.f('ix_stations_device'), table_name='stations')
    op.drop_table('stations')
    # ### end Alembic commands ###
