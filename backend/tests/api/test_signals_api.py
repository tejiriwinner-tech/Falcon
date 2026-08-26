"""
Integration tests for Signals API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_get_live_signals(client):
    """Test GET /api/v1/signals/live endpoint."""
    response = client.get("/api/v1/signals/live", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)


def test_get_latest_signal(client):
    """Test GET /api/v1/signals/latest endpoint."""
    response = client.get("/api/v1/signals/latest", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    # Response can be None or a signal object
    data = response.json()
    assert data is None or isinstance(data, dict)


def test_get_latest_signal_with_symbol_filter(client):
    """Test GET /api/v1/signals/latest with symbol filter."""
    response = client.get("/api/v1/signals/latest?symbol=XAUUSD", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert data is None or isinstance(data, dict)


def test_get_latest_signal_with_timeframe_filter(client):
    """Test GET /api/v1/signals/latest with timeframe filter."""
    response = client.get("/api/v1/signals/latest?timeframe=H1", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert data is None or isinstance(data, dict)


def test_get_signal_history(client):
    """Test GET /api/v1/signals/history endpoint."""
    response = client.get("/api/v1/signals/history", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)


def test_get_signal_history_with_symbol_filter(client):
    """Test GET /api/v1/signals/history with symbol filter."""
    response = client.get("/api/v1/signals/history?symbol=XAUUSD", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)


def test_get_signal_history_with_status_filter(client):
    """Test GET /api/v1/signals/history with status filter."""
    response = client.get("/api/v1/signals/history?status=ACTIVE", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)


def test_get_signal_history_with_timeframe_filter(client):
    """Test GET /api/v1/signals/history with timeframe filter."""
    response = client.get("/api/v1/signals/history?timeframe=H1", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)


def test_get_signal_history_with_limit(client):
    """Test GET /api/v1/signals/history with limit parameter."""
    response = client.get("/api/v1/signals/history?limit=10", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 10


def test_get_signal_history_multiple_filters(client):
    """Test GET /api/v1/signals/history with multiple filters."""
    response = client.get("/api/v1/signals/history?symbol=XAUUSD&status=ACTIVE&timeframe=H1&limit=5", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    assert response.status_code == 200
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5


def test_signals_endpoints_404_on_invalid_path(client):
    """Test that invalid signals paths return 404."""
    response = client.get("/api/v1/signals/invalid")
    assert response.status_code == 404


def test_live_signals_response_structure(client):
    """Test that live signals response has correct structure."""
    response = client.get("/api/v1/signals/live", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    data = response.json()
    
    if len(data) > 0:
        signal = data[0]
        assert "signalId" in signal
        assert "symbol" in signal
        assert "timeframe" in signal
        assert "signalType" in signal
        assert "entryPrice" in signal
        assert "stopLoss" in signal
        assert "status" in signal
        assert "generatedAt" in signal


def test_signal_history_response_structure(client):
    """Test that signal history response has correct structure."""
    response = client.get("/api/v1/signals/history", headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"})
    data = response.json()
    
    if len(data) > 0:
        signal = data[0]
        assert "signalId" in signal
        assert "symbol" in signal
        assert "timeframe" in signal
        assert "signalType" in signal
        assert "entryPrice" in signal
        assert "stopLoss" in signal
        assert "status" in signal
        assert "generatedAt" in signal
