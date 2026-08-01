from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict, Any


class ProviderStatus(str, Enum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    RATE_LIMITED = "RATE_LIMITED"
    OFFLINE = "OFFLINE"


class ProviderType(str, Enum):
    PRICE = "PRICE"
    NEWS = "NEWS"
    ECONOMIC_CALENDAR = "ECONOMIC_CALENDAR"
    SENTIMENT = "SENTIMENT"
    TECHNICAL = "TECHNICAL"
    MARKET_METADATA = "MARKET_METADATA"


class ProviderHealth(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ProviderCapability(str, Enum):
    LIVE_PRICE = "LIVE_PRICE"
    HISTORICAL_CANDLES = "HISTORICAL_CANDLES"
    SPREAD = "SPREAD"
    MARKET_SESSION = "MARKET_SESSION"
    ECONOMIC_EVENTS = "ECONOMIC_EVENTS"
    NEWS_FEED = "NEWS_FEED"
    SENTIMENT = "SENTIMENT"
    SYMBOL_INFORMATION = "SYMBOL_INFORMATION"


class ProviderLatency(BaseModel):
    averageMs: float
    lastRequestMs: float


class ProviderStatistics(BaseModel):
    totalRequests: int
    successfulRequests: int
    failedRequests: int
    successRate: float

    # ── Phase 4.3.7 fields ────────────────────────────────────────────
    consecutiveFailures: int = 0
    http429Count: int = 0
    timeoutCount: int = 0
    lastSuccessAt: Optional[datetime] = None
    lastFailureAt: Optional[datetime] = None
    circuitBreakerState: str = "CLOSED"          # CLOSED | OPEN | HALF_OPEN
    circuitRetryInSeconds: Optional[float] = None  # seconds until HALF_OPEN trial

    # ── Phase 4.3.8 health-score fields ──────────────────────────────
    uptimePercent: float = 100.0            # % of requests that succeeded
    avgSuccessLatencyMs: float = 0.0        # average latency of successful requests
    avgFailureLatencyMs: float = 0.0        # average latency of failed requests
    consecutiveSuccesses: int = 0           # unbroken successful request streak
    recoveryCount: int = 0                  # times circuit went OPEN → CLOSED
    circuitOpenCount: int = 0               # times circuit opened
    circuitCloseCount: int = 0              # times circuit closed (recoveries)
    lastSuccessfulQuoteAt: Optional[datetime] = None   # last quote returned
    lastFailedRequestAt: Optional[datetime] = None     # last request that failed


class ProviderMetadata(BaseModel):
    providerId: str
    providerName: str
    providerVersion: str
    providerType: ProviderType
    capabilities: List[ProviderCapability]
    status: ProviderStatus
    health: ProviderHealth


class ProviderSnapshot(BaseModel):
    providerId: str
    latency: ProviderLatency
    statistics: ProviderStatistics
    metadata: ProviderMetadata
    lastHeartbeat: Optional[datetime] = None
    lastSuccessfulUpdate: Optional[datetime] = None


class ProviderSummary(BaseModel):
    totalProviders: int
    online: int
    degraded: int
    offline: int


# ── Phase 4.3.8 — Dashboard health detail ─────────────────────────────────────
class ProviderHealthDetail(BaseModel):
    """Lightweight per-provider health summary exposed in the dashboard.
    Never includes API keys, internal URLs, or credentials.
    """
    providerId: str
    providerName: str
    status: str                              # ProviderStatus value
    health: str                              # ProviderHealth value
    circuitBreakerState: str                 # CLOSED | OPEN | HALF_OPEN
    successRate: float
    avgLatencyMs: float
    lastSuccessAt: Optional[datetime] = None
    lastFailureAt: Optional[datetime] = None
    circuitRetryInSeconds: Optional[float] = None


class ProviderListResponse(BaseModel):
    providers: List[ProviderSnapshot]
    summary: ProviderSummary
    lastUpdated: datetime


class MarketQuote(BaseModel):
    symbol: str
    bid: float
    ask: float
    spread: float
    spreadPips: float
    mid: float
    timestamp: datetime
    providerId: str
    fresh: bool
    session: str


class MarketDataSnapshot(BaseModel):
    symbol: str
    normalizedSymbol: str
    quote: MarketQuote
    pipelineStage: str = "PROVIDER"
    fetchedAt: datetime
    cacheTtlSeconds: int
    cacheHit: bool
