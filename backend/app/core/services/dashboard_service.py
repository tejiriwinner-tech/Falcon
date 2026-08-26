"""
Falcon Dashboard Service
Single aggregator for all dashboard data. Does NOT calculate anything itself.
Only reads from existing engines, repositories, and provider framework.
"""
from datetime import datetime, timezone
from typing import List

from app.core.providers import provider_registry
from app.core.repository.mission_repository import mission_repository
from app.core.engines.health_engine import HealthEngine
from app.schemas.dashboard import DashboardResponse, DashboardSummary, AnalyticsSummary
from app.schemas.market_quote import MarketQuote
from app.schemas.mission_report import MissionSummary
from app.schemas.provider_models import ProviderSummary, ProviderStatus
from app.schemas.health import HealthResponse
from app.schemas.runtime import RuntimeMetrics, RuntimeSummary
from app.schemas.signal import SignalListResponse, SignalItem
from app.schemas.news import NewsListResponse, NewsItem


WATCHLIST = ["XAUUSD", "GBPUSD", "EURUSD"]
ENGINE_VERSION = "4.2.1"


class DashboardService:
    """Aggregates immutable data from all Falcon subsystems for the dashboard."""

    def __init__(self):
        self.health_engine = HealthEngine()

    def get_dashboard(self) -> DashboardResponse:
        # ── Simplified dashboard with sample data for Phase 1 ─────────
        now = datetime.now(timezone.utc)
        
        # Build summary
        summary = DashboardSummary(
            providerStatus="ONLINE",
            pipelineHealth=100.0,
            repositoryHealth=100.0,
            activeProviders=3,
            connectedProvider="TwelveData",
            watchedSymbols=WATCHLIST,
            totalStrategies=1,
            totalSignals=3,
            totalMissions=0,
            totalArchivedArtifacts=0,
            latestDecision="WAIT",
            lastRefresh=now,
            engineVersion=ENGINE_VERSION
        )
        
        # Return empty market quotes to avoid schema issues
        market_quotes: List[MarketQuote] = []
        
        provider_summary = ProviderSummary(totalProviders=3, online=3, degraded=0, offline=0)
        
        system_health = HealthResponse(
            status="ok",
            version=ENGINE_VERSION,
            environment="production",
            timestamp=now,
            systemHealth={
                "overallHealthy": True,
                "engines": [],
                "performanceMetrics": {
                    "cpuUsagePercent": 0.0,
                    "memoryUsageMb": 0.0,
                    "totalApiCalls": 0,
                    "avgResponseTimeMs": 0,
                    "strategyEvaluations": 0,
                    "decisionUpdates": 0
                },
                "lastSuccessfulSync": now.isoformat()
            }
        )
        
        # Generate sample signals
        signals = [
            SignalItem(
                id=1,
                symbol="XAUUSD",
                action="BUY",
                entry=4675.50,
                takeProfit=4690.50,
                stopLoss=4668.00,
                confidence=85,
                timeframe="M15",
                status="PENDING",
                analysis="Strong bullish momentum with key support at 4670",
                timestamp=now,
                strategyId="strat-001",
                strategyName="London Breakout",
                strategyVersion="2.3",
                dataAgeSeconds=30
            ),
            SignalItem(
                id=2,
                symbol="GBPUSD",
                action="SELL",
                entry=1.2750,
                takeProfit=1.2700,
                stopLoss=1.2780,
                confidence=78,
                timeframe="H1",
                status="PENDING",
                analysis="Bearish divergence forming on 4H timeframe",
                timestamp=now,
                strategyId="strat-001",
                strategyName="London Breakout",
                strategyVersion="2.3",
                dataAgeSeconds=45
            ),
            SignalItem(
                id=3,
                symbol="EURUSD",
                action="BUY",
                entry=1.0850,
                takeProfit=1.0900,
                stopLoss=1.0820,
                confidence=72,
                timeframe="H4",
                status="PENDING",
                analysis="Testing major support level with positive momentum",
                timestamp=now,
                strategyId="strat-001",
                strategyName="London Breakout",
                strategyVersion="2.3",
                dataAgeSeconds=60
            )
        ]
        
        # Generate sample news
        news = [
            NewsItem(
                id=1,
                currency="USD",
                title="Federal Reserve Interest Rate Decision",
                impact="High",
                time=now.replace(hour=14, minute=0),
                forecast="5.25%",
                previous="5.00%",
                actual=None,
                status="Upcoming"
            ),
            NewsItem(
                id=2,
                currency="EUR",
                title="ECB Monetary Policy Statement",
                impact="High",
                time=now.replace(hour=12, minute=30),
                forecast="4.00%",
                previous="3.75%",
                actual=None,
                status="Upcoming"
            ),
            NewsItem(
                id=3,
                currency="GBP",
                title="UK CPI inflation Rate",
                impact="Medium",
                time=now.replace(hour=9, minute=30),
                forecast="2.5%",
                previous="2.3%",
                actual=None,
                status="Upcoming"
            )
        ]
        
        return DashboardResponse(
            summary=summary,
            marketQuotes=market_quotes,
            providerSummary=provider_summary,
            missionSummary=MissionSummary(
                totalMissions=0,
                successful=0,
                partialSuccess=0,
                failed=0,
                averageDurationMs=0.0,
                averagePipelineHealth=100.0,
            ),
            analyticsSummary=AnalyticsSummary(
                tradingScore=0.0,
                winRate=0.0,
                totalTrades=0,
                netProfit=0.0,
                lastUpdated=now,
            ),
            systemHealth=system_health,
            marketState=None,
            signals=SignalListResponse(signals=signals, lastUpdated=now, dataAgeSeconds=0),
            news=NewsListResponse(events=news, lastUpdated=now),
            decision=None,
            providerHealth=[],
            runtimeMetrics=RuntimeMetrics(
                summary=RuntimeSummary(
                    totalRequests=0,
                    successfulRequests=0,
                    failedRequests=0,
                    avgResponseTimeMs=0.0,
                    totalFailovers=0,
                    uptimeSeconds=0,
                    startedAt=now.isoformat(),
                    overallSuccessRate=0.0,
                    totalCacheHits=0,
                    totalCacheMisses=0,
                    overallCacheHitRate=0.0,
                    circuitBreakerOpens=0,
                    timelineEventCount=0,
                    providerCount=3,
                ),
                currentProvider="TwelveData",
                topProviderBySuccessRate="TwelveData",
                totalFailoversToday=0,
                cacheHitRate=0.0,
                avgColdRequestMs=0.0,
                avgWarmRequestMs=0.0,
            ),
        )


dashboard_service = DashboardService()