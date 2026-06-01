import sys
import os

# Add the parent directory to the path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base
from db_testing import test_sync_engine, TestAsyncSessionLocal
from utils.response_cache import get_statistics_cache
_tests_dir = os.path.dirname(os.path.abspath(__file__))
if _tests_dir not in sys.path:
    sys.path.insert(0, _tests_dir)
from statistics_mv_setup import (
    drop_statistics_materialized_views,
    ensure_statistics_materialized_views,
)


@pytest.fixture(scope="session")
def test_client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Setup and teardown database for each test"""
    Base.metadata.create_all(bind=test_sync_engine)
    ensure_statistics_materialized_views(test_sync_engine)
    get_statistics_cache().invalidate("statistics:v1")
    yield
    try:
        drop_statistics_materialized_views(test_sync_engine)
        Base.metadata.drop_all(bind=test_sync_engine)
    except Exception:
        pass


async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db
