"""create hourly_avg view

Revision ID: 8e1c45de1275
Revises: 5516d2dd3e78
Create Date: 2024-11-07 14:21:42.941381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e1c45de1275'
down_revision: Union[str, None] = '5516d2dd3e78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""create view hourly_avg as
select station_id, hour, jsonb_object_agg(dimension, avg) as dimension_avg
from (select station_id, dimension, date_trunc('hour', time_measured) as hour, avg(value)
from measurements as m join values as v on v.measurement_id = m.id
join stations as s on s.id = m.station_id
group by station_id, dimension, hour 
order by station_id, dimension, hour)
group by station_id, hour;""")


def downgrade() -> None:
    op.execute("drop view if exists hourly_avg")
