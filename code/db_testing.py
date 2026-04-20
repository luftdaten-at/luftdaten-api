"""Test database helpers (async session + sync DDL). Not used at runtime by the API."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

SYNC_URL = "postgresql://test_user:test_password@db_test/test_database"
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
