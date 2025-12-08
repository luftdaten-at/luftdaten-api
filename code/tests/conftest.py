import sys
import os

# Add the parent directory to the path so we can import modules
# This must be done BEFORE any imports from the parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

# Configure test database
SQLALCHEMY_DATABASE_URL = "postgresql://test_user:test_password@db_test/test_database"

engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def test_client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    """Create a database session for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """Setup and teardown database for each test"""
    Base.metadata.create_all(bind=engine)
    yield
    # Drop all tables, ignoring errors if tables don't exist
    try:
        Base.metadata.drop_all(bind=engine)
    except Exception:
        # Ignore errors during teardown (e.g., tables already dropped)
        pass

def override_get_db():
    """Override the database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Override the database dependency
app.dependency_overrides[get_db] = override_get_db
