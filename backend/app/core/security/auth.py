import secrets
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from typing import Optional
from app.core.config.settings import settings

# API Key header authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> str:
    """
    Verify API key for authentication.
    
    If FALCON_API_KEY is set in environment, it must match.
    If not set, authentication is disabled (development mode).
    """
    expected = getattr(settings, "FALCON_API_KEY", None)
    require_key = bool(getattr(settings, "REQUIRE_API_KEY", False))

    # If no API key configured, skip authentication unless explicitly required
    if not expected:
        if require_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key authentication is not configured."
            )
        return "dev_mode"
    
    # If API key is configured but not provided
    if not api_key:
        if not require_key:
            return "dev_mode"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header."
        )
    
    # Verify API key using constant-time comparison
    if not secrets.compare_digest(str(api_key), str(expected)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    return api_key