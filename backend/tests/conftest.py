import pytest
from fastapi.testclient import TestClient
from main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def api_key_header():
    """Provide API key header for authenticated requests."""
    return {"X-API-Key": "test_api_key"}