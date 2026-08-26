"""
Focused regression tests for Phase 7.4 M2 security hardening.
"""
import logging
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings


@pytest.fixture
def client():
    return TestClient(app)


class TestApiKeyAuthentication:
    def test_missing_api_key_returns_401(self, client):
        response = client.get("/api/v1/runtime/instruments")
        assert response.status_code == 401
        assert response.json()["detail"] == "Missing API key. Provide it in the X-API-Key header."

    def test_invalid_api_key_returns_401(self, client):
        response = client.get(
            "/api/v1/runtime/instruments",
            headers={"X-API-Key": "invalid-key"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid API key."

    def test_valid_api_key_succeeds(self, client):
        response = client.get(
            "/api/v1/runtime/instruments",
            headers={"X-API-Key": "falcon_dev_key_7a3f9c2e8b1d4f6a0c5e9b7d2f8a1c3e"},
        )
        assert response.status_code == 200

    def test_health_endpoint_remains_public(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestCorsHardening:
    def test_allowed_origin_preflight_succeeds(self, client):
        response = client.options(
            "/api/v1/runtime/instruments",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_disallowed_origin_has_no_allow_origin(self, client):
        response = client.get(
            "/api/v1/runtime/instruments",
            headers={"X-API-Key": "phase74-test-key", "Origin": "https://evil.example"},
        )
        assert response.status_code in (200, 401, 429)
        assert response.headers.get("access-control-allow-origin") != "https://evil.example"


class TestRateLimiting:
    def test_rate_limit_exceeded_returns_429(self, client):
        with patch.object(settings, "RATE_LIMIT_PER_MINUTE", 1):
            first = client.get(
                "/api/v1/runtime/instruments",
                headers={"X-API-Key": "phase74-test-key"},
            )
            assert first.status_code in (200, 429)
            second = client.get(
                "/api/v1/runtime/instruments",
                headers={"X-API-Key": "phase74-test-key"},
            )
            assert second.status_code == 429
            assert second.json()["status_code"] == 429
            assert "Retry-After" in second.headers

    def test_health_endpoint_exempt_from_rate_limit(self, client):
        with patch.object(settings, "RATE_LIMIT_PER_MINUTE", 1):
            for _ in range(3):
                response = client.get("/api/v1/health")
                assert response.status_code == 200


class TestRequestCorrelation:
    def test_request_id_generated_when_missing(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"]

    def test_request_id_preserved_when_provided(self, client):
        request_id = "test-request-id-123"
        response = client.get("/api/v1/health", headers={"X-Request-ID": request_id})
        assert response.headers["X-Request-ID"] == request_id

    def test_process_time_header_present(self, client):
        response = client.get("/api/v1/health")
        assert "X-Process-Time" in response.headers


class TestSecureLogging:
    def test_sensitive_headers_not_logged(self, caplog):
        caplog.set_level(logging.INFO, logger="app.middleware.logging_middleware")
        client = TestClient(app)
        client.get(
            "/api/v1/runtime/instruments",
            headers={"X-API-Key": "super-secret-key"},
        )
        for record in caplog.records:
            assert "super-secret-key" not in record.getMessage()
            assert "X-API-Key" not in record.getMessage()
