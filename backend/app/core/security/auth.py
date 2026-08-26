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
    # If no API key configured, skip authentication (development mode)
    if not settings.FALCON_API_KEY:
        return "dev_mode"
    
    # If API key is configured but not provided
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Provide X-API-Key header."
        )
    
    # Verify API key
    if api_key != settings.FALCON_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    return api_key