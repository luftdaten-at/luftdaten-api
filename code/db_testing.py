"""Test database helpers (async session + sync DDL). Not used at runtime by the API."""

import os

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Docker Compose test DB uses hostname ``db_test``. For pytest on the host against the published port (5433),
# set ``TEST_POSTGRES_HOST=127.0.0.1`` and ``TEST_POSTGRES_PORT=5433``.
_TEST_PG_HOST = os.getenv("TEST_POSTGRES_HOST", "db_test")
_TEST_PG_PORT = os.getenv("TEST_POSTGRES_PORT", "5432")
SYNC_URL = (
    f"postgresql://test_user:test_password@{_TEST_PG_HOST}:{_TEST_PG_PORT}/test_database"
)
ASYNC_URL = SYNC_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

_test_connect = {"application_name": "luftdaten-api-test"}
_test_async_connect = {"server_settings": {"application_name": "luftdaten-api-test"}}

test_sync_engine = create_engine(SYNC_URL, poolclass=NullPool, connect_args=_test_connect)
TestSyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_sync_engine)

test_async_engine = create_async_engine(
    ASYNC_URL, poolclass=NullPool, connect_args=_test_async_connect
)
TestAsyncSessionLocal = async_sessionmaker(
    test_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
