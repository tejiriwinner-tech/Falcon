"""
Falcon Phase 4.3.9 — Runtime Observability Schemas
Read-only diagnostics payloads. No credentials. No API keys. No internal URLs.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class RuntimeProviderStats(BaseModel):
    """Rolling runtime statistics for one provider."""
    providerId: str
    providerName: str
    totalRequests: int
    successfulRequests: int
    failedRequests: int
    successRate: float
    uptimePercent: float
    avgLatencyMs: float
    p95LatencyMs: float
    cacheHits: int
    cacheMisses: int
    cacheHitRate: float
    circuitOpens: int
    circuitCloses: int
    failovers: int
    lastSuccessAt: Optional[str] = None
    lastFailureAt: Optional[str] = None
    firstSeenAt: str


class RuntimeProviderHealth(BaseModel):
    """Live health snapshot for one provider (combines analytics + live metadata)."""
    providerId: str
    providerName: str
    status: str
    health: str
    circuitBreakerState: str
    successRate: float
    avgLatencyMs: float
    p95LatencyMs: float
    consecutiveFailures: int = 0
    consecutiveSuccesses: int = 0
    http429Count: int = 0
    recoveryCount: int = 0
    circuitOpenCount: int = 0
    lastSuccessAt: Optional[datetime] = None
    lastFailureAt: Optional[datetime] = None
    circuitRetryInSeconds: Optional[float] = None


class RuntimeTimelineEvent(BaseModel):
    """One provider lifecycle event."""
    eventType: str
    providerId: str
    providerName: str
    symbol: Optional[str] = None
    detail: str = ""
    timestamp: str
    timeLabel: str


class RuntimeSummary(BaseModel):
    """Aggregate runtime summary across all providers."""
    uptimeSeconds: float
    startedAt: str
    totalRequests: int
    successfulRequests: int
    failedRequests: int
    overallSuccessRate: float
    totalFailovers: int
    totalCacheHits: int
    totalCacheMisses: int
    overallCacheHitRate: float
    circuitBreakerOpens: int
    timelineEventCount: int
    providerCount: int


class RuntimeProvidersResponse(BaseModel):
    """Response for GET /runtime/providers."""
    summary: RuntimeSummary
    providers: List[RuntimeProviderHealth]
    analytics: List[RuntimeProviderStats]
    cacheStats: Dict[str, Any]
    performanceMetrics: Dict[str, Any]
    generatedAt: datetime


class RuntimeEventsResponse(BaseModel):
    """Response for GET /runtime/events."""
    events: List[RuntimeTimelineEvent]
    eventCounts: Dict[str, int]
    totalEvents: int
    generatedAt: datetime


class RuntimeExportResponse(BaseModel):
    """Response for GET /runtime/export."""
    exportedAt: str
    summary: Dict[str, Any]
    providerStats: List[Dict[str, Any]]
    recentTimeline: List[Dict[str, Any]]
    eventCounts: Dict[str, int]


class RuntimeMetrics(BaseModel):
    """Compact runtime metrics embedded in DashboardResponse (Phase 4.3.9)."""
    summary: RuntimeSummary
    currentProvider: str = "Unknown"
    topProviderBySuccessRate: str = "Unknown"
    totalFailoversToday: int = 0
    cacheHitRate: float = 0.0
    avgColdRequestMs: float = 0.0
    avgWarmRequestMs: float = 0.0


# ── Phase 4.3.10 — Provider Resilience & Recovery ─────────────────────

class ProviderQualityScoreResponse(BaseModel):
    """Dynamic provider quality score with component breakdown."""
    providerId: str
    providerName: str
    manualPriority: int
    qualityScore: float
    successRate: float
    latencyScore: float
    stabilityScore: float
    cacheEfficiency: float
    recoveryReliability: float
    effectiveRank: int


class HealthTrendData(BaseModel):
    """Health trend for a time window."""
    windowName: str  # "5min" | "30min" | "24hr"
    timestamp: datetime
    avgLatencyMs: float
    successRate: float
    circuitOpens: int
    recoveries: int
    failovers: int
    cacheHitRatio: float


class RuntimeAlertResponse(BaseModel):
    """Runtime alert record."""
    alertType: str
    providerId: str
    providerName: str
    message: str
    severity: str  # "INFO" | "WARNING" | "CRITICAL"
    timestamp: datetime
    metadata: Dict[str, Any] = {}


class RuntimeAlertsResponse(BaseModel):
    """Response for GET /runtime/alerts."""
    alerts: List[RuntimeAlertResponse]
    alertCounts: Dict[str, int]
    totalAlerts: int
    generatedAt: datetime


class RuntimeRankingResponse(BaseModel):
    """Response for GET /runtime/ranking."""
    qualityScores: List[ProviderQualityScoreResponse]
    generatedAt: datetime


class ProviderHealthTrends(BaseModel):
    """Health trends for one provider across multiple time windows."""
    providerId: str
    providerName: str
    trends: Dict[str, HealthTrendData]  # "5min" → HealthTrendData, etc.
    generatedAt: datetime


class RuntimeTrendsResponse(BaseModel):
    """Response for GET /runtime/trends."""
    providerTrends: List[ProviderHealthTrends]
    generatedAt: datetime


class RuntimeResilienceExportResponse(BaseModel):
    """Extended export response including resilience analytics (Phase 4.3.10)."""
    exportedAt: str
    summary: Dict[str, Any]
    providerStats: List[Dict[str, Any]]
    providerQualityScores: List[Dict[str, Any]]
    providerRankings: Dict[str, Any]
    alertHistory: List[Dict[str, Any]]
    circuitHistory: Dict[str, Any]
    healthTrends: Dict[str, Any]
    recoveryStatistics: Dict[str, Any]
    recentTimeline: List[Dict[str, Any]]
    eventCounts: Dict[str, int]
