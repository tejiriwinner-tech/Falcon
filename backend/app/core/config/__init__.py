"""
Falcon Config Package — re-exports settings and provider_settings for convenience.
"""
from app.core.config.settings import settings
from app.core.config.provider_settings import (
    PRIMARY_PROVIDER,
    FALLBACK_PROVIDER,
    TERTIARY_PROVIDER,
    CACHE_TTL_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    MAX_RETRIES,
    ENABLE_PROVIDER_FAILOVER,
)

__all__ = [
    "settings",
    "PRIMARY_PROVIDER",
    "FALLBACK_PROVIDER",
    "TERTIARY_PROVIDER",
    "CACHE_TTL_SECONDS",
    "REQUEST_TIMEOUT_SECONDS",
    "MAX_RETRIES",
    "ENABLE_PROVIDER_FAILOVER",
]
