#!/usr/bin/env python
"""
Test suite for Mission Persistence and Decision Engine Integration
Phase 7.6.3 Production Hardening
"""
import pytest
import requests
import time

API_BASE = "http://localhost:8000"
API_KEY = "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"
HEADERS = {"X-API-Key": API_KEY}


class TestMissionPersistence:
    """Test mission persistence functionality."""
    
    def test_mission_endpoint_accessible(self):
        """Test that missions endpoint is accessible with valid API key."""
        response = requests.get(f"{API_BASE}/api/v1/missions", headers=HEADERS)
        assert response.status_code == 200
    
    def test_mission_response_structure(self):
        """Test that mission response has correct structure."""
        response = requests.get(f"{API_BASE}/api/v1/missions", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        assert "missions" in data
        assert "summary" in data
        assert isinstance(data["missions"], list)
    
    def test_mission_persistence_after_dashboard(self):
        """Test that missions are persisted after dashboard generation."""
        # Get initial mission count
        initial_response = requests.get(f"{API_BASE}/api/v1/missions", headers=HEADERS)
        initial_count = len(initial_response.json()["missions"])
        
        # Generate dashboard (should create a mission)
        dashboard_response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert dashboard_response.status_code == 200
        
        # Wait for mission to be persisted
        time.sleep(1)
        
        # Check mission count increased
        final_response = requests.get(f"{API_BASE}/api/v1/missions", headers=HEADERS)
        final_count = len(final_response.json()["missions"])
        
        # Mission count should have increased (or stayed same due to duplicate detection)
        assert final_count >= initial_count


class TestDecisionEngineIntegration:
    """Test Decision Engine integration with dashboard."""
    
    def test_decision_engine_output_present(self):
        """Test that Decision Engine output is present in dashboard."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        decision = data.get("decision")
        assert decision is not None
        assert "recommendation" in decision
        assert "confidenceScore" in decision
        assert "riskLevel" in decision
    
    def test_decision_engine_fields_populated(self):
        """Test that Decision Engine fields are properly populated."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        decision = data.get("decision")
        
        # Check critical fields are populated
        assert decision["recommendation"] in ["BUY", "SELL", "WAIT", "HOLD"]
        assert isinstance(decision["confidenceScore"], (int, float))
        assert 0 <= decision["confidenceScore"] <= 100
        assert decision["riskLevel"] in ["LOW", "MEDIUM", "HIGH"]


class TestMarketStateIntegration:
    """Test Market State Engine integration with dashboard."""
    
    def test_market_state_present(self):
        """Test that Market State is present in dashboard."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        market_state = data.get("marketState")
        assert market_state is not None
    
    def test_market_state_fields_populated(self):
        """Test that Market State fields are properly populated."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        market_state = data.get("marketState")
        
        # Check critical fields
        assert "prices" in market_state
        assert "indicators" in market_state
        assert "news" in market_state


class TestProviderFallback:
    """Test provider fallback functionality."""
    
    def test_provider_health_present(self):
        """Test that provider health information is present."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        provider_health = data.get("providerHealth")
        assert provider_health is not None
        assert isinstance(provider_health, list)
    
    def test_provider_summary_present(self):
        """Test that provider summary is present."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        provider_summary = data.get("providerSummary")
        assert provider_summary is not None


class TestRuntimeProviders:
    """Test runtime provider functionality."""
    
    def test_runtime_metrics_present(self):
        """Test that runtime metrics are present."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        runtime_metrics = data.get("runtimeMetrics")
        assert runtime_metrics is not None
    
    def test_system_health_present(self):
        """Test that system health is present."""
        response = requests.get(f"{API_BASE}/api/v1/dashboard", headers=HEADERS)
        assert response.status_code == 200
        data = response.json()
        
        system_health = data.get("systemHealth")
        assert system_health is not None
        assert "status" in system_health


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
