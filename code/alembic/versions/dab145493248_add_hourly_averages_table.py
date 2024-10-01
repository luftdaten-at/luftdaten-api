"""Add hourly averages table

Revision ID: dab145493248
Revises: 72550e56cbb0
Create Date: 2024-10-01 08:30:00.036391

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dab145493248'
down_revision: Union[str, None] = '72550e56cbb0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('hourly_averages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('station_id', sa.Integer(), nullable=True),
    sa.Column('avg_value', sa.Float(), nullable=True),
    sa.Column('sensor_model', sa.Integer(), nullable=True),
    sa.Column('dimension', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_hourly_averages_id'), 'hourly_averages', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_hourly_averages_id'), table_name='hourly_averages')
    op.drop_table('hourly_averages')
    # ### end Alembic commands ###
