"""
Falcon Phase 4.3.9 & 4.3.10 — Runtime Observability & Resilience API
======================================================================
GET /api/v1/runtime/providers  — provider analytics + live health
GET /api/v1/runtime/events     — timeline of recent provider events
GET /api/v1/runtime/export     — full downloadable diagnostics JSON

Phase 4.3.10 additions:
GET /api/v1/runtime/alerts     — runtime alert history
GET /api/v1/runtime/ranking    — provider quality scores & dynamic ranking
GET /api/v1/runtime/trends     — health trend windows (5min, 30min, 24hr)

Read-only. No secrets. No API keys. No internal URLs.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.core.providers import provider_analytics, provider_manager, provider_registry
from app.core.providers.cache import market_cache
from app.core.providers.provider_recovery_manager import provider_recovery_manager
from app.schemas.runtime import (
    RuntimeProvidersResponse,
    RuntimeEventsResponse,
    RuntimeExportResponse,
    RuntimeProviderHealth,
    RuntimeProviderStats,
    RuntimeTimelineEvent,
    RuntimeSummary,
    RuntimeAlertsResponse,
    RuntimeAlertResponse,
    RuntimeRankingResponse,
    ProviderQualityScoreResponse,
    RuntimeTrendsResponse,
    ProviderHealthTrends,
    HealthTrendData,
    RuntimeResilienceExportResponse,
    RuntimeInstrumentsResponse,
    InstrumentDetail,
    ProviderCoverageItem,
)


router = APIRouter(prefix="/runtime", tags=["runtime"])


def _build_provider_health_list():
    """Merge live provider metadata with rolling analytics stats."""
    snapshots  = provider_registry.get_all_snapshots()
    health_list = []
    for snap in snapshots:
        pid   = snap.metadata.providerId
        pname = snap.metadata.providerName
        stats = snap.statistics
        rolling = provider_analytics.get_stats(pid) or {}

        health_list.append(RuntimeProviderHealth(
            providerId=pid,
            providerName=pname,
            status=snap.metadata.status.value,
            health=snap.metadata.health.value,
            circuitBreakerState=stats.circuitBreakerState,
            successRate=stats.successRate,
            avgLatencyMs=snap.latency.averageMs,
            p95LatencyMs=rolling.get("p95LatencyMs", 0.0),
            consecutiveFailures=stats.consecutiveFailures,
            consecutiveSuccesses=stats.consecutiveSuccesses,
            http429Count=stats.http429Count,
            recoveryCount=stats.recoveryCount,
            circuitOpenCount=stats.circuitOpenCount,
            lastSuccessAt=stats.lastSuccessAt or stats.lastSuccessfulQuoteAt,
            lastFailureAt=stats.lastFailureAt or stats.lastFailedRequestAt,
            circuitRetryInSeconds=stats.circuitRetryInSeconds,
        ))
    return health_list


@router.get("/providers", response_model=RuntimeProvidersResponse)
def get_runtime_providers():
    """Return full provider analytics, live health, cache stats, and performance metrics."""
    provider_registry.heartbeat()
    now = datetime.now(timezone.utc)

    summary_dict = provider_analytics.get_summary()
    summary = RuntimeSummary(**summary_dict)

    all_rolling = provider_analytics.get_all_stats()
    analytics_list = [RuntimeProviderStats(**s) for s in all_rolling]

    health_list = _build_provider_health_list()
    pm_metrics  = provider_manager.get_performance_metrics()
    cache_stats = market_cache.stats

    return RuntimeProvidersResponse(
        summary=summary,
        providers=health_list,
        analytics=analytics_list,
        cacheStats=cache_stats,
        performanceMetrics=pm_metrics,
        generatedAt=now,
    )


@router.get("/events", response_model=RuntimeEventsResponse)
def get_runtime_events(
    limit: int = Query(default=100, ge=1, le=500,
                       description="Number of recent events to return (max 500)")
):
    """Return the most recent provider lifecycle events (newest first)."""
    now     = datetime.now(timezone.utc)
    raw     = provider_analytics.get_timeline(limit=limit)
    counts  = provider_analytics.get_event_counts()

    events = [
        RuntimeTimelineEvent(
            eventType=e["eventType"],
            providerId=e["providerId"],
            providerName=e["providerName"],
            symbol=e.get("symbol"),
            detail=e.get("detail", ""),
            timestamp=e["timestamp"],
            timeLabel=e["timeLabel"],
        )
        for e in raw
    ]

    return RuntimeEventsResponse(
        events=events,
        eventCounts=counts,
        totalEvents=len(raw),
        generatedAt=now,
    )


@router.get("/export")
def get_runtime_export():
    """Return a full diagnostics export as downloadable JSON.
    No credentials. No API keys. No internal URLs.
    """
    data = provider_analytics.export()
    # Add live performance metrics and cache stats
    data["performanceMetrics"] = provider_manager.get_performance_metrics()
    data["cacheStats"]         = market_cache.stats

    return JSONResponse(
        content=data,
        headers={
            "Content-Disposition": 'attachment; filename="falcon_runtime_export.json"',
            "Content-Type": "application/json",
        },
    )


# ──────────────────────────────────────────────────────────────────────────────
# Phase 4.3.10 — Resilience, Self-Healing & Intelligent Recovery
# ──────────────────────────────────────────────────────────────────────────────


@router.get("/alerts", response_model=RuntimeAlertsResponse)
def get_runtime_alerts(limit: int = Query(default=100, ge=1, le=500)):
    """Return runtime alerts from the recovery manager."""
    now = datetime.now(timezone.utc)
    alerts = provider_recovery_manager.get_alerts(limit=limit)
    alert_summary = provider_recovery_manager.get_alert_summary()

    return RuntimeAlertsResponse(
        alerts=[
            RuntimeAlertResponse(
                alertType=a.alert_type,
                providerId=a.provider_id,
                providerName=a.provider_name,
                message=a.message,
                severity=a.severity,
                timestamp=a.timestamp,
                metadata=a.metadata,
            )
            for a in alerts
        ],
        alertCounts=alert_summary.get("alertCounts", {}),
        totalAlerts=alert_summary.get("totalAlerts", 0),
        generatedAt=now,
    )


@router.get("/ranking", response_model=RuntimeRankingResponse)
def get_runtime_ranking():
    """Return provider quality scores and dynamic ranking."""
    now = datetime.now(timezone.utc)
    scores = provider_recovery_manager.get_quality_scores()

    return RuntimeRankingResponse(
        qualityScores=[
            ProviderQualityScoreResponse(
                providerId=s.provider_id,
                providerName=s.provider_name,
                manualPriority=s.manual_priority,
                qualityScore=s.quality_score,
                successRate=s.success_rate,
                latencyScore=s.latency_score,
                stabilityScore=s.stability_score,
                cacheEfficiency=s.cache_efficiency,
                recoveryReliability=s.recovery_reliability,
                effectiveRank=s.effective_rank,
            )
            for s in scores
        ],
        generatedAt=now,
    )


@router.get("/trends", response_model=RuntimeTrendsResponse)
def get_runtime_trends():
    """Return health trend windows (5min, 30min, 24hr) for all providers."""
    now = datetime.now(timezone.utc)
    snapshots = provider_registry.get_all_snapshots()
    provider_trends = []

    for snap in snapshots:
        provider_id = snap.metadata.providerId
        provider_name = snap.metadata.providerName
        trends = provider_recovery_manager.get_health_trends(provider_id)

        if trends:
            provider_trends.append(
                ProviderHealthTrends(
                    providerId=provider_id,
                    providerName=provider_name,
                    trends={
                        window_name: HealthTrendData(
                            windowName=trend.window_name,
                            timestamp=trend.timestamp,
                            avgLatencyMs=trend.avg_latency_ms,
                            successRate=trend.success_rate,
                            circuitOpens=trend.circuit_opens,
                            recoveries=trend.recoveries,
                            failovers=trend.failovers,
                            cacheHitRatio=trend.cache_hit_ratio,
                        )
                        for window_name, trend in trends.items()
                    },
                    generatedAt=now,
                )
            )

    return RuntimeTrendsResponse(
        providerTrends=provider_trends,
        generatedAt=now,
    )


@router.get("/resilience-export")
def get_resilience_export():
    """Return extended export with resilience and recovery analytics.
    
    Includes:
      • Provider rankings by quality score
      • Alert history
      • Circuit breaker history
      • Health trends (5min, 30min, 24hr)
      • Recovery statistics
      • Full timeline
    """
    now = datetime.now(timezone.utc)
    
    # Base analytics export
    export_data = provider_analytics.export()
    
    # Add resilience data
    quality_scores = provider_recovery_manager.get_quality_scores()
    export_data["providerQualityScores"] = [s.__dict__ for s in quality_scores]
    
    # Add alert history
    alert_summary = provider_recovery_manager.get_alert_summary()
    alerts = provider_recovery_manager.get_alerts(limit=1000)
    export_data["alertHistory"] = [a.to_dict() for a in alerts]
    
    # Add circuit history placeholder (can be expanded with actual history)
    export_data["circuitHistory"] = {
        "totalOpens": export_data.get("summary", {}).get("circuitBreakerOpens", 0),
        "totalRecoveries": sum(
            s.circuit_close_count for s in quality_scores
        ) if quality_scores else 0,
    }
    
    # Add health trends
    snapshots = provider_registry.get_all_snapshots()
    trends_data = {}
    for snap in snapshots:
        provider_id = snap.metadata.providerId
        trends = provider_recovery_manager.get_health_trends(provider_id)
        if trends:
            trends_data[provider_id] = {
                window_name: t.__dict__
                for window_name, t in trends.items()
            }
    export_data["healthTrends"] = trends_data
    
    # Add recovery statistics
    export_data["recoveryStatistics"] = {
        "lastRecoveryCheck": provider_recovery_manager._last_recovery_check.isoformat()
        if provider_recovery_manager._last_recovery_check else None,
        "recoverySchedulerInterval": provider_recovery_manager.RECOVERY_CHECK_INTERVAL,
        "maxCooldownSeconds": provider_recovery_manager.MAX_COOLDOWN_SECONDS,
        "alertHistory": alert_summary,
    }
    
    # Add performance and cache stats
    export_data["performanceMetrics"] = provider_manager.get_performance_metrics()
    export_data["cacheStats"] = market_cache.stats

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": 'attachment; filename="falcon_resilience_export.json"',
            "Content-Type": "application/json",
        },
    )


@router.get("/instruments", response_model=RuntimeInstrumentsResponse)
def get_runtime_instruments():
    """
    Return complete instrument registry with provider mappings,
    availability status, and usage analytics.
    """
    from app.core.instruments import instrument_registry

    now = datetime.now(timezone.utc)
    instruments_data = []

    for instrument in instrument_registry.all_instruments():
        provider_coverage = []
        for provider_id, provider_symbol in instrument.providerMappings.items():
            # Determine provider availability based on health
            provider_snapshot = provider_registry.get_snapshot(provider_id)
            is_available = (
                provider_snapshot is not None
                and provider_snapshot.metadata.status.value in ["ONLINE", "DEGRADED"]
            )

            provider_coverage.append(
                ProviderCoverageItem(
                    providerId=provider_id,
                    providerSymbol=provider_symbol,
                    isAvailable=is_available,
                    lastQuoteAt=None,
                )
            )

        instruments_data.append(
            InstrumentDetail(
                canonicalSymbol=instrument.canonicalSymbol,
                displayName=instrument.displayName,
                instrumentType=instrument.instrumentType.value,
                assetClass=instrument.assetClass.value,
                exchange=instrument.exchange.value,
                currency=instrument.currency,
                pipSize=instrument.pipSize,
                precision=instrument.precision,
                providerCoverage=provider_coverage,
                active=instrument.active,
            )
        )

    return RuntimeInstrumentsResponse(
        instruments=instruments_data,
        totalInstruments=len(instruments_data),
        generatedAt=now,
    )

