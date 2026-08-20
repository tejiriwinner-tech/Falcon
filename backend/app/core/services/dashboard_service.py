"""
Falcon Dashboard Service
Single aggregator for all dashboard data. Does NOT calculate anything itself.
Only reads from existing engines, repositories, and provider framework.
"""
from datetime import datetime, timezone
from typing import List

from app.core.providers import provider_manager, provider_registry
from app.core.repository.mission_repository import mission_repository
from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.engines.health_engine import HealthEngine
from app.core.engines.decision_engine import DecisionEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.providers.provider_analytics import provider_analytics

from app.schemas.dashboard import DashboardResponse, DashboardSummary, AnalyticsSummary
from app.schemas.market_quote import MarketQuote
from app.schemas.mission_report import MissionSummary
from app.schemas.provider_models import ProviderSummary, ProviderStatus, ProviderHealthDetail
from app.schemas.health import HealthResponse
from app.core.services.news_service import build_news_response
from app.core.services.performance_analytics_service import build_performance_analytics
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_service import signal_service
from app.schemas.decision_engine import RiskAssessment as DERiskAssessment, ExecutionReadiness as DEExecutionReadiness
from app.schemas.strategy import StrategyValidation, StrategyValidationCheck, MarketSnapshot
from app.schemas.runtime import RuntimeMetrics, RuntimeSummary


WATCHLIST = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]
ENGINE_VERSION = "4.2.1"


class DashboardService:
    """Aggregates immutable data from all Falcon subsystems for the dashboard."""

    def __init__(self):
        self.orchestrator = PipelineOrchestrator()
        self.health_engine = HealthEngine()
        self.decision_engine = DecisionEngine()
        self.strategy_engine = StrategyEngine()

    def get_dashboard(self) -> DashboardResponse:
        # ── 1. Reuse the last stored mission, running the pipeline only
        #      when the repository is still empty ─────────────────────
        mission_report = (
            mission_repository.get_latest_mission() or self.orchestrator.run_pipeline()
        )
        artifacts = mission_repository.get_mission_artifacts(mission_report.id)
        
        market_state = artifacts.get("marketState")
        validations = artifacts.get("validations", [])
        assessments = artifacts.get("riskAssessments", [])
        
        # ── 2. Market Quotes ──────────────────────────────────────────
        market_quotes: List[MarketQuote] = []
        for sym in WATCHLIST:
            resp = provider_manager.get_market_quote(sym)
            if resp is not None:
                market_quotes.append(resp.quote)

        # ── 3. Provider Summary ───────────────────────────────────────
        provider_summary: ProviderSummary = provider_registry.get_summary()
        snapshots = provider_registry.get_all_snapshots()

        # connectedProvider must reflect the provider that actually supplied the
        # market quotes — not merely the first ONLINE entry in the registry.
        # Fall back to registry scan only when no quotes are available.
        if market_quotes:
            connected_provider = market_quotes[0].providerName
            provider_status_str = "ONLINE"
        else:
            connected_provider = "Unavailable"
            provider_status_str = "OFFLINE"
            for snap in snapshots:
                if snap.metadata.status == ProviderStatus.ONLINE:
                    connected_provider = snap.metadata.providerName
                    provider_status_str = "ONLINE"
                    break
                elif snap.metadata.status == ProviderStatus.DEGRADED:
                    connected_provider = snap.metadata.providerName
                    provider_status_str = "DEGRADED"

        # ── 4. Repository & Mission Summary ───────────────────────────
        repo_stats = mission_repository.get_statistics()
        all_missions = mission_repository.get_all_missions()

        successful = sum(1 for m in all_missions if m.status.value == "SUCCESS")
        partial = sum(1 for m in all_missions if m.status.value == "PARTIAL_SUCCESS")
        failed = sum(1 for m in all_missions if m.status.value == "FAILED")
        avg_duration = (
            sum(m.performance.totalDurationMs for m in all_missions) / len(all_missions)
            if all_missions else 0.0
        )
        avg_health = (
            sum(m.health.pipelineHealthPercentage for m in all_missions) / len(all_missions)
            if all_missions else 100.0
        )
        mission_summary_obj = MissionSummary(
            totalMissions=repo_stats.totalMissions,
            successful=successful,
            partialSuccess=partial,
            failed=failed,
            averageDurationMs=avg_duration,
            averagePipelineHealth=avg_health,
        )

        # ── 5. Build Sub-Responses (Health, Signals, News, Decision) ──
        
        # Health
        health_data = self.health_engine.get_health()
        system_health = HealthResponse(
            status="ok",
            version=ENGINE_VERSION,
            environment="production",
            timestamp=datetime.now(timezone.utc),
            systemHealth=health_data
        )
        
        # Signals projected from stored mission artifacts
        now = datetime.now(timezone.utc)
        signals = signal_service.build_signals()

        # Economic calendar from the stored FMP events
        news = build_news_response()
        
        # Decision Engine (Bridging logic from router)
        strategy = self.strategy_engine.get_strategy_by_id("strat-001")
        primary_validation = next((v for v in validations if v.strategyId == strategy.id), validations[0] if validations else None)
        primary_assessment = next((a for a in assessments if a.strategyId == strategy.id), assessments[0] if assessments else None)
        
        failed_check_titles = [c.title for c in primary_validation.checks if not c.passed] if primary_validation else []
        bridge_checks = [StrategyValidationCheck(name=c.title, passed=c.passed, value=f"{c.scoreAwarded}/{c.weight}") for c in primary_validation.checks] if primary_validation else []
        
        bridge_snapshot = MarketSnapshot(
            trend=market_state.trend if market_state else "neutral",
            volatility=market_state.volatility if market_state else "low",
            liquidity=market_state.liquidity if market_state else "normal",
            news=market_state.currentNewsImpact if market_state else "none",
            session=market_state.session if market_state else "unknown",
            spread=market_state.spread if market_state else 0.0,
            atr=0.0, rsi=50.0, ema200="above", adx=25.0
        )
        
        bridge_validation = StrategyValidation(
            score=primary_validation.validationScore if primary_validation else 0,
            aiConfidence=primary_validation.validationScore if primary_validation else 0,
            validationDurationSeconds=(primary_validation.validationDurationMs / 1000.0) if primary_validation else 0.0,
            failedChecks=failed_check_titles,
            checks=bridge_checks,
            marketSnapshot=bridge_snapshot
        )
        
        bridge_risk = DERiskAssessment(
            accountRiskPercent=1.0, maxDrawdown=5.0, positionSizeRecommendation=0.10,
            riskFactors=[r.title for r in primary_assessment.reasons] if primary_assessment else []
        )
        
        blocking = [r.title for r in primary_assessment.reasons if r.isBlocking] if primary_assessment else []
        passed_items = [r.title for r in primary_assessment.reasons if not r.isBlocking] if primary_assessment else []
        is_ready = (primary_assessment is not None and not blocking and primary_validation is not None and primary_validation.validationScore >= 85)
        
        bridge_readiness = DEExecutionReadiness(
            isReady=is_ready,
            overallReadinessScore=primary_validation.validationScore if primary_validation else 0,
            blockingConditions=blocking + failed_check_titles,
            passedChecks=passed_items,
            estimatedTimeUntilReady=None if is_ready else "Awaiting confirmation"
        )
        
        decision_resp = self.decision_engine.get_decision(
            strategy=strategy, market_state=market_state, validation=bridge_validation, risk_assessment=bridge_risk, readiness=bridge_readiness
        ) if strategy and market_state else None
        
        latest_decision_str = decision_resp.recommendation.value if decision_resp else "WAIT"

        # ── 6. Combine all into DashboardResponse ─────────────────────
        analytics = build_performance_analytics()
        closed_trades = [
            trade for trade in trade_journal_repository.list_trades()
            if trade.result in ("WIN", "LOSS", "BREAKEVEN")
        ]
        wins = sum(1 for trade in closed_trades if trade.result == "WIN")
        analytics_summary = AnalyticsSummary(
            tradingScore=analytics.tradingScore,
            winRate=round(wins / len(closed_trades) * 100, 2) if closed_trades else 0.0,
            totalTrades=len(closed_trades),
            netProfit=analytics.netProfit,
            lastUpdated=now,
        )
        
        pipeline_health = avg_health if all_missions else 100.0
        total_artifacts = repo_stats.totalCandidates + repo_stats.totalValidations + repo_stats.totalRiskAssessments + repo_stats.totalExecutionReadiness + repo_stats.totalDecisions
        
        summary = DashboardSummary(
            providerStatus=provider_status_str, pipelineHealth=pipeline_health, repositoryHealth=repo_stats.repositoryHealth,
            activeProviders=provider_summary.online, connectedProvider=connected_provider, watchedSymbols=WATCHLIST,
            totalStrategies=len(self.strategy_engine.get_strategies()), totalSignals=repo_stats.totalCandidates, totalMissions=repo_stats.totalMissions,
            totalArchivedArtifacts=total_artifacts, latestDecision=latest_decision_str, lastRefresh=now, engineVersion=ENGINE_VERSION
        )

        # ── Phase 4.3.8 — per-provider health detail ──────────────────
        # Expose status, success rate, latency, circuit state, and last
        # request timestamps.  No API keys or internal URLs included.
        provider_health_details: List[ProviderHealthDetail] = []
        for snap in snapshots:
            s = snap.statistics
            provider_health_details.append(ProviderHealthDetail(
                providerId=snap.metadata.providerId,
                providerName=snap.metadata.providerName,
                status=snap.metadata.status.value,
                health=snap.metadata.health.value,
                circuitBreakerState=s.circuitBreakerState,
                successRate=s.successRate,
                avgLatencyMs=snap.latency.averageMs,
                lastSuccessAt=s.lastSuccessAt or s.lastSuccessfulQuoteAt,
                lastFailureAt=s.lastFailureAt or s.lastFailedRequestAt,
                circuitRetryInSeconds=s.circuitRetryInSeconds,
            ))

        return DashboardResponse(
            summary=summary,
            marketQuotes=market_quotes,
            providerSummary=provider_summary,
            missionSummary=mission_summary_obj,
            analyticsSummary=analytics_summary,
            systemHealth=system_health,
            marketState=market_state,
            signals=signals,
            news=news,
            decision=decision_resp,
            providerHealth=provider_health_details,
            runtimeMetrics=self._build_runtime_metrics(market_quotes),
        )

    def _build_runtime_metrics(self, market_quotes) -> RuntimeMetrics:
        """Build compact runtime metrics for the dashboard panel."""
        summary_dict = provider_analytics.get_summary()
        pm_metrics   = provider_manager.get_performance_metrics()

        # Current provider — the one that actually served the first quote
        current_provider = (
            market_quotes[0].providerName if market_quotes else "Unknown"
        )

        # Top provider by success rate from analytics
        all_stats = provider_analytics.get_all_stats()
        top_provider = "Unknown"
        if all_stats:
            best = max(all_stats, key=lambda s: s["successRate"])
            top_provider = best["providerName"]

        return RuntimeMetrics(
            summary=RuntimeSummary(**summary_dict),
            currentProvider=current_provider,
            topProviderBySuccessRate=top_provider,
            totalFailoversToday=summary_dict.get("totalFailovers", 0),
            cacheHitRate=pm_metrics.get("cacheStats", {}).get("hit_rate", 0.0),
            avgColdRequestMs=pm_metrics.get("avgColdRequestMs", 0.0),
            avgWarmRequestMs=pm_metrics.get("avgWarmRequestMs", 0.0),
        )


dashboard_service = DashboardService()
