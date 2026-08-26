"""
Falcon API Key Authentication Dependency (Phase 7.4 M2)

Provides a reusable FastAPI dependency that requires a valid API key
in the X-API-Key header. Returns 401 Unauthorized when the key is
missing or invalid.

Uses secrets.compare_digest for constant-time comparison to mitigate
timing attacks.
"""
import secrets
from fastapi import Header, HTTPException, status

from app.core.config import settings


def get_api_key(x_api_key: str = Header(None)) -> str:
    """Validate the X-API-Key header against the configured API key.

    Args:
        x_api_key: Value of the X-API-Key request header.

    Returns:
        The validated API key.

    Raises:
        HTTPException: 401 Unauthorized if the key is missing or invalid.
    """
    expected = settings.API_KEY

    # If no API key is configured, authentication cannot succeed.
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key authentication is not configured.",
        )

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it in the X-API-Key header.",
        )

    if not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    return x_api_key