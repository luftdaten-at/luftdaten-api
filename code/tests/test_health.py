import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + '/../')

import pytest
from fastapi.testclient import TestClient
from main import app
from database import get_db, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from apscheduler.schedulers.background import BackgroundScheduler
from unittest.mock import patch, MagicMock
from datetime import datetime

# Configure test database
SQLALCHEMY_DATABASE_URL = "postgresql://test_user:test_password@db_test/test_database"

engine = create_engine(SQLALCHEMY_DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

client = TestClient(app)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="function", autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def mock_scheduler():
    """Create a mock scheduler for testing"""
    scheduler = MagicMock(spec=BackgroundScheduler)
    scheduler.running = True
    scheduler.get_jobs.return_value = [MagicMock()]  # One mock job
    return scheduler

class TestHealthRouter:
    
    def test_simple_health_check(self):
        """Test simple health check endpoint"""
        response = client.get("/v1/health/simple")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.3"
        assert "timestamp" in data
        
        # Verify timestamp is valid ISO format
        datetime.fromisoformat(data["timestamp"])
    
    def test_comprehensive_health_check_all_healthy(self, mock_scheduler):
        """Test comprehensive health check when all components are healthy"""
        # Mock the database connection
        with patch('code.routers.health.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]
            mock_connection.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            
            # Mock the scheduler
            with patch('code.routers.health.scheduler', mock_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 200
                
                data = response.json()
                assert data["status"] == "healthy"
                assert data["version"] == "0.3"
                assert "timestamp" in data
                assert data["checks"]["api"] == "healthy"
                assert data["checks"]["database"] == "healthy"
                assert data["checks"]["scheduler"] == "healthy"
                assert data["scheduler_jobs"] == 1
    
    def test_comprehensive_health_check_database_unhealthy(self, mock_scheduler):
        """Test comprehensive health check when database is unhealthy"""
        # Mock the database connection to fail
        with patch('code.routers.health.engine') as mock_engine:
            mock_engine.connect.side_effect = Exception("Database connection failed")
            
            # Mock the scheduler
            with patch('code.routers.health.scheduler', mock_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503
                
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["version"] == "0.3"
                assert "timestamp" in data
                assert data["checks"]["api"] == "healthy"
                assert data["checks"]["database"] == "unhealthy"
                assert data["checks"]["scheduler"] == "healthy"
                assert "database_error" in data
                assert data["database_error"] == "Database connection failed"
    
    def test_comprehensive_health_check_scheduler_unhealthy(self):
        """Test comprehensive health check when scheduler is unhealthy"""
        # Mock the database connection
        with patch('code.routers.health.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]
            mock_connection.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            
            # Mock the scheduler to be unhealthy
            unhealthy_scheduler = MagicMock(spec=BackgroundScheduler)
            unhealthy_scheduler.running = False
            
            with patch('code.routers.health.scheduler', unhealthy_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503
                
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["version"] == "0.3"
                assert "timestamp" in data
                assert data["checks"]["api"] == "healthy"
                assert data["checks"]["database"] == "healthy"
                assert data["checks"]["scheduler"] == "unhealthy"
    
    def test_comprehensive_health_check_scheduler_none(self):
        """Test comprehensive health check when scheduler is None"""
        # Mock the database connection
        with patch('code.routers.health.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]
            mock_connection.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            
            # Mock the scheduler to be None
            with patch('code.routers.health.scheduler', None):
                response = client.get("/v1/health/")
                assert response.status_code == 503
                
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["checks"]["scheduler"] == "unhealthy"
    
    def test_comprehensive_health_check_scheduler_exception(self):
        """Test comprehensive health check when scheduler raises an exception"""
        # Mock the database connection
        with patch('code.routers.health.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]
            mock_connection.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            
            # Mock the scheduler to raise an exception
            broken_scheduler = MagicMock(spec=BackgroundScheduler)
            broken_scheduler.running.side_effect = Exception("Scheduler error")
            
            with patch('code.routers.health.scheduler', broken_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503
                
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["checks"]["scheduler"] == "unhealthy"
                assert "scheduler_error" in data
                assert data["scheduler_error"] == "Scheduler error"
    
    def test_comprehensive_health_check_multiple_jobs(self, mock_scheduler):
        """Test comprehensive health check with multiple scheduler jobs"""
        # Mock multiple jobs
        mock_scheduler.get_jobs.return_value = [MagicMock(), MagicMock(), MagicMock()]
        
        # Mock the database connection
        with patch('code.routers.health.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]
            mock_connection.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            
            with patch('code.routers.health.scheduler', mock_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 200
                
                data = response.json()
                assert data["scheduler_jobs"] == 3
    
    def test_comprehensive_health_check_database_and_scheduler_unhealthy(self):
        """Test comprehensive health check when both database and scheduler are unhealthy"""
        # Mock the database connection to fail
        with patch('code.routers.health.engine') as mock_engine:
            mock_engine.connect.side_effect = Exception("Database connection failed")
            
            # Mock the scheduler to be unhealthy
            unhealthy_scheduler = MagicMock(spec=BackgroundScheduler)
            unhealthy_scheduler.running = False
            
            with patch('code.routers.health.scheduler', unhealthy_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503
                
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["checks"]["database"] == "unhealthy"
                assert data["checks"]["scheduler"] == "unhealthy"
                assert "database_error" in data
                assert data["database_error"] == "Database connection failed"
    
    def test_health_check_response_structure(self, mock_scheduler):
        """Test that health check response has the correct structure"""
        # Mock the database connection
        with patch('code.routers.health.engine') as mock_engine:
            mock_connection = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchone.return_value = [1]
            mock_connection.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_connection
            
            with patch('code.routers.health.scheduler', mock_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 200
                
                data = response.json()
                
                # Check required fields
                required_fields = ["status", "timestamp", "version", "checks"]
                for field in required_fields:
                    assert field in data
                
                # Check checks structure
                required_checks = ["api", "database", "scheduler"]
                for check in required_checks:
                    assert check in data["checks"]
                
                # Check data types
                assert isinstance(data["status"], str)
                assert isinstance(data["timestamp"], str)
                assert isinstance(data["version"], str)
                assert isinstance(data["checks"], dict)
                assert isinstance(data["scheduler_jobs"], int)
    
    def test_simple_health_check_response_structure(self):
        """Test that simple health check response has the correct structure"""
        response = client.get("/v1/health/simple")
        assert response.status_code == 200
        
        data = response.json()
        
        # Check required fields
        required_fields = ["status", "timestamp", "version"]
        for field in required_fields:
            assert field in data
        
        # Check data types
        assert isinstance(data["status"], str)
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["version"], str)
        
        # Check values
        assert data["status"] == "healthy"
        assert data["version"] == "0.3"
