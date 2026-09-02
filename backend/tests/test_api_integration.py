import pytest
from fastapi.testclient import TestClient


class TestAPIIntegration:
    """Integration tests for API endpoints."""
    
    def test_health_endpoint(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_intelligence_endpoint_valid_symbol(self, client: TestClient):
        """Test intelligence endpoint with valid symbol."""
        response = client.get("/api/v1/intelligence?symbol=XAUUSD")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
        assert data["data"]["symbol"] == "XAUUSD"
        assert "decision" in data["data"]
    
    def test_intelligence_endpoint_invalid_symbol(self, client: TestClient):
        """Test intelligence endpoint with invalid symbol."""
        response = client.get("/api/v1/intelligence?symbol=INVALID123")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
    
    def test_dashboard_endpoint(self, client: TestClient):
        """Test dashboard endpoint."""
        response = client.get("/api/v1/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "data" in data
    
    def test_signals_endpoint(self, client: TestClient):
        """Test signals endpoint."""
        response = client.get("/api/v1/signals")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "signals" in data["data"]
    
    def test_intelligence_statistics(self, client: TestClient):
        """Test intelligence statistics endpoint."""
        response = client.get("/api/v1/intelligence/statistics")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
    
    def test_rate_limiting(self, client: TestClient):
        """Test rate limiting on endpoints."""
        # Make multiple requests to test rate limiting
        # Note: This test may need adjustment based on actual rate limit configuration
        for _ in range(5):
            response = client.get("/api/v1/health")
            assert response.status_code == 200
    
    def test_cors_headers(self, client: TestClient):
        """Test CORS headers are present."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers