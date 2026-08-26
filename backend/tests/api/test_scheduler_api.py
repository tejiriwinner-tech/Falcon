"""
Integration tests for Scheduler API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_get_scheduler_status(client):
    """Test GET /api/v1/scheduler/status endpoint."""
    response = client.get("/api/v1/scheduler/status", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert "is_running" in data
    assert "scan_interval_seconds" in data
    assert "markets_monitored" in data
    assert "timeframes_monitored" in data
    assert "total_combinations" in data
    assert "last_scan_time" in data
    assert "consecutive_failures" in data
    assert "max_consecutive_failures" in data


def test_get_scheduler_statistics(client):
    """Test GET /api/v1/scheduler/statistics endpoint."""
    response = client.get("/api/v1/scheduler/statistics", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert "total_scans" in data
    assert "successful_scans" in data
    assert "failed_scans" in data
    assert "signals_generated" in data
    assert "signals_approved" in data
    assert "signals_rejected" in data
    assert "duplicates_prevented" in data
    assert "signals_expired" in data
    assert "approval_rate" in data
    assert "avg_scan_time_ms" in data
    assert "uptime_seconds" in data


def test_get_repository_statistics(client):
    """Test GET /api/v1/scheduler/repository-stats endpoint."""
    response = client.get("/api/v1/scheduler/repository-stats", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert "total_signals" in data
    assert "active_signals" in data
    assert "expired_signals" in data
    assert "symbol_counts" in data


def test_scheduler_status_structure(client):
    """Test that scheduler status has correct structure."""
    response = client.get("/api/v1/scheduler/status", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    data = response.json()
    
    # Check types
    assert isinstance(data["is_running"], bool)
    assert isinstance(data["scan_interval_seconds"], int)
    assert isinstance(data["markets_monitored"], list)
    assert isinstance(data["timeframes_monitored"], list)
    assert isinstance(data["total_combinations"], int)
    assert isinstance(data["consecutive_failures"], int)
    assert isinstance(data["max_consecutive_failures"], int)


def test_scheduler_statistics_structure(client):
    """Test that scheduler statistics has correct structure."""
    response = client.get("/api/v1/scheduler/statistics", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    data = response.json()
    
    # Check types
    assert isinstance(data["total_scans"], int)
    assert isinstance(data["successful_scans"], int)
    assert isinstance(data["failed_scans"], int)
    assert isinstance(data["signals_generated"], int)
    assert isinstance(data["signals_approved"], int)
    assert isinstance(data["signals_rejected"], int)
    assert isinstance(data["duplicates_prevented"], int)
    assert isinstance(data["signals_expired"], int)
    assert isinstance(data["approval_rate"], (int, float))
    assert isinstance(data["uptime_seconds"], (int, float))


def test_repository_statistics_structure(client):
    """Test that repository statistics has correct structure."""
    response = client.get("/api/v1/scheduler/repository-stats", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    data = response.json()
    
    # Check types
    assert isinstance(data["total_signals"], int)
    assert isinstance(data["active_signals"], int)
    assert isinstance(data["expired_signals"], int)
    assert isinstance(data["symbol_counts"], dict)


def test_scheduler_endpoints_404_on_invalid_path(client):
    """Test that invalid scheduler paths return 404."""
    response = client.get("/api/v1/scheduler/invalid")
    assert response.status_code == 404
