"""Enable pg_stat_statements extension for query statistics.

Requires PostgreSQL to load the library at startup, e.g.:
  shared_preload_libraries = 'pg_stat_statements'
(see docker-compose `db` service `command`).

Revision ID: 7f3a9c2e1d0b
Revises: 8d4c2b1a9f0e
Create Date: 2026-04-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7f3a9c2e1d0b"
down_revision: Union[str, None] = "8d4c2b1a9f0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_stat_statements"))


def downgrade() -> None:
    op.execute(sa.text("DROP EXTENSION IF EXISTS pg_stat_statements"))
