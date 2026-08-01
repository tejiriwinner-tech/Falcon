"""
Falcon Provider Framework — Provider Settings Configuration
Centralized configuration for market data providers, caching, and failover behavior.
"""

PRIMARY_PROVIDER: str = "twelve_data"
FALLBACK_PROVIDER: str = "yahoo_finance"
TERTIARY_PROVIDER: str = "mock_price"

CACHE_TTL_SECONDS: int = 10
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
# circuit breaker state.  Higher-reliability providers earn longer TTLs; rate-limited
# or degraded providers use shorter TTLs so Falcon re-checks sooner.
#
# Rate-limited state uses a longer TTL to avoid hammering the provider further.
CACHE_TTL_EXCELLENT_SECONDS: int = 30   # success rate > 98 %
CACHE_TTL_GOOD_SECONDS: int = 20        # success rate 90–98 %
CACHE_TTL_POOR_SECONDS: int = 10        # success rate < 90 %
CACHE_TTL_RATE_LIMITED_SECONDS: int = 60  # circuit OPEN / RATE_LIMITED
