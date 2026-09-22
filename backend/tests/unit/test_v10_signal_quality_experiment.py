"""
Falcon V10 — Signal Quality & Regime-Confluence Experiment Test Suite

Comprehensive verification of:
1. Configuration & defaults (default disabled, version, min sample size)
2. Schema & data models (enums, observation models, analytics response)
3. Market Regime & Strategy Compatibility (compatible, incompatible, avoid conditions, unmapped)
4. Multi-Timeframe Alignment (aligned, conflicted, partially aligned, missing data)
5. Market Structure Confirmation (HH/HL confirmed, LH/LL confirmed, counter-trend invalidation)
6. Liquidity Sweep Confirmation (bearish sweep, bullish sweep, observational vs required)
7. Volatility Suitability (observational ATR/spread, elevated/compressed/suitable, no arbitrary multipliers)
8. Categorical Decision (PASS, REJECT with deterministic reason, UNKNOWN fail-closed)
9. In-Memory Registry & Zero Lookahead Protection (as_of filtering)
10. Sample Adequacy (N < 10 NOT_EVALUABLE, N >= 10 EVALUABLE)
11. Control Group Comparison (baseline vs experimental accepted vs rejected)
12. Structural LIVE Bypass & Safety Boundary (zero broker automation, LIVE isolation)
13. REST API Endpoint (GET /api/v1/analytics/signal-quality, routing, as_of, version filter)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from main import app

from app.core.config.settings import settings
from app.core.analytics.signal_quality_experiment_service import (
    SignalQualityExperimentService,
    signal_quality_experiment_service,
)
from app.schemas.signal_candidate import (
    CandidateCondition,
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateReason,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.market_state import MarketState
from app.schemas.signal_quality_experiment import (
    ExperimentalQualityDecision,
    MtfAlignmentState,
    StructureState,
    LiquidityState,
    VolatilitySuitabilityState,
    RegimeObservation,
    MtfObservation,
    StructureObservation,
    LiquidityObservation,
    VolatilityObservation,
    SignalQualityEvaluationItem,
    SignalQualityAnalyticsResponse,
)


# --------------------------------------------------------------------------
# Helpers & Fixtures
# --------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_experiment_cache():
    """Ensure in-memory experiment cache is clean before and after each test."""
    signal_quality_experiment_service.clear_evaluations()
    yield
    signal_quality_experiment_service.clear_evaluations()


def make_market_state(
    id: str = "ms-1",
    symbol: str = "EURUSD",
    trend: str = "Bullish",
    volatility: str = "Moderate",
    session: str = "London",
    spread: float = 1.0,
    currentNewsImpact: str = "Low",
    atr: float = 0.0015,
) -> MarketState:
    ms = MarketState(
        id=id,
        symbol=symbol,
        trend=trend,
        volatility=volatility,
        session=session,
        spread=spread,
        currentNewsImpact=currentNewsImpact,
        timestamp=datetime.now(timezone.utc),
        dataAgeSeconds=0,
    )
    object.__setattr__(ms, "atr", atr)
    return ms


def make_candidate(
    candidate_id: str = "cand-001",
    symbol: str = "EURUSD",
    strategy_id: str = "strat-001",
    strategy_name: str = "London Breakout",
    direction: CandidateDirection = CandidateDirection.BUY,
    status: CandidateStatus = CandidateStatus.APPROVED,
    evaluated_at: datetime = None,
) -> SignalCandidate:
    now = evaluated_at or datetime.now(timezone.utc)
    return SignalCandidate(
        id=candidate_id,
        symbol=symbol,
        strategyId=strategy_id,
        strategyName=strategy_name,
        strategyVersion="1.0.0",
        strategyGrade="A",
        strategyScore=85,
        direction=direction,
        confidence=80,
        readinessScore=85,
        entryPrice=1.0850,
        stopLoss=1.0820,
        takeProfit=1.0910,
        riskReward=2.0,
        status=status,
        generatedAt=now,
        reasons=[CandidateReason(title="Trend", description="Bullish trend", passed=True)],
        conditions=[CandidateCondition(title="Spread", description="Spread OK", passed=True)],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="Moderate",
            session="London",
            spread=1.2,
            newsImpact="Low",
            marketSentiment="Bullish",
            marketConfidence=85,
            atr=0.0015,
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=85,
            strategyScore=80,
            sessionScore=85,
            sentimentScore=80,
            newsScore=90,
        ),
        evaluationDurationMs=15,
        marketDataAgeSeconds=5,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
    )


# ==========================================================================
# 1. Configuration & Defaults
# ==========================================================================

def test_default_settings():
    assert settings.SIGNAL_QUALITY_EXPERIMENT_ENABLED is False
    assert settings.SIGNAL_QUALITY_EXPERIMENT_VERSION == "1.0.0"
    assert settings.SIGNAL_QUALITY_MIN_SAMPLE_SIZE == 10


def test_settings_types():
    assert isinstance(settings.SIGNAL_QUALITY_EXPERIMENT_ENABLED, bool)
    assert isinstance(settings.SIGNAL_QUALITY_EXPERIMENT_VERSION, str)
    assert isinstance(settings.SIGNAL_QUALITY_MIN_SAMPLE_SIZE, int)


# ==========================================================================
# 2. Schema & Enums
# ==========================================================================

def test_decision_enums():
    assert ExperimentalQualityDecision.PASS == "PASS"
    assert ExperimentalQualityDecision.REJECT == "REJECT"
    assert ExperimentalQualityDecision.UNKNOWN == "UNKNOWN"
    assert ExperimentalQualityDecision.NOT_APPLICABLE == "NOT_APPLICABLE"


def test_mtf_enums():
    assert MtfAlignmentState.ALIGNED == "ALIGNED"
    assert MtfAlignmentState.PARTIALLY_ALIGNED == "PARTIALLY_ALIGNED"
    assert MtfAlignmentState.CONFLICTED == "CONFLICTED"
    assert MtfAlignmentState.UNKNOWN == "UNKNOWN"


def test_structure_enums():
    assert StructureState.CONFIRMED == "CONFIRMED"
    assert StructureState.UNCONFIRMED == "UNCONFIRMED"
    assert StructureState.INVALIDATED == "INVALIDATED"
    assert StructureState.UNKNOWN == "UNKNOWN"


def test_liquidity_enums():
    assert LiquidityState.CONFIRMED == "CONFIRMED"
    assert LiquidityState.SWEEP_DETECTED == "SWEEP_DETECTED"
    assert LiquidityState.NO_SWEEP == "NO_SWEEP"
    assert LiquidityState.UNKNOWN == "UNKNOWN"


def test_volatility_enums():
    assert VolatilitySuitabilityState.SUITABLE == "SUITABLE"
    assert VolatilitySuitabilityState.ELEVATED == "ELEVATED"
    assert VolatilitySuitabilityState.COMPRESSED == "COMPRESSED"
    assert VolatilitySuitabilityState.UNKNOWN == "UNKNOWN"


# ==========================================================================
# 3. Market Regime & Strategy Compatibility
# ==========================================================================

def test_regime_compatible_trending():
    cand = make_candidate(strategy_id="strat-001")  # London Breakout requires Trending / Volatile
    market_state = make_market_state(
        id="ms-1",
        symbol="EURUSD",
        trend="Bullish",
        volatility="Moderate",
        session="London",
        spread=1.1,
        currentNewsImpact="Low",
    )
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=market_state)
    assert item.regimeObservation.strategyCompatibility == "COMPATIBLE"
    assert item.regimeObservation.avoidConditionMatched is False


def test_regime_incompatible_ranging():
    # London Breakout avoids "Ranging Markets" or incompatible with Ranging
    cand = make_candidate(strategy_id="strat-002")  # Gold Trend Continuation avoids Ranging Markets
    market_state = make_market_state(
        id="ms-2",
        symbol="XAUUSD",
        trend="Ranging",
        volatility="Low",
        session="London",
        spread=1.5,
        currentNewsImpact="Low",
    )
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=market_state)
    assert item.regimeObservation.avoidConditionMatched is True or item.regimeObservation.strategyCompatibility == "INCOMPATIBLE"
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT
    assert any("Regime" in r for r in item.rejectionReasons)


def test_regime_avoid_condition_high_impact_news():
    cand = make_candidate(strategy_id="strat-001")  # avoidConditions includes High Impact News
    market_state = make_market_state(
        id="ms-3",
        symbol="EURUSD",
        trend="Bullish",
        volatility="Moderate",
        session="London",
        spread=1.0,
        currentNewsImpact="High",
    )
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=market_state)
    assert item.regimeObservation.avoidConditionMatched is True
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT
    assert any("avoid condition" in r.lower() for r in item.rejectionReasons)


def test_regime_missing_market_state():
    cand = make_candidate(strategy_id="strat-001")
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=None)
    assert item.regimeObservation.regime == "UNKNOWN"
    assert item.regimeObservation.avoidConditionMatched is False


def test_regime_unmapped_strategy():
    cand = make_candidate(strategy_id="strat-nonexistent")
    market_state = make_market_state(
        id="ms-4",
        symbol="EURUSD",
        trend="Bullish",
        volatility="Moderate",
        session="London",
        spread=1.0,
    )
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=market_state)
    assert item.regimeObservation.strategyCompatibility == "NOT_APPLICABLE"


# ==========================================================================
# 4. Multi-Timeframe Alignment
# ==========================================================================

def test_mtf_aligned_buy():
    cand = make_candidate(direction=CandidateDirection.BUY)
    mtf_data = {
        "H4": {"trend": "BULLISH"},
        "H1": {"trend": "BULLISH"},
        "M15": {"trend": "BULLISH"},
    }
    item = signal_quality_experiment_service.evaluate_candidate(cand, mtf_data=mtf_data)
    assert item.mtfObservation.state == MtfAlignmentState.ALIGNED
    assert item.mtfObservation.confluenceScore == 100.0
    assert "H4" in item.mtfObservation.alignedTimeframes


def test_mtf_conflicted_higher_timeframe_opposing_buy():
    cand = make_candidate(direction=CandidateDirection.BUY)
    mtf_data = {
        "H4": {"trend": "BEARISH"},
        "H1": {"trend": "BULLISH"},
        "M15": {"trend": "BULLISH"},
    }
    item = signal_quality_experiment_service.evaluate_candidate(cand, mtf_data=mtf_data)
    assert item.mtfObservation.state == MtfAlignmentState.CONFLICTED
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT
    assert any("MTF" in r for r in item.rejectionReasons)


def test_mtf_aligned_sell():
    cand = make_candidate(direction=CandidateDirection.SELL)
    mtf_data = {
        "H4": {"trend": "BEARISH"},
        "H1": {"trend": "BEARISH"},
        "M15": {"trend": "BEARISH"},
    }
    item = signal_quality_experiment_service.evaluate_candidate(cand, mtf_data=mtf_data)
    assert item.mtfObservation.state == MtfAlignmentState.ALIGNED
    assert item.mtfObservation.confluenceScore == 100.0


def test_mtf_conflicted_higher_timeframe_opposing_sell():
    cand = make_candidate(direction=CandidateDirection.SELL)
    mtf_data = {
        "H4": {"trend": "BULLISH"},
        "H1": {"trend": "BEARISH"},
    }
    item = signal_quality_experiment_service.evaluate_candidate(cand, mtf_data=mtf_data)
    assert item.mtfObservation.state == MtfAlignmentState.CONFLICTED
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT


def test_mtf_missing_data():
    cand = make_candidate()
    item = signal_quality_experiment_service.evaluate_candidate(cand, mtf_data=None)
    assert item.mtfObservation.state == MtfAlignmentState.UNKNOWN
    assert item.mtfObservation.confluenceScore == 0.0


# ==========================================================================
# 5. Market Structure Confirmation
# ==========================================================================

def test_structure_buy_confirmed_higher_high_higher_low():
    cand = make_candidate(direction=CandidateDirection.BUY)
    # 10 candles: first 5 at lower range, next 5 at higher range (HH + HL)
    candles = [
        {"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(5)
    ] + [
        {"high": 1.0850, "low": 1.0770, "close": 1.0830} for _ in range(5)
    ]
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.structureObservation.state == StructureState.CONFIRMED
    assert item.structureObservation.swingStructure == "HH_HL"
    assert item.structureObservation.lastEvent == "BOS_BULLISH"


def test_structure_buy_invalidated_lower_high_lower_low():
    cand = make_candidate(direction=CandidateDirection.BUY)
    # 10 candles: first 5 at higher range, next 5 at lower range (LH + LL opposes BUY)
    candles = [
        {"high": 1.0900, "low": 1.0850, "close": 1.0880} for _ in range(5)
    ] + [
        {"high": 1.0840, "low": 1.0780, "close": 1.0800} for _ in range(5)
    ]
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.structureObservation.state == StructureState.INVALIDATED
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT
    assert any("Structure" in r for r in item.rejectionReasons)


def test_structure_sell_confirmed_lower_high_lower_low():
    cand = make_candidate(direction=CandidateDirection.SELL)
    candles = [
        {"high": 1.0900, "low": 1.0850, "close": 1.0880} for _ in range(5)
    ] + [
        {"high": 1.0840, "low": 1.0780, "close": 1.0800} for _ in range(5)
    ]
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.structureObservation.state == StructureState.CONFIRMED
    assert item.structureObservation.swingStructure == "LH_LL"
    assert item.structureObservation.lastEvent == "BOS_BEARISH"


def test_structure_sell_invalidated_higher_high_higher_low():
    cand = make_candidate(direction=CandidateDirection.SELL)
    candles = [
        {"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(5)
    ] + [
        {"high": 1.0850, "low": 1.0770, "close": 1.0830} for _ in range(5)
    ]
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.structureObservation.state == StructureState.INVALIDATED
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT


def test_structure_insufficient_candles():
    cand = make_candidate()
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=[{"high": 1.0, "low": 0.9, "close": 0.95}])
    assert item.structureObservation.state == StructureState.UNKNOWN


# ==========================================================================
# 6. Liquidity Sweep Confirmation
# ==========================================================================

def test_liquidity_bearish_sweep_detected():
    cand = make_candidate(direction=CandidateDirection.SELL)
    # Prior bars resistance at 1.0850
    candles = [
        {"high": 1.0850, "low": 1.0800, "close": 1.0820} for _ in range(5)
    ]
    # Latest candle pierces 1.0850 reaching 1.0865, but closes below at 1.0840
    candles.append({"high": 1.0865, "low": 1.0830, "close": 1.0840})
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.liquidityObservation.state == LiquidityState.SWEEP_DETECTED
    assert item.liquidityObservation.trapType == "BEARISH_SWEEP"
    assert item.liquidityObservation.sweptLevel == 1.0850


def test_liquidity_bullish_sweep_detected():
    cand = make_candidate(direction=CandidateDirection.BUY)
    # Prior bars support at 1.0750
    candles = [
        {"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(5)
    ]
    # Latest candle pierces 1.0750 reaching 1.0735, but closes above at 1.0760
    candles.append({"high": 1.0770, "low": 1.0735, "close": 1.0760})
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.liquidityObservation.state == LiquidityState.SWEEP_DETECTED
    assert item.liquidityObservation.trapType == "BULLISH_SWEEP"
    assert item.liquidityObservation.sweptLevel == 1.0750


def test_liquidity_observational_for_regular_strategy():
    # Strategy that does not require sweep
    cand = make_candidate(strategy_id="strat-001", strategy_name="London Breakout")
    candles = [{"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(6)]
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.liquidityObservation.state == LiquidityState.NO_SWEEP
    # Regular strategy is NOT rejected for lacking sweep
    assert not any("Liquidity requirement" in r for r in item.rejectionReasons)


def test_liquidity_required_strategy_rejects_when_no_sweep():
    # Strategy that explicitly requires liquidity sweep
    cand = make_candidate(strategy_id="strat-sweep-001", strategy_name="Liquidity Sweep Sniper")
    candles = [{"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(6)]
    item = signal_quality_experiment_service.evaluate_candidate(cand, candles=candles)
    assert item.liquidityObservation.state == LiquidityState.NO_SWEEP
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT
    assert any("Liquidity requirement not met" in r for r in item.rejectionReasons)


# ==========================================================================
# 7. Volatility Suitability (Purely Observational)
# ==========================================================================

def test_volatility_observational_suitable():
    cand = make_candidate()
    ms = make_market_state(
        id="ms-5",
        symbol="EURUSD",
        trend="Bullish",
        volatility="Moderate",
        session="London",
        spread=1.2,
        atr=0.0014,
    )
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms)
    assert item.volatilityObservation.state == VolatilitySuitabilityState.SUITABLE
    assert item.volatilityObservation.atr == 0.0014
    assert item.volatilityObservation.spread == 1.2
    assert "no arbitrary" in item.volatilityObservation.details.lower()


def test_volatility_observational_elevated():
    cand = make_candidate()
    ms = make_market_state(
        id="ms-6",
        symbol="EURUSD",
        trend="Bullish",
        volatility="Extreme",
        session="London",
        spread=3.5,
        atr=0.0045,
    )
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms)
    assert item.volatilityObservation.state == VolatilitySuitabilityState.ELEVATED
    assert item.volatilityObservation.atr == 0.0045


def test_volatility_observational_compressed():
    cand = make_candidate()
    ms = make_market_state(
        id="ms-7",
        symbol="EURUSD",
        trend="Ranging",
        volatility="Low",
        session="Asian",
        spread=0.8,
        atr=0.0006,
    )
    item = signal_quality_experiment_service.evaluate_candidate(cand, market_state=ms)
    assert item.volatilityObservation.state == VolatilitySuitabilityState.COMPRESSED


# ==========================================================================
# 8. Categorical Decision & Rejection Over Manufacturing
# ==========================================================================

def test_all_components_aligned_passes():
    cand = make_candidate(strategy_id="strat-001", direction=CandidateDirection.BUY)
    ms = make_market_state(
        id="ms-8",
        symbol="EURUSD",
        trend="Bullish",
        volatility="Moderate",
        session="London",
        spread=1.0,
        currentNewsImpact="Low",
    )
    mtf = {"H4": {"trend": "BULLISH"}, "H1": {"trend": "BULLISH"}}
    candles = [
        {"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(5)
    ] + [
        {"high": 1.0850, "low": 1.0770, "close": 1.0830} for _ in range(5)
    ]

    item = signal_quality_experiment_service.evaluate_candidate(
        cand, market_state=ms, mtf_data=mtf, candles=candles
    )
    assert item.experimentalDecision == ExperimentalQualityDecision.PASS
    assert len(item.rejectionReasons) == 0
    assert item.provenance == "PAPER_EXPERIMENT_ONLY"
    assert item.experimentVersion == "1.0.0"


def test_multiple_conflicts_accumulates_rejection_reasons():
    # London Breakout in Ranging (avoid condition) + MTF conflict + Structure conflict
    cand = make_candidate(strategy_id="strat-001", direction=CandidateDirection.BUY)
    ms = make_market_state(
        id="ms-9",
        symbol="EURUSD",
        trend="Ranging",
        volatility="Moderate",
        session="London",
        spread=1.0,
        currentNewsImpact="High",
    )
    mtf = {"H4": {"trend": "BEARISH"}}
    candles = [
        {"high": 1.0900, "low": 1.0850, "close": 1.0880} for _ in range(5)
    ] + [
        {"high": 1.0840, "low": 1.0780, "close": 1.0800} for _ in range(5)
    ]

    item = signal_quality_experiment_service.evaluate_candidate(
        cand, market_state=ms, mtf_data=mtf, candles=candles
    )
    assert item.experimentalDecision == ExperimentalQualityDecision.REJECT
    assert len(item.rejectionReasons) >= 2


def test_fails_closed_to_unknown_when_no_data():
    cand = make_candidate(strategy_id="strat-nonexistent")
    item = signal_quality_experiment_service.evaluate_candidate(cand)
    assert item.experimentalDecision == ExperimentalQualityDecision.UNKNOWN


# ==========================================================================
# 9. In-Memory Registry & Zero Lookahead Protection
# ==========================================================================

def test_zero_lookahead_as_of_filtering():
    t0 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    t_past = t0 - timedelta(hours=2)
    t_future = t0 + timedelta(hours=2)

    # 3 past evaluations
    for i in range(3):
        cand = make_candidate(candidate_id=f"past-{i}", evaluated_at=t_past)
        signal_quality_experiment_service.evaluate_candidate(cand, as_of=t_past)

    # 4 future evaluations
    for i in range(4):
        cand = make_candidate(candidate_id=f"future-{i}", evaluated_at=t_future)
        signal_quality_experiment_service.evaluate_candidate(cand, as_of=t_future)

    # Query with as_of=t0: must only return 3 past items
    res = signal_quality_experiment_service.get_signal_quality_analytics(as_of=t0)
    assert res.sampleSize == 3
    assert all(e.evaluatedAt <= t0 for e in res.evaluations)

    # Query with no as_of: returns all 7 items
    res_all = signal_quality_experiment_service.get_signal_quality_analytics()
    assert res_all.sampleSize == 7


# ==========================================================================
# 10. Sample Adequacy
# ==========================================================================

def test_sample_adequacy_not_evaluable_below_threshold():
    # Insert 5 evaluations (< 10)
    for i in range(5):
        cand = make_candidate(candidate_id=f"sub-{i}")
        signal_quality_experiment_service.evaluate_candidate(cand)

    res = signal_quality_experiment_service.get_signal_quality_analytics()
    assert res.sampleSize == 5
    assert res.minSampleSize == 10
    assert res.sampleAdequacy == "NOT_EVALUABLE"
    assert any("NOT_EVALUABLE" in note for note in res.summaryNotes)


def test_sample_adequacy_evaluable_at_threshold():
    # Insert 10 evaluations (>= 10)
    for i in range(10):
        cand = make_candidate(candidate_id=f"thresh-{i}")
        signal_quality_experiment_service.evaluate_candidate(cand)

    res = signal_quality_experiment_service.get_signal_quality_analytics()
    assert res.sampleSize == 10
    assert res.minSampleSize == 10
    assert res.sampleAdequacy == "EVALUABLE"
    assert any("meets observation threshold" in note for note in res.summaryNotes)


# ==========================================================================
# 11. Control Group Comparison & Outcome Tracking
# ==========================================================================

def test_control_group_comparison_with_outcomes():
    # Generate 12 passed evaluations
    ms = make_market_state(trend="Bullish", volatility="Moderate", currentNewsImpact="Low")
    mtf = {"H4": {"trend": "BULLISH"}, "H1": {"trend": "BULLISH"}}
    candles = [
        {"high": 1.0800, "low": 1.0750, "close": 1.0780} for _ in range(5)
    ] + [
        {"high": 1.0850, "low": 1.0770, "close": 1.0830} for _ in range(5)
    ]

    for i in range(12):
        cand = make_candidate(candidate_id=f"trade-{i}", strategy_id="strat-001")
        signal_quality_experiment_service.evaluate_candidate(
            cand, market_state=ms, mtf_data=mtf, candles=candles
        )

    # Record 2 wins and 1 loss on passed items
    signal_quality_experiment_service.record_trade_outcome("trade-0", 25.0, "CLOSED_PROFIT")
    signal_quality_experiment_service.record_trade_outcome("trade-1", 30.0, "CLOSED_PROFIT")
    signal_quality_experiment_service.record_trade_outcome("trade-2", -15.0, "CLOSED_LOSS")

    res = signal_quality_experiment_service.get_signal_quality_analytics()
    assert res.sampleAdequacy == "EVALUABLE"
    accepted = res.controlGroupComparison["experimentalAcceptedGroup"]
    assert accepted["tradesWithOutcome"] == 3
    assert accepted["winRate"] == round((2 / 3) * 100.0, 2)
    assert accepted["totalPnl"] == 40.0


# ==========================================================================
# 12. Structural LIVE Bypass & Safety Verification
# ==========================================================================

def test_broker_safety_assertion():
    # Service explicitly asserts broker safety
    signal_quality_experiment_service.assert_no_broker_automation()


def test_live_mode_isolation():
    # Ensure that evaluating a candidate in the experiment does not modify
    # any live settings or Guardian thresholds
    initial_mode = settings.EXECUTION_MODE
    cand = make_candidate()
    signal_quality_experiment_service.evaluate_candidate(cand)
    assert settings.EXECUTION_MODE == initial_mode


# ==========================================================================
# 13. REST API Endpoint
# ==========================================================================

client = TestClient(app)


def test_api_signal_quality_empty():
    response = client.get("/api/v1/analytics/signal-quality")
    assert response.status_code == 200
    data = response.json()
    assert "experimentEnabled" in data
    assert data["experimentVersion"] == "1.0.0"
    assert data["sampleAdequacy"] == "NOT_EVALUABLE"
    assert data["sampleSize"] == 0


def test_api_signal_quality_with_evaluations():
    # Populate cache
    for i in range(10):
        cand = make_candidate(candidate_id=f"api-{i}")
        signal_quality_experiment_service.evaluate_candidate(cand)

    response = client.get("/api/v1/analytics/signal-quality")
    assert response.status_code == 200
    data = response.json()
    assert data["sampleSize"] == 10
    assert data["sampleAdequacy"] == "EVALUABLE"
    assert len(data["evaluations"]) == 10


def test_api_signal_quality_as_of_filtering():
    t0 = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)
    t_past = t0 - timedelta(hours=1)
    t_future = t0 + timedelta(hours=1)

    cand1 = make_candidate(candidate_id="api-past", evaluated_at=t_past)
    signal_quality_experiment_service.evaluate_candidate(cand1, as_of=t_past)

    cand2 = make_candidate(candidate_id="api-future", evaluated_at=t_future)
    signal_quality_experiment_service.evaluate_candidate(cand2, as_of=t_future)

    as_of_iso = t0.strftime("%Y-%m-%dT%H:%M:%SZ")
    response = client.get(f"/api/v1/analytics/signal-quality?as_of={as_of_iso}")
    assert response.status_code == 200
    data = response.json()
    assert data["sampleSize"] == 1
    assert data["evaluations"][0]["candidateId"] == "api-past"


def test_api_routing_no_analytics_id_collision():
    # Ensure /signal-quality does not hit /{analytics_id}
    response = client.get("/api/v1/analytics/signal-quality")
    assert response.status_code == 200
    # A report requested on non-existent id returns 404
    bad_resp = client.get("/api/v1/analytics/non-existent-id")
    assert bad_resp.status_code == 404
