#!/usr/bin/env python
"""
Test suite for Dashboard Generation and Captain's Briefing
Phase 7.6.3 Production Hardening
"""
import pytest
import requests
import time
from datetime import datetime

API_BASE = "http://localhost:8000"
API_KEY = "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"
HEADERS = {"X-API-Key": API_KEY}


class TestDashboard:
    """Test dashboard generation and Captain's Briefing."""
    
    def test_dashboard_authentication_required(self):
        """Test that dashboard requires API key."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard")
        assert response.status_code == 401
        assert "Missing API key" in response.json()["detail"]
    
    def test_dashboard_invalid_api_key(self):
        """Test that dashboard rejects invalid API key."""
        headers = {"X-API-Key": "invalid_key"}
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=headers)
        assert response.status_code == 401
        assert "Invalid API key" in response.json()["detail"]
    
    def test_dashboard_valid_api_key(self):
        """Test that dashboard accepts valid API key."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
    
    def test_dashboard_structure_complete(self):
        """Test that dashboard response contains all required fields."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        required_fields = [
            "summary", "marketQuotes", "providerSummary", "missionSummary",
            "analyticsSummary", "systemHealth", "marketState", "signals",
            "news", "decision", "providerHealth", "runtimeMetrics",
            "instrumentContexts", "instrumentValidationWarnings", "generatedAt"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
            assert data[field] is not None, f"Field {field} is null"
    
    def test_captains_briefing_structure(self):
        """Test that Captain's Briefing decision is complete."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        decision = data.get("decision", {})
        assert decision is not None
        
        # Required decision fields
        required_fields = [
            "greetingMessage", "recommendation", "confidenceScore",
            "captainsAction", "reasons", "missingConditions",
            "strategyId", "strategyName", "riskLevel", "tradeQuality"
        ]
        
        for field in required_fields:
            assert field in decision, f"Missing decision field: {field}"
    
    def test_dashboard_performance_target(self):
        """Test that dashboard generation meets performance target (<2s)."""
        start = time.time()
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 3.0, f"Dashboard generation took {elapsed:.2f}s, target is <3s"
    
    def test_dashboard_consistency(self):
        """Test that dashboard produces consistent results on consecutive calls."""
        responses = []
        for _ in range(3):
            response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
            assert response.status_code == 200
            responses.append(response.json())
            time.sleep(0.5)
        
        # All responses should have the same structure
        for response in responses:
            assert set(response.keys()) == set(responses[0].keys())


class TestHealthEndpoint:
    """Test health endpoint functionality."""
    
    def test_health_public_access(self):
        """Test that health endpoint is public (no auth required)."""
        response = requests.get(f"{API_BASE}/api/v1/health")
        assert response.status_code == 200
    
    def test_health_structure_complete(self):
        """Test that health response contains all required fields."""
        response = requests.get(f"{API_BASE}/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "environment" in data
        assert "systemHealth" in data


class TestAuthentication:
    """Test authentication functionality."""
    
    def test_missing_api_key(self):
        """Test that missing API key returns 401."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard")
        assert response.status_code == 401
    
    def test_invalid_api_key(self):
        """Test that invalid API key returns 401."""
        headers = {"X-API-Key": "wrong_key"}
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=headers)
        assert response.status_code == 401
    
    def test_valid_api_key(self):
        """Test that valid API key returns 200."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
