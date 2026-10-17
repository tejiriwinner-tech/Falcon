"""
Falcon Provider Framework — Provider Settings Configuration
Centralized configuration for market data providers, caching, and failover behavior.
"""

PRIMARY_PROVIDER: str = "oanda"
FALLBACK_PROVIDER: str = "fmp"
TERTIARY_PROVIDER: str = "mock_provider"

CACHE_TTL_SECONDS: int = 300
REQUEST_TIMEOUT_SECONDS: int = 5
MAX_RETRIES: int = 3
ENABLE_PROVIDER_FAILOVER: bool = True

# ── Circuit Breaker Configuration ─────────────────────────────────────────────
# Number of consecutive failures before the circuit opens (blocks live requests).
CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3

# Seconds to wait in OPEN state before allowing a single trial request (HALF_OPEN).
CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 60

# ── Adaptive Cache TTL Tiers (Phase 4.3.8) ────────────────────────────────────
# TTL selected automatically based on the supplying provider's success rate and
# circuit breaker state. Paced to prevent premature exhaustion of the daily quota.
CACHE_TTL_EXCELLENT_SECONDS: int = 360   # success rate > 98 % (6 minutes)
CACHE_TTL_GOOD_SECONDS: int = 300        # success rate 90–98 % (5 minutes)
CACHE_TTL_POOR_SECONDS: int = 180        # success rate < 90 % (3 minutes)
CACHE_TTL_RATE_LIMITED_SECONDS: int = 360  # circuit OPEN / RATE_LIMITED
