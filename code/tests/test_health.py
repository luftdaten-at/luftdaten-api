import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from main import app
from apscheduler.schedulers.background import BackgroundScheduler
from unittest.mock import patch, MagicMock, PropertyMock, AsyncMock
from datetime import datetime

client = TestClient(app)


@pytest.fixture
def mock_scheduler():
    """Create a mock scheduler for testing"""
    scheduler = MagicMock(spec=BackgroundScheduler)
    scheduler.running = True
    scheduler.get_jobs.return_value = [MagicMock()]
    return scheduler


class TestHealthRouter:

    def test_simple_health_check(self):
        response = client.get("/v1/health/simple")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.3"
        assert "timestamp" in data

        datetime.fromisoformat(data["timestamp"])

    def test_comprehensive_health_check_all_healthy(self, mock_scheduler):
        with patch('routers.health.database_health_check', new_callable=AsyncMock) as mock_db:
            mock_db.return_value = None

            with patch('routers.health.scheduler', mock_scheduler):
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
        with patch(
            'routers.health.database_health_check',
            new_callable=AsyncMock,
            side_effect=Exception("Database connection failed"),
        ):
            with patch('routers.health.scheduler', mock_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503

                data = response.json()["detail"]
                assert data["status"] == "unhealthy"
                assert data["checks"]["database"] == "unhealthy"
                assert "database_error" in data
                assert data["database_error"] == "Database connection failed"

    def test_comprehensive_health_check_scheduler_unhealthy(self):
        with patch('routers.health.database_health_check', new_callable=AsyncMock):
            unhealthy_scheduler = MagicMock(spec=BackgroundScheduler)
            unhealthy_scheduler.running = False

            with patch('routers.health.scheduler', unhealthy_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503

                data = response.json()["detail"]
                assert data["checks"]["scheduler"] == "unhealthy"

    def test_comprehensive_health_check_scheduler_none(self):
        with patch('routers.health.database_health_check', new_callable=AsyncMock):
            with patch('routers.health.scheduler', None):
                response = client.get("/v1/health/")
                assert response.status_code == 503

                data = response.json()["detail"]
                assert data["checks"]["scheduler"] == "unhealthy"

    def test_comprehensive_health_check_scheduler_exception(self):
        with patch('routers.health.database_health_check', new_callable=AsyncMock):
            broken_scheduler = MagicMock(spec=BackgroundScheduler)
            type(broken_scheduler).running = PropertyMock(side_effect=Exception("Scheduler error"))

            with patch('routers.health.scheduler', broken_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503

                data = response.json()["detail"]
                assert "scheduler_error" in data

    def test_comprehensive_health_check_multiple_jobs(self, mock_scheduler):
        mock_scheduler.get_jobs.return_value = [MagicMock(), MagicMock(), MagicMock()]

        with patch('routers.health.database_health_check', new_callable=AsyncMock):
            with patch('routers.health.scheduler', mock_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 200
                assert response.json()["scheduler_jobs"] == 3

    def test_comprehensive_health_check_database_and_scheduler_unhealthy(self):
        with patch(
            'routers.health.database_health_check',
            new_callable=AsyncMock,
            side_effect=Exception("Database connection failed"),
        ):
            unhealthy_scheduler = MagicMock(spec=BackgroundScheduler)
            unhealthy_scheduler.running = False

            with patch('routers.health.scheduler', unhealthy_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 503

                data = response.json()["detail"]
                assert data["checks"]["database"] == "unhealthy"
                assert data["checks"]["scheduler"] == "unhealthy"

    def test_health_check_response_structure(self, mock_scheduler):
        with patch('routers.health.database_health_check', new_callable=AsyncMock):
            with patch('routers.health.scheduler', mock_scheduler):
                response = client.get("/v1/health/")
                assert response.status_code == 200

                data = response.json()
                for field in ["status", "timestamp", "version", "checks"]:
                    assert field in data
                for check in ["api", "database", "scheduler"]:
                    assert check in data["checks"]
                assert isinstance(data["scheduler_jobs"], int)

    def test_simple_health_check_response_structure(self):
        response = client.get("/v1/health/simple")
        assert response.status_code == 200
        data = response.json()
        for field in ["status", "timestamp", "version"]:
            assert field in data
        assert data["status"] == "healthy"
        assert data["version"] == "0.3"
