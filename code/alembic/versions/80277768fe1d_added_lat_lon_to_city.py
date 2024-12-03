"""added lat, lon to city

Revision ID: 80277768fe1d
Revises: 2df6cd6bb99c
Create Date: 2024-12-03 14:20:12.262337

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80277768fe1d'
down_revision: Union[str, None] = '2df6cd6bb99c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('cities', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('cities', sa.Column('lon', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('cities', 'lon')
    op.drop_column('cities', 'lat')
    # ### end Alembic commands ###
