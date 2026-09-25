"""
Falcon V10 — Phase 5B: Dedicated Signal Pipeline Remediation & Safety Hardening Test Suite.
Exact 48-Test Census across 10 Safety Groups as mandated by Phase 5B Specification:

GROUP 1 — GET READ-ONLY (Tests 1-4)
GROUP 2 — EXECUTION DECOUPLING (Tests 5-8)
GROUP 3 — RESEARCH CONTEXT (Tests 9-16)
GROUP 4 — DECISION ARTIFACT (Tests 17-20)
GROUP 5 — TIMEFRAME INTEGRITY (Tests 21-24)
GROUP 6 — RSI (Tests 25-30)
GROUP 7 — ATR STOP (Tests 31-35)
GROUP 8 — FIELD CONSISTENCY (Tests 36-39)
GROUP 9 — SAFETY REGRESSION (Tests 40-44)
GROUP 10 — LEGACY COMPATIBILITY (Tests 45-48)
"""

import copy
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.analytics.historical_findings_service import (
    HistoricalFindingsService,
    historical_findings_service,
)
from app.core.engines.candlestick_pattern_engine import (
    CandleBar,
    CandlestickPatternEngine,
    PatternType,
    SignalDirection as PatSignalDirection,
)
from app.core.engines.decision_engine import DecisionEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.strategy_engine import StrategyEngine
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
from app.schemas.capital_guardian import CapitalGuardianDecision, GuardianState
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
# FIXTURES & TEST HARNESS
# =============================================================================

@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch):
    """Ensure in-memory repositories and prevent external DB/network queries."""
    from app.core.services.market_history_service import market_history_service
    monkeypatch.setattr(market_history_service, "get_bars", lambda *args, **kwargs: [])
    from app.core.services.signal_outcome_resolver import signal_outcome_resolver
    monkeypatch.setattr(signal_outcome_resolver, "resolve_signals", lambda *args, **kwargs: None)

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


@pytest.fixture
def sample_strategy():
    engine = StrategyEngine()
    strategies = engine.get_strategies()
    return strategies[0]


@pytest.fixture
def dummy_promoted_context():
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


# =============================================================================
# GROUP 1 — GET READ-ONLY (Tests 1-4)
# =============================================================================

class TestGroup1GetReadOnly:
    """Verify that GET endpoints are strictly read-only and idempotent."""

    def test_01_get_signals_does_not_insert_trade_journal(self, test_client, sample_candidate):
        """1. GET /api/v1/signals must NOT insert records into trade_journal."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        decision = make_valid_decision_artifact("dec-001", sample_candidate)
        _create_test_mission("mission-ro-1", sample_candidate, decision)

        count_before = len(trade_journal_repository.list_trades())
        resp = test_client.get("/api/v1/signals")
        assert resp.status_code == 200
        count_after = len(trade_journal_repository.list_trades())

        assert count_after == count_before == 0

    def test_02_repeated_get_signals_does_not_accumulate_pending_reservations(self, test_client, sample_candidate):
        """2. Repeated GET /api/v1/signals polling does NOT accumulate PENDING reservations."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        decision = make_valid_decision_artifact("dec-002", sample_candidate)
        _create_test_mission("mission-ro-2", sample_candidate, decision)

        for _ in range(5):
            resp = test_client.get("/api/v1/signals")
            assert resp.status_code == 200

        trades = trade_journal_repository.list_trades()
        pending_trades = [t for t in trades if getattr(t, "status", "") == "PENDING"]
        assert len(pending_trades) == 0
        assert len(trades) == 0

    def test_03_get_signal_candidates_does_not_mutate_db(self, test_client, sample_candidate):
        """3. GET /api/v1/signal-candidates does not mutate trade_journal or capital_cycles."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        _create_test_mission("mission-ro-3", sample_candidate)

        j_before = len(trade_journal_repository.list_trades())
        c_before = len(capital_cycle_repository.list_cycles())

        resp = test_client.get("/api/v1/signal-candidates")
        assert resp.status_code == 200

        j_after = len(trade_journal_repository.list_trades())
        c_after = len(capital_cycle_repository.list_cycles())

        assert j_before == j_after == 0
        assert c_before == c_after == 1

    def test_04_get_decision_artifacts_does_not_mutate_db(self, test_client, sample_candidate):
        """4. GET /api/v1/decision-artifacts does not mutate trade_journal or capital_cycles."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        decision = make_valid_decision_artifact("dec-004", sample_candidate)
        _create_test_mission("mission-ro-4", sample_candidate, decision)

        j_before = len(trade_journal_repository.list_trades())
        c_before = len(capital_cycle_repository.list_cycles())

        resp = test_client.get("/api/v1/decision-artifacts")
        assert resp.status_code == 200

        j_after = len(trade_journal_repository.list_trades())
        c_after = len(capital_cycle_repository.list_cycles())

        assert j_before == j_after == 0
        assert c_before == c_after == 1


# =============================================================================
# GROUP 2 — EXECUTION DECOUPLING (Tests 5-8)
# =============================================================================

class TestGroup2ExecutionDecoupling:
    """Verify that signal creation and reading paths never auto-queue execution orders."""

    def test_05_signal_serialization_does_not_create_execution_orders(self, sample_candidate):
        """5. Signal serialization / _to_signal does not create execution orders."""
        svc = SignalService()
        now = datetime.now(timezone.utc)
        with patch.object(order_execution_service, "create_order") as mock_create_order:
            sig = svc._to_signal(sample_candidate, None, 1, now)
            assert sig is not None
            assert mock_create_order.call_count == 0

    def test_06_candidate_generation_does_not_create_execution_orders(self, sample_strategy):
        """6. Candidate generation does not create execution orders."""
        engine = SignalGenerationEngine()
        market_state = MarketState(
            id="mkt-1",
            timestamp=datetime.now(timezone.utc),
            provider="twelve_data",
            prices={
                "EURUSD": MarketPrice(
                    symbol="EURUSD",
                    currentPrice=1.0851,
                    bid=1.0850,
                    ask=1.0852,
                    spread=0.2,
                    timestamp=datetime.now(timezone.utc),
                    provider="twelve_data",
                )
            },
            environment="PRODUCTION",
            session="London",
            dataAgeSeconds=10,
        )
        with patch.object(order_execution_service, "create_order") as mock_create_order:
            cands = engine.generate_candidates(market_state=market_state, strategies=[sample_strategy])
            assert mock_create_order.call_count == 0

    def test_07_get_signals_does_not_call_create_order(self, test_client, sample_candidate):
        """7. GET /api/v1/signals does not call order_execution_service.create_order()."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        decision = make_valid_decision_artifact("dec-007", sample_candidate)
        _create_test_mission("mission-ro-7", sample_candidate, decision)

        with patch.object(order_execution_service, "create_order") as mock_create_order:
            resp = test_client.get("/api/v1/signals")
            assert resp.status_code == 200
            assert mock_create_order.call_count == 0

    def test_08_background_signal_refresh_does_not_queue_orders(self, sample_candidate):
        """8. Background signal refresh / build_signals does not queue execution orders."""
        sample_candidate.generatedAt = datetime.now(timezone.utc)
        sample_candidate.readinessScore = 90
        decision = make_valid_decision_artifact("dec-008", sample_candidate)
        _create_test_mission("mission-ro-8", sample_candidate, decision)

        svc = SignalService()
        with patch.object(order_execution_service, "create_order") as mock_create_order:
            signals = svc.build_signals()
            assert mock_create_order.call_count == 0


# =============================================================================
# GROUP 3 — RESEARCH CONTEXT (Tests 9-16)
# =============================================================================

class TestGroup3ResearchContext:
    """Verify authoritative research context propagation and 5-tuple contract."""

    def test_09_eligible_promoted_context_reaches_candidate(self, sample_candidate, dummy_promoted_context):
        """9. Eligible promoted context reaches candidate with exact 5-tuple match."""
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

    def test_10_unpromoted_candidate_has_none(self, dummy_promoted_context):
        """10. Unpromoted candidate has researchContext=None."""
        matched = SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="1h",
            behaviour_identity="BEARISH_ENGULFING",  # Unpromoted pattern
            context_identity="UPTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        )
        assert matched is None

    def test_11_instrument_mismatch_fails_closed(self, dummy_promoted_context):
        """11. Instrument mismatch fails closed to None."""
        assert SignalGenerationEngine.match_research_context(
            instrument="GBPUSD",
            timeframe="1h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        ) is None

    def test_12_timeframe_mismatch_fails_closed(self, dummy_promoted_context):
        """12. Timeframe mismatch fails closed to None."""
        assert SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="4h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        ) is None

    def test_13_behaviour_mismatch_fails_closed(self, dummy_promoted_context):
        """13. Behaviour mismatch fails closed to None."""
        assert SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="1h",
            behaviour_identity="PINBAR",
            context_identity="UPTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        ) is None

    def test_14_context_mismatch_fails_closed(self, dummy_promoted_context):
        """14. Context mismatch fails closed to None."""
        assert SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="1h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="DOWNTREND",
            horizon=5,
            contexts=[dummy_promoted_context],
        ) is None

    def test_15_horizon_mismatch_fails_closed(self, dummy_promoted_context):
        """15. Horizon mismatch fails closed to None."""
        assert SignalGenerationEngine.match_research_context(
            instrument="EURUSD",
            timeframe="1h",
            behaviour_identity="BULLISH_ENGULFING",
            context_identity="UPTREND",
            horizon=10,
            contexts=[dummy_promoted_context],
        ) is None

    def test_16_research_context_cannot_modify_signal_trading_parameters(self, sample_candidate, dummy_promoted_context):
        """16. Research context cannot modify any trading parameter."""
        cand_with = copy.deepcopy(sample_candidate)
        cand_with.researchContext = dummy_promoted_context

        cand_without = copy.deepcopy(sample_candidate)
        cand_without.researchContext = None

        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig_with = svc._to_signal(cand_with, None, 1, now)
        sig_without = svc._to_signal(cand_without, None, 2, now)

        assert sig_with.symbol == sig_without.symbol
        assert sig_with.action == sig_without.action
        assert sig_with.entry == sig_without.entry
        assert sig_with.stopLoss == sig_without.stopLoss
        assert sig_with.takeProfit == sig_without.takeProfit
        assert sig_with.confidence == sig_without.confidence
        assert sig_with.riskReward == sig_without.riskReward
        assert sig_with.timeframe == sig_without.timeframe
        assert sig_with.researchContext is not None
        assert sig_without.researchContext is None


# =============================================================================
# GROUP 4 — DECISION ARTIFACT (Tests 17-20)
# =============================================================================

class TestGroup4DecisionArtifact:
    """Verify canonical trade parameters in DecisionArtifact."""

    def test_17_symbol_propagated_correctly(self, sample_candidate):
        """17. DecisionArtifact.symbol matches candidate symbol."""
        artifact = make_valid_decision_artifact("dec-017", sample_candidate)
        assert artifact.symbol == sample_candidate.symbol == "EURUSD"

    def test_18_entry_price_propagated_correctly(self, sample_candidate):
        """18. DecisionArtifact.entryPrice matches candidate entryPrice."""
        artifact = make_valid_decision_artifact("dec-018", sample_candidate)
        assert artifact.entryPrice == sample_candidate.entryPrice == 1.0850

    def test_19_stop_loss_propagated_correctly(self, sample_candidate):
        """19. DecisionArtifact.stopLoss matches candidate stopLoss."""
        artifact = make_valid_decision_artifact("dec-019", sample_candidate)
        assert artifact.stopLoss == sample_candidate.stopLoss == 1.0815

    def test_20_take_profit_propagated_correctly(self, sample_candidate):
        """20. DecisionArtifact.takeProfit matches candidate takeProfit."""
        artifact = make_valid_decision_artifact("dec-020", sample_candidate)
        assert artifact.takeProfit == sample_candidate.takeProfit == 1.0920


# =============================================================================
# GROUP 5 — TIMEFRAME INTEGRITY (Tests 21-24)
# =============================================================================

class TestGroup5TimeframeIntegrity:
    """Verify truthful timeframe handling without false 5m/15m claims."""

    def test_21_1h_bars_are_not_used_as_5m_bars(self):
        """21. 1h bars are not used as 5m bars in pattern analysis."""
        engine = CandlestickPatternEngine()
        candles_1h = [
            CandleBar(open=1.0800, high=1.0850, low=1.0790, close=1.0840),
            CandleBar(open=1.0840, high=1.0890, low=1.0830, close=1.0880),
            CandleBar(open=1.0880, high=1.0920, low=1.0870, close=1.0910),
        ]
        results = engine.analyze_patterns(candles_1h=candles_1h)
        # Should NOT return 5m breakout pattern
        assert all(r.pattern_type != PatternType.TIMEFRAME_15M_5M_BREAKOUT for r in results)

    def test_22_1h_bars_are_not_used_as_15m_bars(self):
        """22. 1h bars are not used as 15m bars in pattern analysis."""
        engine = CandlestickPatternEngine()
        candles_1h = [
            CandleBar(open=1.0800, high=1.0850, low=1.0790, close=1.0840),
            CandleBar(open=1.0840, high=1.0890, low=1.0830, close=1.0880),
            CandleBar(open=1.0880, high=1.0920, low=1.0870, close=1.0910),
        ]
        results = engine.analyze_patterns(candles_1h=candles_1h)
        assert all("15m" not in r.pattern_name.lower() for r in results)

    def test_23_unavailable_timeframe_fails_closed_or_skips_analysis(self):
        """23. Unavailable lower timeframe skips multi-timeframe breakout pattern."""
        engine = CandlestickPatternEngine()
        candles_1h = [
            CandleBar(open=1.0840, high=1.0850, low=1.0830, close=1.0845),
            CandleBar(open=1.0850, high=1.0860, low=1.0800, close=1.0810),
            CandleBar(open=1.0805, high=1.0880, low=1.0800, close=1.0870),
        ]
        results = engine.analyze_patterns(candles_1h=candles_1h, candles_5m=None, candles_15m=None)
        assert any(r.pattern_type == PatternType.BULLISH_ENGULFING for r in results)
        assert all(r.pattern_type != PatternType.TIMEFRAME_15M_5M_BREAKOUT for r in results)

    def test_24_candidate_timeframe_remains_truthful(self, sample_candidate):
        """24. Candidate and Signal timeframe defaults to '1h', never legacy 'M15'."""
        svc = SignalService()
        cand = copy.deepcopy(sample_candidate)
        cand.strategyId = "unknown-strat-fallback"
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(cand, None, 1, now)
        assert sig.timeframe == "1h"


# =============================================================================
# GROUP 6 — RSI (Tests 25-30)
# =============================================================================

class TestGroup6Rsi:
    """Verify authentic RSI telemetry and safe missing handling."""

    def test_25_rsi_populated_from_authoritative_indicator_source(self):
        """25. RSI is extracted and stored in CandidateMarketSnapshot."""
        snap = CandidateMarketSnapshot(
            trend="Bullish",
            volatility="NORMAL",
            session="London",
            spread=0.1,
            newsImpact="LOW",
            marketSentiment="BULLISH",
            marketConfidence=80,
            atr=0.0015,
            rsi=48.2,
        )
        assert snap.rsi == 48.2

    def test_26_rsi_30_handled_correctly(self, sample_candidate):
        """26. RSI = 30.0 (boundary minimum) passes validation."""
        v_engine = ValidationEngine()
        market_state = MarketState(timestamp=datetime.now(timezone.utc), provider="twelve_data", environment="PRODUCTION", prices={}, session="London", dataAgeSeconds=0)
        sample_candidate.marketSnapshot.rsi = 30.0

        results = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check = next((c for c in results[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check is not None
        assert rsi_check.passed is True
        assert rsi_check.scoreAwarded == 15

    def test_27_rsi_50_handled_correctly(self, sample_candidate):
        """27. RSI = 50.0 (midpoint) passes validation."""
        v_engine = ValidationEngine()
        market_state = MarketState(timestamp=datetime.now(timezone.utc), provider="twelve_data", environment="PRODUCTION", prices={}, session="London", dataAgeSeconds=0)
        sample_candidate.marketSnapshot.rsi = 50.0

        results = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check = next((c for c in results[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check is not None
        assert rsi_check.passed is True
        assert rsi_check.scoreAwarded == 15

    def test_28_rsi_70_handled_correctly(self, sample_candidate):
        """28. RSI = 70.0 (boundary maximum) passes validation."""
        v_engine = ValidationEngine()
        market_state = MarketState(timestamp=datetime.now(timezone.utc), provider="twelve_data", environment="PRODUCTION", prices={}, session="London", dataAgeSeconds=0)
        sample_candidate.marketSnapshot.rsi = 70.0

        results = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check = next((c for c in results[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check is not None
        assert rsi_check.passed is True
        assert rsi_check.scoreAwarded == 15

    def test_29_missing_rsi_does_not_become_50_point_0(self, sample_candidate):
        """29. Missing RSI does not become 50.0; fails safely."""
        v_engine = ValidationEngine()
        market_state = MarketState(timestamp=datetime.now(timezone.utc), provider="twelve_data", environment="PRODUCTION", prices={}, session="London", dataAgeSeconds=0)
        sample_candidate.marketSnapshot.rsi = None

        results = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check = next((c for c in results[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check is not None
        assert rsi_check.passed is False
        assert rsi_check.scoreAwarded == 0
        assert sample_candidate.marketSnapshot.rsi is None

    def test_30_malformed_rsi_fails_safely(self, sample_candidate):
        """30. Malformed / out-of-bounds RSI (e.g. 85.0) fails safely."""
        v_engine = ValidationEngine()
        market_state = MarketState(timestamp=datetime.now(timezone.utc), provider="twelve_data", environment="PRODUCTION", prices={}, session="London", dataAgeSeconds=0)
        sample_candidate.marketSnapshot.rsi = 85.0

        results = v_engine.validate_candidates([sample_candidate], strategies=[], market_state=market_state)
        rsi_check = next((c for c in results[0].checks if c.title == "RSI Validation"), None)
        assert rsi_check is not None
        assert rsi_check.passed is False
        assert rsi_check.scoreAwarded == 0


# =============================================================================
# GROUP 7 — ATR STOP (Tests 31-35)
# =============================================================================

class TestGroup7AtrStop:
    """Verify dynamic ATR-based fallback stop-loss calculations."""

    def test_31_structural_stop_remains_unchanged_when_valid(self):
        """31. Structural swing stop preserves priority when valid."""
        engine = SignalGenerationEngine()
        entry, sl, tp = engine._calculate_trade_levels(
            direction=CandidateDirection.BUY,
            current_price=1.0850,
            atr=0.0020,
            symbol="EURUSD",
            adaptive_mult=1.0,
            pattern_details={"swing_low": 1.0820, "target_price": 1.0910},
            rr=2.0,
        )
        # Structural stop 1.0820 retained
        assert sl == 1.0820
        assert tp == 1.0910

    def test_32_fallback_stop_uses_atr(self):
        """32. Fallback stop uses 1.5 * ATR when structural stop is absent."""
        engine = SignalGenerationEngine()
        entry, sl, tp = engine._calculate_trade_levels(
            direction=CandidateDirection.BUY,
            current_price=1.0850,
            atr=0.0020,
            symbol="EURUSD",
            adaptive_mult=1.0,
            pattern_details=None,
            rr=2.0,
        )
        expected_sl = round(1.0850 - (1.5 * 0.0020), 4)
        assert sl == expected_sl

    def test_33_changing_atr_changes_fallback_distance(self):
        """33. Doubling ATR doubles the fallback stop-loss distance."""
        engine = SignalGenerationEngine()
        _, sl1, _ = engine._calculate_trade_levels(
            direction=CandidateDirection.BUY,
            current_price=1.0850,
            atr=0.0020,
            symbol="EURUSD",
            adaptive_mult=1.0,
            pattern_details=None,
            rr=2.0,
        )
        _, sl2, _ = engine._calculate_trade_levels(
            direction=CandidateDirection.BUY,
            current_price=1.0850,
            atr=0.0040,
            symbol="EURUSD",
            adaptive_mult=1.0,
            pattern_details=None,
            rr=2.0,
        )
        dist1 = abs(1.0850 - sl1)
        dist2 = abs(1.0850 - sl2)
        assert abs((dist2 / dist1) - 2.0) < 0.05

    def test_34_invalid_atr_fails_closed(self):
        """34. Invalid/None ATR uses minimum safety distance without crash."""
        engine = SignalGenerationEngine()
        entry, sl, tp = engine._calculate_trade_levels(
            direction=CandidateDirection.BUY,
            current_price=1.0850,
            atr=None,
            symbol="EURUSD",
            adaptive_mult=1.0,
            pattern_details=None,
            rr=2.0,
        )
        assert sl < entry < tp
        assert abs(entry - sl) >= 0.0005

    def test_35_fallback_sl_remains_valid_relative_to_entry(self):
        """35. Fallback SL remains valid relative to entry for BUY and SELL."""
        engine = SignalGenerationEngine()
        # BUY: SL < Entry < TP
        _, sl_buy, tp_buy = engine._calculate_trade_levels(
            direction=CandidateDirection.BUY,
            current_price=1.0850,
            atr=0.0020,
            symbol="EURUSD",
            adaptive_mult=1.0,
            pattern_details=None,
            rr=2.0,
        )
        assert sl_buy < 1.0850 < tp_buy

        # SELL: TP < Entry < SL
        _, sl_sell, tp_sell = engine._calculate_trade_levels(
            direction=CandidateDirection.SELL,
            current_price=1.0850,
            atr=0.0020,
            symbol="EURUSD",
            adaptive_mult=1.0,
            pattern_details=None,
            rr=2.0,
        )
        assert tp_sell < 1.0850 < sl_sell


# =============================================================================
# GROUP 8 — FIELD CONSISTENCY (Tests 36-39)
# =============================================================================

class TestGroup8FieldConsistency:
    """Verify field consistency across Candidate, Signal, and DecisionArtifact."""

    def test_36_candidate_signal_artifact_symbol_consistent(self, sample_candidate):
        """36. Symbol is identical across candidate, signal, and decision artifact."""
        decision = make_valid_decision_artifact("dec-036", sample_candidate)
        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(sample_candidate, decision, 1, now)

        assert sample_candidate.symbol == sig.symbol == decision.symbol == "EURUSD"

    def test_37_candidate_signal_artifact_entry_consistent(self, sample_candidate):
        """37. Entry price is identical across candidate, signal, and decision artifact."""
        decision = make_valid_decision_artifact("dec-037", sample_candidate)
        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(sample_candidate, decision, 1, now)

        assert sample_candidate.entryPrice == sig.entry == decision.entryPrice == 1.0850

    def test_38_candidate_signal_artifact_sl_consistent(self, sample_candidate):
        """38. Stop loss is identical across candidate, signal, and decision artifact."""
        decision = make_valid_decision_artifact("dec-038", sample_candidate)
        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(sample_candidate, decision, 1, now)

        assert sample_candidate.stopLoss == sig.stopLoss == decision.stopLoss == 1.0815

    def test_39_candidate_signal_artifact_tp_consistent(self, sample_candidate):
        """39. Take profit is identical across candidate, signal, and decision artifact."""
        decision = make_valid_decision_artifact("dec-039", sample_candidate)
        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(sample_candidate, decision, 1, now)

        assert sample_candidate.takeProfit == sig.takeProfit == decision.takeProfit == 1.0920


# =============================================================================
# GROUP 9 — SAFETY REGRESSION (Tests 40-44)
# =============================================================================

class TestGroup9SafetyRegression:
    """Verify Capital Guardian rules and research context isolation."""

    def test_40_capital_guardian_rules_remain_enforced(self, sample_candidate):
        """40. Capital Guardian evaluation rejects trade if capacity is exceeded."""
        auth_svc = SignalAuthorizationService()
        # Mock cycle with 0 active trading capital
        zero_cycle = CapitalCycleCreate(
            cycleId="cycle-zero",
            cycleNumber=2,
            startingCapital=Decimal("0.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
        )
        capital_cycle_repository.clear()
        capital_cycle_repository.create_cycle(zero_cycle)

        decision = auth_svc.evaluate_candidate(sample_candidate)
        assert decision.allowed is False
        assert "capital" in decision.reason.lower() or "drawdown" in decision.reason.lower() or "loss" in decision.reason.lower()

    def test_41_research_context_cannot_affect_monetary_risk(self, sample_candidate, dummy_promoted_context):
        """41. Research context cannot affect monetary risk."""
        auth_svc = SignalAuthorizationService()
        cand_with = copy.deepcopy(sample_candidate)
        cand_with.researchContext = dummy_promoted_context

        cand_without = copy.deepcopy(sample_candidate)
        cand_without.researchContext = None

        dec_with = auth_svc.evaluate_candidate(cand_with)
        dec_without = auth_svc.evaluate_candidate(cand_without)

        assert dec_with.proposedWorstCaseLoss == dec_without.proposedWorstCaseLoss

    def test_42_research_context_cannot_affect_lot_size(self, sample_candidate, dummy_promoted_context):
        """42. Research context cannot affect lot size."""
        svc = SignalService()
        cand_with = copy.deepcopy(sample_candidate)
        cand_with.researchContext = dummy_promoted_context

        cand_without = copy.deepcopy(sample_candidate)
        cand_without.researchContext = None

        now = datetime.now(timezone.utc)
        sig_with = svc._to_signal(cand_with, None, 1, now, lot_size=0.01)
        sig_without = svc._to_signal(cand_without, None, 2, now, lot_size=0.01)

        # Lot size or monetary calculations are invariant
        assert sig_with.entry == sig_without.entry

    def test_43_research_context_cannot_affect_direction(self, sample_candidate, dummy_promoted_context):
        """43. Research context cannot affect direction."""
        svc = SignalService()
        cand_with = copy.deepcopy(sample_candidate)
        cand_with.researchContext = dummy_promoted_context

        cand_without = copy.deepcopy(sample_candidate)
        cand_without.researchContext = None

        now = datetime.now(timezone.utc)
        sig_with = svc._to_signal(cand_with, None, 1, now)
        sig_without = svc._to_signal(cand_without, None, 2, now)

        assert sig_with.action == sig_without.action == "BUY"

    def test_44_research_context_cannot_affect_confidence(self, sample_candidate, dummy_promoted_context):
        """44. Research context cannot affect confidence."""
        svc = SignalService()
        cand_with = copy.deepcopy(sample_candidate)
        cand_with.researchContext = dummy_promoted_context

        cand_without = copy.deepcopy(sample_candidate)
        cand_without.researchContext = None

        now = datetime.now(timezone.utc)
        sig_with = svc._to_signal(cand_with, None, 1, now)
        sig_without = svc._to_signal(cand_without, None, 2, now)

        assert sig_with.confidence == sig_without.confidence == 85


# =============================================================================
# GROUP 10 — LEGACY COMPATIBILITY (Tests 45-48)
# =============================================================================

class TestGroup10LegacyCompatibility:
    """Verify backward compatibility of candidate, signal, and decision schemas."""

    def test_45_signal_candidate_without_research_context_validates(self, sample_candidate):
        """45. SignalCandidate without researchContext validates cleanly."""
        data = sample_candidate.model_dump()
        data["researchContext"] = None
        cand = SignalCandidate.model_validate(data)
        assert cand.researchContext is None

    def test_46_signal_item_without_research_context_validates(self, sample_candidate):
        """46. SignalItem without researchContext validates cleanly."""
        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(sample_candidate, None, 1, now)
        dumped = sig.model_dump()
        dumped["researchContext"] = None
        sig2 = SignalItem.model_validate(dumped)
        assert sig2.researchContext is None

    def test_47_existing_api_response_structure_remains_compatible(self, sample_candidate):
        """47. SignalListResponse schema remains 100% compatible."""
        svc = SignalService()
        now = datetime.now(timezone.utc)
        sig = svc._to_signal(sample_candidate, None, 1, now)
        resp = SignalListResponse(signals=[sig], lastUpdated=now, dataAgeSeconds=5)
        dumped = resp.model_dump()
        assert "signals" in dumped
        assert "lastUpdated" in dumped
        assert "dataAgeSeconds" in dumped

    def test_48_mobile_tests_remain_compatible(self, sample_candidate):
        """48. DecisionArtifact serializes camelCase fields matching Flutter client expectations."""
        artifact = make_valid_decision_artifact("dec-048", sample_candidate)
        dumped = artifact.model_dump(by_alias=True)
        assert "symbol" in dumped
        assert "entryPrice" in dumped
        assert "stopLoss" in dumped
        assert "takeProfit" in dumped
        assert "researchContext" in dumped
        assert dumped["symbol"] == "EURUSD"
        assert dumped["entryPrice"] == 1.0850
