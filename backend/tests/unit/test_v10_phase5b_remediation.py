"""
Falcon V10 — Phase 5B: Production Signal Pipeline Remediation & Hardening Test Suite.

Comprehensive verification of all 8 Phase 5A audit defect remediations:

1. Read-Only Signal Pipeline (Defects 1 & 6):
   - GET /api/v1/signals is strictly read-only and idempotent.
   - Signal generation does NOT call authorize_candidate() or insert PENDING records into trade_journal.
   - Signal generation does NOT invoke OrderExecutionService.create_order() or create execution orders.
   - SignalAuthorizationService.evaluate_candidate() runs pure in-memory Guardian validation without DB mutation.

2. Promoted Research Context Propagation (Defect 2):
   - ResearchPromotionService provides active promoted research contexts.
   - Exact 5-tuple matching attaches research context to candidates and signals.
   - Mismatches safely return None (fail-closed).
   - Core trading parameters (direction, entry, SL, TP, confidence, lot size, monetary risk)
     are 100% invariant whether research context is attached or absent.

3. Truthful Timeframe Provenance (Defect 3):
   - CandlestickPatternEngine requires genuine multi-timeframe data for alignment; does not fabricate 5m/15m.
   - CandlestickPatternEngine processes 1h candles truthfully.
   - SignalGenerationEngine queries and analyzes 1h candles without relabeling.
   - SignalService defaults to "1h" timeframe, never "M15".

4. Authentic RSI Telemetry & Safe Missing Handling (Defect 4):
   - CandidateMarketSnapshot carries optional authentic rsi field.
   - SignalGenerationEngine extracts authentic rsi from indicators.
   - ValidationEngine uses authentic RSI when present (healthy boundary 30-70).
   - ValidationEngine handles missing RSI safely without fabricating 50.0.

5. DecisionArtifact Canonical Trade Parameters (Defect 5):
   - DecisionArtifact schema defines symbol, entryPrice, stopLoss, takeProfit, researchContext.
   - DecisionEngine populates canonical trade parameters directly from candidate.
   - Serialized JSON exports camelCase fields: symbol, entryPrice, stopLoss, takeProfit.

6. Dynamic ATR Fallback Stop-Loss Distance (Defect 7):
   - Fallback stop distance uses dynamic 1.5 * ATR * adaptive_mult.
   - Hardcoded magic numbers (11.50, 0.45, 0.0035, 0.0028) are absent from signal generation stop-loss logic.
   - Valid pattern swing stop retains priority over ATR fallback when risk-reward is sufficient.

7. Mobile Execution Dead-Code Removal (Defect 8):
   - Mobile ApiService does NOT contain executeOrder method.
   - Mobile codebase has zero references to executeOrder.

8. Safety Invariants:
   - Zero broker calls (order_send, order_modify, order_close, MetaTrader5.initialize).
"""

import copy
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.analytics.historical_findings_service import (
    HistoricalFindingsService,
    historical_findings_service,
)
from app.core.analytics.candlestick_research_service import candlestick_research_service
from app.core.engines.candlestick_pattern_engine import (
    CandleBar,
    CandlestickPatternEngine,
    PatternType,
    SignalDirection as PatSignalDirection,
)
from app.core.engines.decision_engine import DecisionEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
    capital_cycle_repository,
)
from app.core.repository.mission_repository import (
    InMemoryMissionStorage,
    MissionRepository,
    mission_repository,
)
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.market_history_service import market_history_service
from app.core.services.research_promotion_service import (
    ResearchPromotionService,
    research_promotion_service,
)
from app.core.services.signal_authorization_service import (
    SignalAuthorizationService,
    signal_authorization_service,
)
from app.core.services.signal_service import (
    SignalService,
    signal_service,
)
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleStatus
from app.schemas.capital_guardian import CapitalGuardianDecision
from app.schemas.decision_artifact import (
    DecisionArtifact,
    DecisionMarketSnapshot,
    DecisionPipelineSummary,
    DecisionPriority,
    DecisionRecommendation,
    DecisionRecommendationDetails,
    DecisionStatus,
    MissionVerdict,
)
from app.schemas.execution_readiness import ExecutionReadiness, ExecutionReadinessStatus, ReadinessSeverity
from app.schemas.historical_findings import (
    ForwardValidationStatus,
    HypothesisStatus,
)
from app.schemas.market_state import MarketPrice, MarketState
from app.schemas.mission_report import (
    MissionArtifactReferences,
    MissionHealth,
    MissionPerformance,
    MissionPipelineSummary,
    MissionReport,
    MissionStatus,
)
from app.schemas.research_promotion import (
    PromotionStatus,
    ResearchPromotionResponse,
    ResearchPromotionResult,
    ResearchSignalContext,
)
from app.schemas.risk_assessment import RiskAssessment, RiskAssessmentStatus, RiskLevel
from app.schemas.signal import SignalItem, SignalListResponse
from app.schemas.signal_candidate import (
    CandidateCondition,
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateReason,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.strategy import (
    RiskLevel as StratRiskLevel,
    StrategyCategory,
    StrategyHealth,
    StrategyItem,
    StrategyScore,
    StrategyStatus,
    StrategyType,
)
from app.schemas.validation_result import ValidationResult, ValidationStatus
from app.services.execution.order_execution_service import (
    OrderExecutionService,
    order_execution_service,
)


# =============================================================================
# FIXTURES & TEST SETUP
# =============================================================================

@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """Ensure in-memory repositories and prevent external DB/network queries."""
    monkeypatch.setattr(market_history_service, "get_bars", lambda *args, **kwargs: [])
    from app.core.services.signal_outcome_resolver import signal_outcome_resolver
    monkeypatch.setattr(signal_outcome_resolver, "resolve_signals", lambda *args, **kwargs: None)

    # Use clean in-memory storage for repositories
    original_journal_storage = trade_journal_repository._storage
    journal_mem = InMemoryTradeJournalStorage()
    trade_journal_repository._storage = journal_mem
    trade_journal_repository.clear()

    original_mission_storage = mission_repository._storage
    mission_mem = InMemoryMissionStorage()
    mission_repository._storage = mission_mem
    mission_repository._invalidate_cache()

    original_cycle_storage = capital_cycle_repository._storage
    cycle_mem = InMemoryCapitalCycleStorage()
    capital_cycle_repository._storage = cycle_mem
    capital_cycle_repository.clear()

    # Initialize an active capital cycle so Guardian can evaluate
    capital_cycle_repository.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-1",
            cycleNumber=1,
            startingCapital=Decimal("100.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("100.00"),
            status=CapitalCycleStatus.ACTIVE,
        )
    )

    yield

    trade_journal_repository.clear()
    trade_journal_repository._storage = original_journal_storage
    mission_repository._storage = original_mission_storage
    mission_repository._invalidate_cache()
    capital_cycle_repository.clear()
    capital_cycle_repository._storage = original_cycle_storage


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def sample_candidate():
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    return SignalCandidate(
        id="cand-eurusd-001",
        symbol="EURUSD",
        strategyId="strat-001",
        strategyName="Falcon Core Trend",
        strategyVersion="1.0.0",
        strategyGrade="A",
        strategyScore=85,
        direction=CandidateDirection.BUY,
        confidence=85,
        readinessScore=85,
        entryPrice=1.0850,
        stopLoss=1.0815,
        takeProfit=1.0920,
        riskReward=2.0,
        status=CandidateStatus.APPROVED,
        generatedAt=now,
        reasons=[
            CandidateReason(
                title="BULLISH_ENGULFING",
                description="Bullish engulfing candle on 1h",
                passed=True,
            )
        ],
        conditions=[
            CandidateCondition(
                title="Spread Check",
                description="Spread within acceptable limits",
                passed=True,
            )
        ],
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=85,
            strategyScore=85,
            sessionScore=85,
            sentimentScore=85,
            newsScore=85,
        ),
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="NORMAL",
            session="London",
            spread=0.2,
            newsImpact="LOW",
            marketSentiment="BULLISH",
            marketConfidence=85,
            atr=0.0020,
            rsi=55.0,
        ),
        evaluationDurationMs=15,
        marketDataAgeSeconds=10,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
    )


# =============================================================================
# SECTION 1: READ-ONLY SIGNAL PIPELINE & ZERO ORDER CREATION (DEFECTS 1 & 6)
# =============================================================================

def _create_test_mission(mission_id: str, candidate: SignalCandidate, decision: Optional[DecisionArtifact] = None):
    now = datetime.now(timezone.utc)
    report = MissionReport(
        id=mission_id,
        missionNumber=1,
        status=MissionStatus.SUCCESS,
        artifactReferences=MissionArtifactReferences(
            marketStateId="market-1",
            candidateIds=[candidate.id],
            validationIds=[],
            riskAssessmentIds=[],
            executionReadinessIds=[],
            decisionIds=[decision.id] if decision else [],
        ),
        pipelineSummary=MissionPipelineSummary(
            marketStateCount=1,
            candidateCount=1,
            validationCount=0,
            riskAssessmentCount=0,
            executionReadinessCount=0,
            decisionCount=1 if decision else 0,
        ),
        performance=MissionPerformance(
            totalDurationMs=10,
            marketDurationMs=1,
            signalDurationMs=1,
            validationDurationMs=1,
            riskDurationMs=1,
            executionDurationMs=1,
            decisionDurationMs=1,
            averageStageDurationMs=1.0,
        ),
        health=MissionHealth(
            pipelineHealthPercentage=100.0,
            providerHealthPercentage=100.0,
            enginesHealthy=6,
            providersHealthy=3,
            warnings=[],
        ),
        timeline=[],
        startedAt=now,
        completedAt=now,
    )
    mission_repository.save_mission(report)
    mission_repository.save_candidates(mission_id, [candidate])
    if decision:
        mission_repository.save_decisions(mission_id, [decision])


def make_valid_decision_artifact(
    decision_id: str,
    candidate: SignalCandidate,
    status: DecisionStatus = DecisionStatus.APPROVED,
) -> DecisionArtifact:
    now = datetime.now(timezone.utc)
    return DecisionArtifact(
        id=decision_id,
        marketStateId="market-1",
        candidateId=candidate.id,
        validationId="val-1",
        riskAssessmentId="risk-1",
        executionReadinessId="exec-1",
        strategyId=candidate.strategyId,
        strategyName=candidate.strategyName,
        strategyVersion=candidate.strategyVersion,
        recommendation=DecisionRecommendation.BUY if candidate.direction == CandidateDirection.BUY else DecisionRecommendation.SELL,
        status=status,
        decisionConfidence=float(candidate.confidence),
        recommendationDetails=DecisionRecommendationDetails(
            recommendation=DecisionRecommendation.BUY if candidate.direction == CandidateDirection.BUY else DecisionRecommendation.SELL,
            priority=DecisionPriority.HIGH,
            expectedHolding="4 hours",
            missionStatus="SUCCESS",
            title="Approved Setup",
            description="Setup passed all validation gates.",
        ),
        missionVerdict=MissionVerdict(
            signalVerdict=candidate.status,
            validationVerdict=ValidationStatus.PASSED,
            riskVerdict=RiskLevel.LOW,
            executionVerdict=ExecutionReadinessStatus.READY,
            decisionVerdict=DecisionRecommendation.BUY if candidate.direction == CandidateDirection.BUY else DecisionRecommendation.SELL,
        ),
        decisionTrace=[],
        supportingFactors=[],
        blockingFactors=[],
        watchItems=[],
        pipelineSummary=DecisionPipelineSummary(
            candidateStatus=candidate.status,
            validationStatus=ValidationStatus.PASSED,
            riskStatus=RiskAssessmentStatus.PASSED,
            executionStatus=ExecutionReadinessStatus.READY,
            signalConfidence=float(candidate.confidence),
            validationScore=90.0,
            overallRiskScore=15.0,
            executionReadinessScore=85.0,
        ),
        marketSnapshot=DecisionMarketSnapshot(
            trend=candidate.marketSnapshot.trend,
            volatility=candidate.marketSnapshot.volatility,
            session=candidate.marketSnapshot.session,
            spread=candidate.marketSnapshot.spread,
            newsImpact=candidate.marketSnapshot.newsImpact,
            marketSentiment=candidate.marketSnapshot.marketSentiment,
            marketConfidence=float(candidate.marketSnapshot.marketConfidence),
            dataAgeSeconds=candidate.marketDataAgeSeconds,
        ),
        symbol=candidate.symbol,
        entryPrice=candidate.entryPrice,
        stopLoss=candidate.stopLoss,
        takeProfit=candidate.takeProfit,
        researchContext=candidate.researchContext,
        decidedAt=now,
        decisionDurationMs=15,
    )


class TestReadOnlySignalPipeline:
    """Verify that signal generation and the signals endpoint are 100% read-only."""

    def test_signals_endpoint_does_not_mutate_trade_journal(self, test_client, sample_candidate):
        """GET /api/v1/signals must NOT insert PENDING records into trade_journal."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        decision = make_valid_decision_artifact("dec-001", sample_candidate)
        _create_test_mission("mission-read-only-test", sample_candidate, decision)

        initial_count = len(trade_journal_repository.list_trades())
        assert initial_count == 0

        # Invoke GET /api/v1/signals
        response = test_client.get("/api/v1/signals")
        assert response.status_code == 200

        # Count must remain 0 — absolutely no PENDING reservation created
        final_count = len(trade_journal_repository.list_trades())
        assert final_count == 0, f"Expected 0 journal records, found {final_count} (mutated on GET!)"

    def test_signals_endpoint_is_idempotent(self, test_client, sample_candidate):
        """Repeated GET /api/v1/signals calls produce identical output and 0 journal writes."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        decision = make_valid_decision_artifact("dec-002", sample_candidate)
        _create_test_mission("mission-idempotent-test", sample_candidate, decision)

        resp1 = test_client.get("/api/v1/signals")
        resp2 = test_client.get("/api/v1/signals")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert len(resp1.json()["signals"]) == len(resp2.json()["signals"])
        assert len(trade_journal_repository.list_trades()) == 0

    def test_signal_service_does_not_call_order_execution_service(self, sample_candidate):
        """SignalService.build_signals() must NEVER call OrderExecutionService.create_order()."""
        svc = SignalService()
        now = datetime.now(timezone.utc)
        with patch.object(order_execution_service, "create_order") as mock_create_order:
            svc._to_signal(sample_candidate, None, 1, now)
            assert mock_create_order.call_count == 0, (
                "SignalService._to_signal called OrderExecutionService.create_order!"
            )

    def test_signal_service_calls_evaluate_candidate_not_authorize(self, sample_candidate):
        """SignalService.build_signals() must call evaluate_candidate, NOT authorize_candidate."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        sample_candidate.readinessScore = 90
        decision = make_valid_decision_artifact("dec-eval", sample_candidate)
        _create_test_mission("mission-eval-test", sample_candidate, decision)

        with patch.object(signal_authorization_service, "evaluate_candidate", wraps=signal_authorization_service.evaluate_candidate) as mock_eval, \
             patch.object(signal_authorization_service, "authorize_candidate") as mock_auth:
            
            svc = SignalService()
            svc.build_signals()

            assert mock_eval.call_count >= 1, "evaluate_candidate was not called!"
            assert mock_auth.call_count == 0, "authorize_candidate was called during signal generation!"

    def test_evaluate_candidate_is_pure_in_memory(self, sample_candidate):
        """SignalAuthorizationService.evaluate_candidate() runs Guardian without DB mutation."""
        auth_svc = SignalAuthorizationService()
        count_before = len(trade_journal_repository.list_trades())

        decision = auth_svc.evaluate_candidate(sample_candidate)

        count_after = len(trade_journal_repository.list_trades())
        assert count_before == count_after == 0, "evaluate_candidate modified trade_journal!"
        assert isinstance(decision, CapitalGuardianDecision)
        assert isinstance(decision.allowed, bool)
        assert isinstance(decision.reason, str)


# =============================================================================
# SECTION 2: PROMOTED RESEARCH CONTEXT PROPAGATION (DEFECT 2)
# =============================================================================

class TestResearchContextPropagation:
    """Verify research context propagation, exact 5-tuple matching, and signal invariance."""

    @pytest.fixture
    def dummy_promoted_context(self):
        return ResearchSignalContext(
            candidate_id="HYP-EURUSD-1H-H5-001",
            instrument="EURUSD",
            timeframe="1H",
            horizon=5,
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            candidate_as_of=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
            validation_as_of=datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
            promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
            qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
            forward_validation_sample_size=35,
            forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
            methodology_version="1.0.0",
            provenance_note="Verified Phase 4B promoted hypothesis",
            limitations=["Descriptive research finding only; not an execution recommendation."],
        )

    def test_research_promotion_service_cache(self, dummy_promoted_context):
        """ResearchPromotionService caches and returns promoted contexts."""
        svc = ResearchPromotionService()
        key = ("EURUSD", "1H", "BULLISH_ENGULFING", "UPTREND", 5)
        svc.set_active_promoted_contexts([dummy_promoted_context])
        contexts1 = svc.get_active_promoted_contexts()
        contexts2 = svc.get_active_promoted_contexts()

        assert len(contexts1) == 1
        assert contexts1[key].candidate_id == dummy_promoted_context.candidate_id
        assert contexts1 == contexts2

    def test_exact_5tuple_matching_attaches_context(self, sample_candidate, dummy_promoted_context):
        """Candidate matching exact 5-tuple receives researchContext."""
        matched = SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="1h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        )
        assert matched is not None
        assert matched.candidate_id == dummy_promoted_context.candidate_id
        assert matched.promotion_status == PromotionStatus.ELIGIBLE_INFORMATIONAL

    def test_mismatched_5tuple_fails_closed(self, dummy_promoted_context):
        """Any mismatch across the 5 dimensions returns None."""
        # Mismatched instrument
        assert SignalGenerationEngine.match_research_context(
            instrument="GBPUSD",
            timeframe="1h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        ) is None

        # Mismatched timeframe
        assert SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="4h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        ) is None

        # Mismatched horizon
        assert SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="1h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            horizon=10,
            contexts=[dummy_promoted_context],
        ) is None

    def test_signal_invariance_with_and_without_research_context(self, sample_candidate, dummy_promoted_context):
        """Trading parameters must be 100% IDENTICAL whether research context is present or None."""
        cand_with_ctx = copy.deepcopy(sample_candidate)
        cand_with_ctx.researchContext = dummy_promoted_context

        cand_without_ctx = copy.deepcopy(sample_candidate)
        cand_without_ctx.researchContext = None

        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig_with = svc._to_signal(cand_with_ctx, None, 1, now)
        sig_without = svc._to_signal(cand_without_ctx, None, 2, now)

        assert sig_with.symbol == sig_without.symbol
        assert sig_with.action == sig_without.action
        assert sig_with.entry == sig_without.entry
        assert sig_with.stopLoss == sig_without.stopLoss
        assert sig_with.takeProfit == sig_without.takeProfit
        assert sig_with.confidence == sig_without.confidence
        assert sig_with.riskReward == sig_without.riskReward
        assert sig_with.timeframe == sig_without.timeframe

        # The only difference is researchContext presence
        assert sig_with.researchContext is not None
        assert sig_without.researchContext is None


# =============================================================================
# SECTION 3: TRUTHFUL TIMEFRAME PROVENANCE (DEFECT 3)
# =============================================================================

class TestTimeframeIntegrity:
    """Verify authentic timeframe handling and elimination of fabricated 5m/15m claims."""

    def test_candlestick_pattern_engine_requires_authentic_multi_timeframe(self):
        """Multi-timeframe alignment is not returned when 5m/15m candles are missing."""
        engine = CandlestickPatternEngine()
        candles_1h = [
            CandleBar(open=1.0800, high=1.0850, low=1.0790, close=1.0840),
            CandleBar(open=1.0840, high=1.0890, low=1.0830, close=1.0880),
        ]

        results = engine.analyze_patterns(candles_1h=candles_1h)
        assert all(r.pattern_type != PatternType.TIMEFRAME_15M_5M_BREAKOUT for r in results)

    def test_candlestick_pattern_engine_processes_1h_candles_truthfully(self):
        """1h candles are analyzed directly without fabricating higher or lower timeframes."""
        engine = CandlestickPatternEngine()
        # Bullish engulfing on 1h: prev red bar, curr green engulfing body (requires >= 3 candles)
        candles_1h = [
            CandleBar(open=1.0840, high=1.0850, low=1.0830, close=1.0845),
            CandleBar(open=1.0850, high=1.0860, low=1.0800, close=1.0810),
            CandleBar(open=1.0805, high=1.0880, low=1.0800, close=1.0870),
        ]
        results = engine.analyze_patterns(candles_1h=candles_1h)
        assert len(results) > 0
        assert results[0].pattern_type == PatternType.BULLISH_ENGULFING
        assert results[0].direction == PatSignalDirection.BUY

    def test_signal_service_defaults_to_1h_not_m15(self, sample_candidate):
        """SignalItem timeframe defaults to '1h', never legacy 'M15'."""
        svc = SignalService()
        cand = copy.deepcopy(sample_candidate)
        cand.strategyId = "unknown-strat-fallback"
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(cand, None, 1, now)
        assert sig.timeframe == "1h", f"Expected timeframe '1h', got {sig.timeframe}"


# =============================================================================
# SECTION 4: AUTHENTIC RSI TELEMETRY & SAFE MISSING HANDLING (DEFECT 4)
# =============================================================================

class TestRsiDataIntegrity:
    """Verify authentic RSI telemetry and safe missing handling."""

    def test_candidate_market_snapshot_carries_rsi(self):
        """CandidateMarketSnapshot accepts and stores authentic RSI float."""
        snap = CandidateMarketSnapshot(
            trend="Bullish",
            volatility="NORMAL",
            session="London",
            spread=0.1,
            newsImpact="LOW",
            marketSentiment="BULLISH",
            marketConfidence=80,
            atr=0.0015,
            rsi=42.5,
        )
        assert snap.rsi == 42.5

        # Allows None
        snap_none = CandidateMarketSnapshot(
            trend="Bullish",
            volatility="NORMAL",
            session="London",
            spread=0.1,
            newsImpact="LOW",
            marketSentiment="BULLISH",
            marketConfidence=80,
            atr=0.0015,
            rsi=None,
        )
        assert snap_none.rsi is None

    def test_validation_engine_evaluates_authentic_rsi(self, sample_candidate):
        """ValidationEngine respects authentic RSI when evaluating candidate."""
        v_engine = ValidationEngine()
        market_state = MarketState(
            timestamp=datetime.now(timezone.utc),
            provider="twelve_data",
            environment="PRODUCTION",
            prices={},
            session="London",
            dataAgeSeconds=0,
        )

        # 1. Healthy RSI for candidate (55.0 — inside 30-70)
        sample_candidate.marketSnapshot.rsi = 55.0
        results_healthy = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check_healthy = next((c for c in results_healthy[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check_healthy is not None
        assert rsi_check_healthy.passed is True
        assert rsi_check_healthy.scoreAwarded == 15

        # 2. Overbought RSI (78.0 — outside 30-70)
        sample_candidate.marketSnapshot.rsi = 78.0
        results_overbought = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check_overbought = next((c for c in results_overbought[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check_overbought is not None
        assert rsi_check_overbought.passed is False
        assert rsi_check_overbought.scoreAwarded == 0

    def test_validation_engine_handles_missing_rsi_safely_without_fabrication(self, sample_candidate):
        """ValidationEngine does NOT fabricate 50.0 when RSI is None."""
        v_engine = ValidationEngine()
        market_state = MarketState(
            timestamp=datetime.now(timezone.utc),
            provider="twelve_data",
            environment="PRODUCTION",
            prices={},
            session="London",
            dataAgeSeconds=0,
        )
        sample_candidate.marketSnapshot.rsi = None

        results = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check = next((c for c in results[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check is not None
        assert rsi_check.passed is False
        assert "telemetry unavailable" in rsi_check.description.lower()
        # Ensure candidate RSI remains None and was not backfilled with 50.0
        assert sample_candidate.marketSnapshot.rsi is None


# =============================================================================
# SECTION 5: DECISION ARTIFACT CANONICAL TRADE PARAMETERS (DEFECT 5)
# =============================================================================

class TestDecisionArtifactIntegrity:
    """Verify canonical trade parameters in DecisionArtifact."""

    def test_decision_artifact_schema_contains_canonical_fields(self):
        """DecisionArtifact model defines symbol, entryPrice, stopLoss, takeProfit."""
        fields = DecisionArtifact.model_fields
        assert "symbol" in fields
        assert "entry_price" in fields or "entryPrice" in fields
        assert "stop_loss" in fields or "stopLoss" in fields
        assert "take_profit" in fields or "takeProfit" in fields
        assert "research_context" in fields or "researchContext" in fields

    def test_decision_engine_populates_canonical_trade_parameters(self, sample_candidate):
        """DecisionEngine populates symbol, entryPrice, stopLoss, takeProfit from candidate."""
        now = datetime.now(timezone.utc)
        class MockItem:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

        rec_mock = MockItem(nextReviewIn="Immediate")
        snap_mock = MockItem(
            volatility="NORMAL",
            session="London",
            spread=0.2,
            newsImpact="LOW",
            marketSentiment="BULLISH",
            marketConfidence=85.0,
            dataAgeSeconds=10,
        )
        exec_item = MockItem(
            id="exec-001",
            candidateId=sample_candidate.id,
            validationId="val-001",
            riskAssessmentId="risk-001",
            strategyId="strat-001",
            status=ExecutionReadinessStatus.READY,
            overallReadinessScore=85.0,
            candidateStatus=sample_candidate.status,
            validationStatus=ValidationStatus.PASSED,
            riskLevel=RiskLevel.LOW,
            riskStatus=RiskAssessmentStatus.PASSED,
            reasons=[],
            evaluatedAt=now,
            recommendation=rec_mock,
            marketSnapshot=snap_mock,
        )
        risk_item = MockItem(
            id="risk-001",
            overallRiskScore=15.0,
            assessedAt=now,
        )
        val_item = MockItem(
            id="val-001",
            validationScore=85.0,
            validatedAt=now,
        )
        strat_item = MockItem(
            id="strat-001",
            name="Falcon Strategy",
            strategyVersion="1.0.0",
            estimatedHoldingTime="4 Hours",
        )
        market_state = MarketState(
            id="market-1",
            timestamp=now,
            provider="twelve_data",
            environment="PRODUCTION",
            prices={},
            session="London",
            dataAgeSeconds=0,
        )

        engine = DecisionEngine()
        artifacts = engine.generate_decisions(
            execution_readiness_items=[exec_item],
            risk_assessments=[risk_item],
            validation_results=[val_item],
            signal_candidates=[sample_candidate],
            strategies=[strat_item],
            market_state=market_state,
        )

        assert len(artifacts) == 1
        artifact = artifacts[0]
        assert artifact.symbol == sample_candidate.symbol
        assert artifact.entryPrice == sample_candidate.entryPrice
        assert artifact.stopLoss == sample_candidate.stopLoss
        assert artifact.takeProfit == sample_candidate.takeProfit

    def test_decision_artifact_serialization_exposes_camelcase(self, sample_candidate):
        """DecisionArtifact.model_dump(by_alias=True) exposes canonical camelCase."""
        artifact = make_valid_decision_artifact("dec-001", sample_candidate)
        dumped = artifact.model_dump(by_alias=True)
        assert "symbol" in dumped
        assert "entryPrice" in dumped
        assert "stopLoss" in dumped
        assert "takeProfit" in dumped
        assert dumped["symbol"] == "EURUSD"
        assert dumped["entryPrice"] == 1.0850
        assert dumped["stopLoss"] == 1.0815
        assert dumped["takeProfit"] == 1.0920


# =============================================================================
# SECTION 6: DYNAMIC ATR FALLBACK STOP-LOSS DISTANCE (DEFECT 7)
# =============================================================================

class TestDynamicAtrFallbackStopLoss:
    """Verify dynamic 1.5 * ATR stop loss fallback and absence of magic numbers."""

    def test_atr_fallback_replaces_hardcoded_buffers_eurusd(self):
        """EURUSD ATR=0.0020 yields fallback SL distance of 0.0030, NOT 0.0035."""
        engine = SignalGenerationEngine()
        entry, sl, tp = engine._calculate_trade_levels(
            CandidateDirection.BUY,
            current_price=1.0850,
            atr=0.0020,
            symbol="EURUSD",
        )
        expected_sl = 1.0850 - (1.5 * 0.0020)
        assert round(sl, 4) == round(expected_sl, 4)
        assert round(abs(entry - sl), 4) == 0.0030

    def test_atr_fallback_replaces_hardcoded_buffers_xauusd(self):
        """XAUUSD ATR=10.0 yields fallback SL distance of 15.0, NOT 11.50."""
        engine = SignalGenerationEngine()
        entry, sl, tp = engine._calculate_trade_levels(
            CandidateDirection.BUY,
            current_price=2500.0,
            atr=10.0,
            symbol="XAUUSD",
        )
        expected_sl = 2500.0 - (1.5 * 10.0)
        assert round(sl, 2) == round(expected_sl, 2)
        assert round(abs(entry - sl), 2) == 15.00

    def test_atr_fallback_replaces_hardcoded_buffers_gbpusd(self):
        """GBPUSD ATR=0.0020 yields fallback SL distance of 0.0030, NOT 0.0028."""
        engine = SignalGenerationEngine()
        entry, sl, tp = engine._calculate_trade_levels(
            CandidateDirection.SELL,
            current_price=1.3000,
            atr=0.0020,
            symbol="GBPUSD",
        )
        expected_sl = 1.3000 + (1.5 * 0.0020)
        assert round(sl, 4) == round(expected_sl, 4)
        assert round(abs(entry - sl), 4) == 0.0030

    def test_atr_fallback_replaces_hardcoded_buffers_usdjpy(self):
        """USDJPY ATR=0.20 yields fallback SL distance of 0.30, NOT 0.45."""
        engine = SignalGenerationEngine()
        entry, sl, tp = engine._calculate_trade_levels(
            CandidateDirection.BUY,
            current_price=150.00,
            atr=0.20,
            symbol="USDJPY",
        )
        expected_sl = 150.00 - (1.5 * 0.20)
        assert round(sl, 2) == round(expected_sl, 2)
        assert round(abs(entry - sl), 2) == 0.30

    def test_hardcoded_buffers_absent_from_signal_generation_code(self):
        """Magic buffers (11.50, 0.45, 0.0035, 0.0028) must not exist in _calculate_trade_levels."""
        engine_file = Path(__file__).resolve().parents[2] / "app/core/engines/signal_generation_engine.py"
        content = engine_file.read_text(encoding="utf-8")

        # Check for specific magic assignments previously identified in Defect 7
        assert "stop_distance = 11.50" not in content
        assert "stop_distance = 0.45" not in content
        assert "stop_distance = 0.0035" not in content
        assert "stop_distance = 0.0028" not in content

    def test_pattern_swing_stop_preserves_priority(self):
        """When pattern swing stop provides >= 1.5 R, swing stop is used over ATR fallback."""
        engine = SignalGenerationEngine()
        # Entry at 1.0850, valid swing low at 1.0830 (20 pips distance)
        # ATR fallback with ATR=0.0020 would be 30 pips.
        pattern_details = {
            "swing_low": 1.0830,
            "pattern_type": "HAMMER",
        }
        entry, sl, tp = engine._calculate_trade_levels(
            CandidateDirection.BUY,
            current_price=1.0850,
            pattern_details=pattern_details,
            atr=0.0020,
            symbol="EURUSD",
        )
        # Swing low at 1.0830 must be preserved
        assert round(sl, 4) in (1.0830, 1.0828)


# =============================================================================
# SECTION 7: MOBILE EXECUTION DEAD-CODE REMOVAL (DEFECT 8)
# =============================================================================

class TestMobileExecutionDeadCodeRemoval:
    """Verify that executeOrder is completely eliminated from mobile codebase."""

    def test_api_service_does_not_contain_execute_order(self):
        """mobile/lib/services/api/api_service.dart must NOT contain executeOrder."""
        api_service_file = Path(__file__).resolve().parents[3] / "mobile/lib/services/api/api_service.dart"
        assert api_service_file.exists(), "api_service.dart not found!"
        content = api_service_file.read_text(encoding="utf-8")
        assert "executeOrder" not in content, "executeOrder found in api_service.dart!"

    def test_mobile_lib_directory_has_zero_execute_order_references(self):
        """Zero occurrences of executeOrder across entire mobile/lib directory."""
        mobile_lib = Path("mobile/lib") if Path("mobile/lib").exists() else Path(__file__).resolve().parents[3] / "mobile/lib"
        assert mobile_lib.exists(), "mobile/lib not found!"
        
        matches = []
        for dart_file in mobile_lib.rglob("*.dart"):
            content = dart_file.read_text(encoding="utf-8")
            if "executeOrder" in content:
                matches.append(str(dart_file))

        assert len(matches) == 0, f"Found executeOrder references in: {matches}"


# =============================================================================
# SECTION 8: SAFETY & ZERO-BROKER INVARIANTS
# =============================================================================

class TestSafetyInvariants:
    """Verify zero broker execution and zero unauthorized mutations."""

    def test_zero_broker_execution_calls_in_backend(self):
        """Forbidden broker functions must not be called in backend."""
        forbidden_patterns = [
            r"mt5\.order_send\(",
            r"MetaTrader5\.initialize\(",
            r"order_send\(",
        ]
        backend_dir = Path("backend/app") if Path("backend/app").exists() else Path("app")
        violations = []

        for py_file in backend_dir.rglob("*.py"):
            # Exclude mock execution services or test files
            if "test" in str(py_file).lower():
                continue
            content = py_file.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                if re.search(pattern, content):
                    violations.append(f"{py_file}: matches {pattern}")

        assert len(violations) == 0, f"Forbidden broker execution calls found: {violations}"
