"""
Falcon Phase 7 — Unit Tests: Decision Context Builder (Milestone 1)

Tests the build_context() pure function comprehensively:
  - All inputs present → fully populated context
  - Missing optional inputs → graceful defaults, no crash
  - Candidate direction/confidence/RR are cached correctly
  - Strategy fields are cached correctly
  - Regime report is threaded through (pre-M3 optional)
  - Market state spread/session/trend fallback chain works
  - builtAt is a UTC datetime
  - contextVersion is "1.0"
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.core.engines.decision.context_builder import build_context
from app.schemas.decision_context import DecisionContext


# ─── Helpers ──────────────────────────────────────────────────────────────────

from app.schemas.signal_candidate import SignalCandidate, CandidateDirection, CandidateMarketSnapshot
from app.schemas.market_state import MarketState
from app.schemas.strategy import StrategyItem

def _make_candidate(
    cand_id="cand-001",
    direction="BUY",
    confidence=88,
    rr=2.4,
    spread=0.35,
    session="London",
    trend="Bullish",
    volatility="Moderate",
    news_impact="Low",
):
    snap = CandidateMarketSnapshot.model_construct(
        spread=spread,
        session=session,
        trend=trend,
        volatility=volatility,
        newsImpact=news_impact
    )
    cand = SignalCandidate.model_construct(
        id=cand_id,
        direction=CandidateDirection(direction) if hasattr(CandidateDirection, direction) else direction,
        confidence=confidence,
        riskReward=rr,
        marketSnapshot=snap
    )
    # Ensure direction has .value for test compatibility if it's an enum, or just mock it:
    cand.direction = MagicMock(value=direction)
    return cand


def _make_market_state(
    trend="Bearish",
    session="Asian",
    spread=0.80,
    volatility="High",
    news_impact="High",
    market_open=True,
    data_age=5,
):
    ms = MarketState.model_construct(
        trend=trend,
        session=session,
        spread=spread,
        volatility=volatility,
        currentNewsImpact=news_impact,
        marketOpen=market_open,
        dataAgeSeconds=data_age
    )
    return ms


def _make_strategy(
    strat_id="strat-001",
    name="London Breakout",
    preferred_sessions=None,
    min_confidence=85.0,
    min_rr=2.0,
    avoid_conditions=None,
    market_compatibility=None,
):
    s = StrategyItem.model_construct(
        id=strat_id,
        name=name,
        preferredSessions=preferred_sessions or ["London", "New York"],
        minimumConfidence=min_confidence,
        minimumRiskReward=min_rr,
        avoidConditions=avoid_conditions or ["High Impact News"],
        marketCompatibility=market_compatibility or ["Trending", "Volatile"]
    )
    return s


# ─── Tests ────────────────────────────────────────────────────────────────────

from app.schemas.validation_result import ValidationResult
from app.schemas.risk_assessment import RiskAssessment
from app.schemas.execution_readiness import ExecutionReadiness
from app.schemas.market_regime import MarketRegimeReport

class TestBuildContextAllInputsPresent:
    """All upstream artifacts provided — context must be fully populated."""

    def setup_method(self):
        self.candidate = _make_candidate()
        self.market_state = _make_market_state()
        self.strategy = _make_strategy()
        self.context = build_context(
            candidate_id="cand-001",
            mission_id="mission-001",
            candidate=self.candidate,
            validation=ValidationResult.model_construct(),
            risk=RiskAssessment.model_construct(),
            readiness=ExecutionReadiness.model_construct(),
            strategy=self.strategy,
            market_state=self.market_state,
            regime_report=MarketRegimeReport.model_construct(),
        )

    def test_returns_decision_context_type(self):
        assert isinstance(self.context, DecisionContext)

    def test_candidate_id_stored(self):
        assert self.context.candidateId == "cand-001"

    def test_mission_id_stored(self):
        assert self.context.missionId == "mission-001"

    def test_candidate_direction_cached(self):
        # Candidate snapshot takes priority over market state
        assert self.context.candidateDirection == "BUY"

    def test_candidate_confidence_cached(self):
        assert self.context.candidateConfidence == 88.0

    def test_candidate_rr_cached(self):
        assert self.context.candidateRiskReward == 2.4

    def test_spread_from_candidate_snapshot(self):
        # Candidate snapshot spread (0.35) should take priority over market state spread (0.80)
        assert self.context.spread == 0.35

    def test_session_from_candidate_snapshot(self):
        # Candidate snapshot session ("London") takes priority over market state ("Asian")
        assert self.context.session == "London"

    def test_trend_from_candidate_snapshot(self):
        # Candidate snapshot trend ("Bullish") takes priority over market state ("Bearish")
        assert self.context.trend == "Bullish"

    def test_volatility_from_candidate_snapshot(self):
        assert self.context.volatility == "Moderate"

    def test_news_impact_from_candidate_snapshot(self):
        assert self.context.newsImpact == "Low"

    def test_market_open_from_market_state(self):
        assert self.context.marketOpen is True

    def test_data_age_from_market_state(self):
        assert self.context.dataAgeSeconds == 5

    def test_strategy_id_cached(self):
        assert self.context.strategyId == "strat-001"

    def test_strategy_name_cached(self):
        assert self.context.strategyName == "London Breakout"

    def test_preferred_sessions_cached(self):
        assert "London" in self.context.preferredSessions
        assert "New York" in self.context.preferredSessions

    def test_minimum_confidence_cached(self):
        assert self.context.minimumConfidence == 85.0

    def test_minimum_rr_cached(self):
        assert self.context.minimumRiskReward == 2.0

    def test_avoid_conditions_cached(self):
        assert "High Impact News" in self.context.avoidConditions

    def test_market_compatibility_cached(self):
        assert "Trending" in self.context.marketCompatibility

    def test_built_at_is_utc_datetime(self):
        assert isinstance(self.context.builtAt, datetime)
        assert self.context.builtAt.tzinfo is not None

    def test_context_version_is_1_0(self):
        assert self.context.contextVersion == "1.0"

    def test_regime_report_stored(self):
        assert self.context.regimeReport is not None

    def test_artifacts_stored(self):
        assert self.context.candidate is not None
        assert self.context.validation is not None
        assert self.context.risk is not None
        assert self.context.readiness is not None
        assert self.context.strategy is not None
        assert self.context.marketState is not None


class TestBuildContextNoInputs:
    """No upstream artifacts — context must use all safe defaults, never raise."""

    def setup_method(self):
        self.context = build_context(
            candidate_id="cand-000",
            mission_id="mission-000",
        )

    def test_returns_decision_context(self):
        assert isinstance(self.context, DecisionContext)

    def test_candidate_id_set(self):
        assert self.context.candidateId == "cand-000"

    def test_direction_defaults_to_wait(self):
        assert self.context.candidateDirection == "WAIT"

    def test_confidence_defaults_to_zero(self):
        assert self.context.candidateConfidence == 0.0

    def test_rr_defaults_to_zero(self):
        assert self.context.candidateRiskReward == 0.0

    def test_spread_defaults_to_zero(self):
        assert self.context.spread == 0.0

    def test_session_defaults_to_unknown(self):
        assert self.context.session == "Unknown"

    def test_trend_defaults_to_neutral(self):
        assert self.context.trend == "Neutral"

    def test_volatility_defaults_to_moderate(self):
        assert self.context.volatility == "Moderate"

    def test_news_impact_defaults_to_low(self):
        assert self.context.newsImpact == "Low"

    def test_market_closed_by_default(self):
        assert self.context.marketOpen is False

    def test_all_artifacts_none(self):
        assert self.context.candidate is None
        assert self.context.validation is None
        assert self.context.risk is None
        assert self.context.readiness is None
        assert self.context.strategy is None
        assert self.context.marketState is None
        assert self.context.regimeReport is None

    def test_strategy_fields_default(self):
        assert self.context.strategyId == ""
        assert self.context.strategyName == "Unknown"
        assert self.context.preferredSessions == []
        assert self.context.avoidConditions == []

    def test_context_version_set(self):
        assert self.context.contextVersion == "1.0"


class TestBuildContextMarketStateFallback:
    """Candidate snapshot absent — market state fields must be used as fallback."""

    def setup_method(self):
        # Candidate with no marketSnapshot attribute
        self.candidate = SignalCandidate.model_construct(
            id="cand-002",
            direction=CandidateDirection.SELL,
            confidence=75,
            riskReward=1.8,
            marketSnapshot=None  # No snapshot
        )
        # Ensure direction has .value for test compatibility if it's an enum, or just mock it:
        self.candidate.direction = MagicMock(value="SELL")

        self.market_state = _make_market_state(
            trend="Bearish",
            session="New York",
            spread=0.60,
            volatility="High",
            news_impact="High",
            market_open=True,
            data_age=12,
        )

        self.context = build_context(
            candidate_id="cand-002",
            mission_id="mission-002",
            candidate=self.candidate,
            market_state=self.market_state,
        )

    def test_spread_falls_back_to_market_state(self):
        assert self.context.spread == 0.60

    def test_session_falls_back_to_market_state(self):
        assert self.context.session == "New York"

    def test_trend_falls_back_to_market_state(self):
        assert self.context.trend == "Bearish"

    def test_volatility_falls_back_to_market_state(self):
        assert self.context.volatility == "High"

    def test_news_impact_falls_back_to_market_state(self):
        assert self.context.newsImpact == "High"

    def test_market_open_from_market_state(self):
        assert self.context.marketOpen is True

    def test_data_age_from_market_state(self):
        assert self.context.dataAgeSeconds == 12


class TestBuildContextRegimeOptional:
    """Regime report is Optional — must work before M3 wires it in."""

    def test_no_regime_no_crash(self):
        ctx = build_context(
            candidate_id="cand-003",
            mission_id="mission-003",
            candidate=_make_candidate(),
            regime_report=None,
        )
        assert ctx.regimeReport is None

    def test_regime_stored_when_provided(self):
        regime = MarketRegimeReport.model_construct()
        ctx = build_context(
            candidate_id="cand-003",
            mission_id="mission-003",
            candidate=_make_candidate(),
            regime_report=regime,
        )
        assert ctx.regimeReport is regime


class TestBuildContextDeterminism:
    """Same inputs must always produce the same cached values."""

    def test_identical_inputs_produce_identical_cached_values(self):
        candidate = _make_candidate(spread=0.42, session="London", trend="Bullish")
        ms = _make_market_state(spread=0.80, session="Asian")

        ctx1 = build_context("cand-x", "m-x", candidate=candidate, market_state=ms)
        ctx2 = build_context("cand-x", "m-x", candidate=candidate, market_state=ms)

        assert ctx1.spread == ctx2.spread
        assert ctx1.session == ctx2.session
        assert ctx1.trend == ctx2.trend
        assert ctx1.candidateDirection == ctx2.candidateDirection
        assert ctx1.candidateConfidence == ctx2.candidateConfidence


class TestBuildContextMarketClosed:
    """Market closed scenario — marketOpen must be False."""

    def test_market_closed(self):
        ms = _make_market_state(market_open=False)
        ctx = build_context(
            candidate_id="cand-004",
            mission_id="mission-004",
            market_state=ms,
        )
        assert ctx.marketOpen is False
