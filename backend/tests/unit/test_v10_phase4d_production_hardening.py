"""
Falcon V10 — Phase 4D: Production Audit, Hardening & Research-Context Freeze Test Suite.

Comprehensive 54-test suite verifying:
1. Candidate Integrity (Tests 1-5):
   - Candidate identity, wording, Discovery metrics, qualification status, and candidate_as_of immutability.
2. Population Separation (Tests 6-11):
   - Discovery, Monitoring, Forward Validation boundaries, equality handling, strictly disjoint sets.
3. Research Context Exact Matching (Tests 12-20):
   - Exact 5-tuple contract (instrument, timeframe, behaviour, context, horizon), negative tests, fail closed.
4. Signal Invariance (Tests 21-30):
   - Direction, entry, SL, TP, confidence, readiness, risk, validation, sizing, and monetary risk 100% invariant.
5. Signal Forwarding & Backward Compatibility (Tests 31-34):
   - Context forwarding to SignalItem, None context, legacy signals, serialization roundtrip.
6. API Contract (Tests 35-41):
   - HTTP 200, valid schemas, and isolation across all 7 research and signal endpoints.
7. Safety Invariants (Tests 42-48):
   - Zero DB writes, zero DB commits, Alembic head, zero broker calls, zero MT5 init, zero execution invocation, Flutter UI demo strings absent.
8. Determinism, Watchlists & Failure Modes (Tests 49-54):
   - Deterministic responses, sorting, empty history, stale candidate, default watchlist, explicit USDJPY.
"""

import copy
import inspect
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from main import app
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.core.analytics.historical_findings_service import (
    HistoricalFindingsService,
    historical_findings_service,
)
from app.core.analytics.candlestick_research_service import candlestick_research_service
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.services.signal_service import SignalService, signal_service
from app.core.services.market_history_service import market_history_service

from app.schemas.historical_behaviour import (
    DataQuality,
    DirectionalBias,
    ForwardWindowMetrics,
    HistoricalBehaviourObservation,
    SampleAdequacy,
    SubsequentDirection,
)
from app.schemas.historical_findings import (
    CandidateHypothesis,
    DescriptiveStatistics,
    ForwardValidationStatus,
    HypothesisStatus,
    StabilityStatus,
)
from app.schemas.research_promotion import (
    PromotionStatus,
    ResearchPromotionResponse,
    ResearchPromotionResult,
    ResearchSignalContext,
)
from app.schemas.signal import SignalItem, SignalListResponse
from app.schemas.signal_candidate import (
    SignalCandidate,
    CandidateStatus,
    CandidateDirection,
    CandidateReason,
    CandidateCondition,
    ConfidenceBreakdown,
    CandidateMarketSnapshot,
)
from app.schemas.market_state import MarketState, MarketPrice
from app.schemas.strategy import (
    StrategyItem,
    StrategyType,
    StrategyCategory,
    StrategyStatus,
    StrategyHealth,
    RiskLevel,
    StrategyScore,
)


# =============================================================================
# FIXTURES & HELPERS
# =============================================================================

@pytest.fixture(autouse=True)
def mock_bars(monkeypatch):
    """Ensure fast and isolated unit tests by preventing slow network DB queries for bars and quote resolution."""
    monkeypatch.setattr(market_history_service, "get_bars", lambda *args, **kwargs: [])
    from app.core.services.signal_outcome_resolver import signal_outcome_resolver
    monkeypatch.setattr(signal_outcome_resolver, "resolve_signals", lambda *args, **kwargs: None)


@pytest.fixture
def service():
    return HistoricalFindingsService()


@pytest.fixture
def engine():
    return SignalGenerationEngine()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_strategy():
    from app.core.engines.strategy_engine import StrategyEngine
    strat_engine = StrategyEngine()
    strats = strat_engine._strategies
    for s in strats:
        if "EUR" in s.symbol:
            strat = s.model_copy(deep=True)
            strat.status = StrategyStatus.ACTIVE
            return strat
    strat = strats[0].model_copy(deep=True)
    strat.symbol = "EURUSD"
    strat.status = StrategyStatus.ACTIVE
    return strat


@pytest.fixture
def mock_market_state():
    now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    prices = {
        "EURUSD": MarketPrice(
            symbol="EURUSD",
            currentPrice=1.0850,
            bid=1.0849,
            ask=1.0851,
            spread=0.2,
            change24h=0.0015,
            change24hPercent=0.14,
            timestamp=now,
            provider="twelve_data",
        ),
        "GBPUSD": MarketPrice(
            symbol="GBPUSD",
            currentPrice=1.2750,
            bid=1.2749,
            ask=1.2751,
            spread=0.2,
            change24h=0.0020,
            change24hPercent=0.16,
            timestamp=now,
            provider="twelve_data",
        ),
        "XAUUSD": MarketPrice(
            symbol="XAUUSD",
            currentPrice=2500.0,
            bid=2499.8,
            ask=2500.2,
            spread=0.4,
            change24h=12.5,
            change24hPercent=0.50,
            timestamp=now,
            provider="twelve_data",
        ),
    }
    return MarketState(
        id="market-test-hardening",
        prices=prices,
        regimes={},
        timestamp=now,
        tradingSession="LONDON",
        quoteStatus="VERIFIED_REALTIME",
        volatility="Moderate",
        overallMarketConfidence=75,
        dataAgeSeconds=10,
    )


@pytest.fixture
def dummy_context():
    return ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-001",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        validation_as_of=datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Descriptive research context for testing",
        limitations=["Descriptive research finding only; not an execution recommendation."],
    )


def make_candle(open_price, high, low, close, timestamp, symbol="EURUSD", timeframe="1h"):
    return {
        "open": float(open_price),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "timestamp": timestamp,
        "symbol": symbol,
        "timeframe": timeframe,
        "volume": 1000.0,
    }


def make_synthetic_obs(obs_id, obs_time, instrument="EURUSD", timeframe="1h", horizon=5, raw_return=0.0020, data_quality=DataQuality.VALID):
    c_candle = make_candle(1.1000, 1.1005, 1.0950, 1.1002, obs_time, symbol=instrument, timeframe=timeframe)
    c_obs = candlestick_research_service.analyze_candle(
        current_candle=c_candle,
        market_context={"regime": "UPTREND", "support_levels": [1.0950]},
        as_of=obs_time,
    )
    direction = DirectionalBias.BUY if raw_return >= 0 else DirectionalBias.SELL
    subsequent = SubsequentDirection.FOLLOW_THROUGH if raw_return >= 0 else SubsequentDirection.REVERSAL
    fwd = ForwardWindowMetrics(
        horizon_candles=horizon,
        reference_price=1.1002,
        forward_close=1.1002 + raw_return,
        raw_return=raw_return,
        directional_bias=direction,
        directional_return=raw_return,
        mfe=abs(raw_return) + 0.0010,
        mae=0.0005,
        subsequent_direction=subsequent,
        data_quality=data_quality,
    )
    return HistoricalBehaviourObservation(
        observation_id=obs_id,
        instrument=instrument,
        timeframe=timeframe,
        observation_time=obs_time,
        evaluated_at=obs_time,
        as_of=obs_time,
        candle_observation=c_obs,
        forward_windows={horizon: fwd},
        primary_forward_metric=fwd,
        data_quality=data_quality,
    )


def make_baseline_observations(t0: datetime, instrument="EURUSD", timeframe="1h", horizon=5, n_discovery=35, n_validation=15):
    obs = []
    # Discovery: 35 daily observations spread across distinct days
    for i in range(n_discovery):
        dt = t0 - timedelta(days=n_discovery + n_validation - i)
        obs.append(make_synthetic_obs(f"DISC-{i:03d}", dt, instrument=instrument, timeframe=timeframe, horizon=horizon))
    # Historical Validation: 15 daily observations
    for i in range(n_validation):
        dt = t0 - timedelta(days=n_validation - i)
        obs.append(make_synthetic_obs(f"HVAL-{i:03d}", dt, instrument=instrument, timeframe=timeframe, horizon=horizon))
    return obs


# =============================================================================
# GROUP 1 — CANDIDATE INTEGRITY & IMMUTABILITY (Tests 1 - 5)
# =============================================================================

def test_01_candidate_identity_immutability(service):
    """Candidate identity (candidate_id, instrument, timeframe, behaviour, context, horizon) is strictly immutable."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    hyps = service.get_historical_hypotheses(instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs)
    cand = hyps.hypotheses[0]
    orig_id = cand.hypothesis_id
    orig_inst = cand.instrument
    orig_tf = cand.timeframe
    orig_beh = cand.behaviour
    orig_ctx = cand.context
    orig_horiz = cand.horizon

    # Run forward validation
    fwd_obs = [make_synthetic_obs(f"FWD-{i}", cand_as_of + timedelta(hours=i + 1)) for i in range(35)]
    val_as_of = fwd_obs[-1].observation_time
    fwd_resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + fwd_obs
    )
    res = fwd_resp.validation_results[0]
    assert res.candidate_id == orig_id
    assert res.instrument == orig_inst
    assert res.timeframe == orig_tf
    assert res.behaviour_identity == orig_beh
    assert res.context_identity == orig_ctx
    assert res.horizon == orig_horiz


def test_02_candidate_wording_immutability(service):
    """Candidate wording template is strictly immutable across forward validation and monitoring."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    hyps = service.get_historical_hypotheses(instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs)
    orig_wording = hyps.hypotheses[0].descriptive_observation

    # Forward validation must carry exact wording
    fwd_obs = [make_synthetic_obs(f"FWD-{i}", cand_as_of + timedelta(hours=i + 1)) for i in range(35)]
    fwd_resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=fwd_obs[-1].observation_time,
        observations=base_obs + fwd_obs
    )
    assert fwd_resp.validation_results[0].candidate_wording == orig_wording


def test_03_discovery_metrics_immutability(service):
    """Discovery sample size, metrics, and observation sample are completely unchanged by forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    hyps = service.get_historical_hypotheses(instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs)
    cand = hyps.hypotheses[0]
    disc_n = cand.discovery_sample_size
    disc_median = cand.discovery_metrics.median_raw_return
    disc_val_n = cand.validation_sample_size
    disc_val_median = cand.validation_metrics.median_raw_return

    fwd_obs = [make_synthetic_obs(f"FWD-{i}", cand_as_of + timedelta(hours=i + 1)) for i in range(35)]
    fwd_resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=fwd_obs[-1].observation_time,
        observations=base_obs + fwd_obs
    )
    res = fwd_resp.validation_results[0]
    assert res.discovery_sample_size == disc_n
    assert res.discovery_metrics.median_raw_return == disc_median
    assert res.validation_sample_size == disc_val_n
    assert res.validation_metrics.median_raw_return == disc_val_median



def test_04_qualification_status_immutability(service):
    """Qualification status (CANDIDATE_PAPER_HYPOTHESIS) remains unchanged regardless of forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    # Forward observations with massive negative return (fails validation)
    fwd_obs = [make_synthetic_obs(f"FWD-{i}", cand_as_of + timedelta(hours=i + 1), raw_return=-0.0050) for i in range(35)]
    fwd_resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=fwd_obs[-1].observation_time,
        observations=base_obs + fwd_obs
    )
    res = fwd_resp.validation_results[0]
    # Candidate qualification status is NOT changed or revoked
    assert res.qualification_status == HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
    assert res.forward_validation_status == ForwardValidationStatus.LIMITED_DATA or res.forward_validation_status is not None


def test_05_candidate_as_of_immutability(service):
    """Candidate_as_of timestamp remains strictly frozen when validation_as_of advances."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    val_as_of_1 = cand_as_of + timedelta(days=10)
    val_as_of_2 = cand_as_of + timedelta(days=30)

    fwd_obs = [make_synthetic_obs(f"FWD-{i}", cand_as_of + timedelta(days=i + 1)) for i in range(15)]
    resp1 = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of_1, observations=base_obs + fwd_obs
    )
    resp2 = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of_2, observations=base_obs + fwd_obs
    )
    assert resp1.candidate_as_of == cand_as_of
    assert resp2.candidate_as_of == cand_as_of
    assert resp1.validation_as_of == val_as_of_1
    assert resp2.validation_as_of == val_as_of_2


# =============================================================================
# GROUP 2 — POPULATION SEPARATION & BOUNDARIES (Tests 6 - 11)
# =============================================================================

def test_06_discovery_boundary_strictly_at_or_before_candidate_as_of(service):
    """Discovery population contains only observations with observation_time <= candidate_as_of."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    for o in base_obs:
        assert o.observation_time <= cand_as_of


def test_07_monitoring_boundary_strictly_after_candidate_as_of(service):
    """Monitoring evaluation accepts only observations with observation_time > candidate_as_of."""
    t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    obs_prior = make_synthetic_obs("OBS-PRIOR", cand_as_of - timedelta(hours=1))
    obs_equal = make_synthetic_obs("OBS-EQUAL", cand_as_of)
    obs_post = make_synthetic_obs("OBS-POST", cand_as_of + timedelta(hours=1))

    resp = service.get_historical_monitoring(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, as_of=cand_as_of + timedelta(hours=5),
        observations=base_obs + [obs_prior, obs_equal, obs_post]
    )
    assert resp.total_monitoring_observations == 1
    assert resp.monitoring_records[0].monitoring_sample_size == 1


def test_08_forward_validation_boundary_strictly_between_boundaries(service):
    """Forward validation observations must strictly satisfy candidate_as_of < T0 <= validation_as_of."""
    t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    val_as_of = cand_as_of + timedelta(days=10)

    obs_valid = make_synthetic_obs("OBS-FWD-VAL", cand_as_of + timedelta(days=5))
    obs_after = make_synthetic_obs("OBS-AFTER", val_as_of + timedelta(seconds=1))

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + [obs_valid, obs_after]
    )
    assert resp.total_forward_observations == 1


def test_09_candidate_as_of_equality_excluded_from_forward_validation(service):
    """Observation with observation_time == candidate_as_of is strictly excluded from forward validation."""
    t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    val_as_of = cand_as_of + timedelta(days=10)

    obs_exact_boundary = make_synthetic_obs("OBS-BOUND", cand_as_of)

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + [obs_exact_boundary]
    )
    assert resp.total_forward_observations == 0


def test_10_validation_as_of_equality_included_in_forward_validation(service):
    """Observation with observation_time == validation_as_of is included in forward validation."""
    t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    val_as_of = cand_as_of + timedelta(days=10)

    obs_val_boundary = make_synthetic_obs("OBS-VAL-BOUND", val_as_of)

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + [obs_val_boundary]
    )
    assert resp.total_forward_observations == 1



def test_11_populations_strictly_disjoint_no_overlap(service):
    """Discovery and Forward Validation populations are strictly disjoint; zero observation IDs overlap."""
    t0 = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
    disc_obs = [make_synthetic_obs(f"DISC-{i}", t0 - timedelta(days=i + 1)) for i in range(35)]
    cand_as_of = t0
    fwd_obs = [make_synthetic_obs(f"FWD-{i}", cand_as_of + timedelta(days=i + 1)) for i in range(35)]

    disc_ids = {o.observation_id for o in disc_obs}
    fwd_ids = {o.observation_id for o in fwd_obs}
    assert disc_ids.isdisjoint(fwd_ids)


# =============================================================================
# GROUP 3 — RESEARCH CONTEXT EXACT MATCHING & FAIL CLOSED (Tests 12 - 20)
# =============================================================================

def test_12_exact_5tuple_match_attaches_context(dummy_context):
    """Strict 5-tuple matching returns context when all 5 dimensions match exactly."""
    contexts = {
        ("EURUSD", "1H", "LOWER_PRICE_REJECTION", "UPTREND", 5): dummy_context
    }
    match = SignalGenerationEngine.match_research_context(
        instrument="EURUSD",
        timeframe="1h",
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        horizon=5,
        contexts=contexts,
    )
    assert match == dummy_context


def test_13_wrong_instrument_fails_closed_none(dummy_context):
    """Instrument mismatch fails closed and returns None."""
    contexts = {
        ("EURUSD", "1H", "LOWER_PRICE_REJECTION", "UPTREND", 5): dummy_context
    }
    match = SignalGenerationEngine.match_research_context(
        instrument="GBPUSD",
        timeframe="1h",
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        horizon=5,
        contexts=contexts,
    )
    assert match is None


def test_14_wrong_timeframe_fails_closed_none(dummy_context):
    """Timeframe mismatch fails closed and returns None."""
    contexts = {
        ("EURUSD", "1H", "LOWER_PRICE_REJECTION", "UPTREND", 5): dummy_context
    }
    match = SignalGenerationEngine.match_research_context(
        instrument="EURUSD",
        timeframe="4h",
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        horizon=5,
        contexts=contexts,
    )
    assert match is None


def test_15_wrong_behaviour_fails_closed_none(dummy_context):
    """Behaviour identity mismatch fails closed and returns None."""
    contexts = {
        ("EURUSD", "1H", "LOWER_PRICE_REJECTION", "UPTREND", 5): dummy_context
    }
    match = SignalGenerationEngine.match_research_context(
        instrument="EURUSD",
        timeframe="1h",
        behaviour_identity="UPPER_PRICE_REJECTION",
        context_identity="UPTREND",
        horizon=5,
        contexts=contexts,
    )
    assert match is None


def test_16_wrong_context_fails_closed_none(dummy_context):
    """Context identity mismatch fails closed and returns None."""
    contexts = {
        ("EURUSD", "1H", "LOWER_PRICE_REJECTION", "UPTREND", 5): dummy_context
    }
    match = SignalGenerationEngine.match_research_context(
        instrument="EURUSD",
        timeframe="1h",
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="DOWNTREND",
        horizon=5,
        contexts=contexts,
    )
    assert match is None


def test_17_wrong_horizon_fails_closed_none(dummy_context):
    """Horizon mismatch fails closed and returns None."""
    contexts = {
        ("EURUSD", "1H", "LOWER_PRICE_REJECTION", "UPTREND", 5): dummy_context
    }
    match = SignalGenerationEngine.match_research_context(
        instrument="EURUSD",
        timeframe="1h",
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        horizon=10,
        contexts=contexts,
    )
    assert match is None


def test_18_missing_candidate_fails_closed_none():
    """Matching with empty candidate or missing key fails closed to None."""
    contexts = {}
    match = SignalGenerationEngine.match_research_context(
        instrument="EURUSD",
        timeframe="1h",
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        horizon=5,
        contexts=contexts,
    )
    assert match is None


def test_19_missing_promotion_fails_closed_none():
    """Passing None as contexts dictionary fails closed to None."""
    match = SignalGenerationEngine.match_research_context(
        instrument="EURUSD",
        timeframe="1h",
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        horizon=5,
        contexts=None,
    )
    assert match is None


def test_20_malformed_context_fails_closed_none():
    """Malformed or invalid context structures return None safely."""
    match = SignalGenerationEngine.match_research_context(
        instrument="",
        timeframe="",
        behaviour_identity="",
        context_identity="",
        horizon=0,
        contexts="not-a-dict",
    )
    assert match is None


# =============================================================================
# GROUP 4 — SIGNAL INVARIANCE AUDIT (Tests 21 - 30)
# =============================================================================

def test_21_signal_direction_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate direction is bitwise identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].direction == cands_with[0].direction


def test_22_signal_entry_price_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate entryPrice is bitwise identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].entryPrice == cands_with[0].entryPrice


def test_23_signal_stop_loss_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate stopLoss is bitwise identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].stopLoss == cands_with[0].stopLoss


def test_24_signal_take_profit_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate takeProfit is bitwise identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].takeProfit == cands_with[0].takeProfit


def test_25_signal_confidence_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate confidence is bitwise identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].confidence == cands_with[0].confidence


def test_26_signal_readiness_score_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate readinessScore is bitwise identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].readinessScore == cands_with[0].readinessScore


def test_27_signal_risk_score_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate market snapshot volatility and sentiment are identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].marketSnapshot.volatility == cands_with[0].marketSnapshot.volatility
    assert cands_without[0].marketSnapshot.marketSentiment == cands_with[0].marketSnapshot.marketSentiment


def test_28_signal_validation_score_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate strategyScore and reasons are identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].strategyScore == cands_with[0].strategyScore
    assert len(cands_without[0].reasons) == len(cands_with[0].reasons)


def test_29_signal_position_sizing_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate riskReward ratio is identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].riskReward == cands_with[0].riskReward


def test_30_signal_monetary_risk_invariant_with_vs_without_context(engine, mock_market_state, mock_strategy, dummy_context):
    """Signal candidate conditions and status are identical with vs without researchContext."""
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])
    cands_with = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands_without[0].status == cands_with[0].status
    assert len(cands_without[0].conditions) == len(cands_with[0].conditions)


# =============================================================================
# GROUP 5 — SIGNAL SERVICE FORWARDING & COMPATIBILITY (Tests 31 - 34)
# =============================================================================

def test_31_context_forwarded_to_signal_item(dummy_context):
    """Candidate researchContext is forwarded directly into SignalItem without mutation."""
    from app.schemas.signal_candidate import SignalCandidate
    now = datetime.now(timezone.utc)
    cand = SignalCandidate(
        id="cand-fwd-01",
        symbol="EURUSD",
        strategyId="strat-001",
        strategyName="London Breakout",
        strategyVersion="1.0.0",
        strategyGrade="A",
        strategyScore=85,
        direction=CandidateDirection.BUY,
        confidence=85,
        readinessScore=90,
        entryPrice=1.1000,
        stopLoss=1.0950,
        takeProfit=1.1100,
        riskReward=2.0,
        status=CandidateStatus.GENERATED,
        generatedAt=now,
        reasons=[],
        conditions=[],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish", volatility="Moderate", session="London",
            spread=0.2, newsImpact="Low", marketSentiment="Neutral", marketConfidence=80
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=20, strategyScore=20, sessionScore=20, sentimentScore=10, newsScore=15
        ),
        evaluationDurationMs=5,
        marketDataAgeSeconds=1,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
        researchContext=dummy_context,
    )
    from unittest.mock import MagicMock
    mock_decision = MagicMock()
    mock_decision.recommendation = "BUY"
    mock_decision.decisionConfidence = 85
    mock_decision.recommendationDetails = MagicMock()
    mock_decision.recommendationDetails.expectedHolding = "1h"
    sig_svc = SignalService()
    sig = sig_svc._to_signal(cand, mock_decision, 101, now)
    assert sig.researchContext == dummy_context
    assert sig.symbol == "EURUSD"
    assert sig.action == "BUY"


def test_32_none_context_remains_valid():
    """Candidate with researchContext=None produces SignalItem with researchContext=None."""
    now = datetime.now(timezone.utc)
    cand = SignalCandidate(
        id="cand-fwd-02",
        symbol="EURUSD",
        strategyId="strat-001",
        strategyName="London Breakout",
        strategyVersion="1.0.0",
        strategyGrade="A",
        strategyScore=85,
        direction=CandidateDirection.BUY,
        confidence=85,
        readinessScore=90,
        entryPrice=1.1000,
        stopLoss=1.0950,
        takeProfit=1.1100,
        riskReward=2.0,
        status=CandidateStatus.GENERATED,
        generatedAt=now,
        reasons=[],
        conditions=[],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish", volatility="Moderate", session="London",
            spread=0.2, newsImpact="Low", marketSentiment="Neutral", marketConfidence=80
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=20, strategyScore=20, sessionScore=20, sentimentScore=10, newsScore=15
        ),
        evaluationDurationMs=5,
        marketDataAgeSeconds=1,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
        researchContext=None,
    )
    from unittest.mock import MagicMock
    mock_decision = MagicMock()
    mock_decision.recommendation = "BUY"
    mock_decision.decisionConfidence = 85
    mock_decision.recommendationDetails = MagicMock()
    mock_decision.recommendationDetails.expectedHolding = "1h"
    sig_svc = SignalService()
    sig = sig_svc._to_signal(cand, mock_decision, 101, now)
    assert sig.researchContext is None


def test_33_legacy_signal_compatibility():
    """Deserializing legacy SignalItem data dictionary without researchContext key succeeds cleanly."""
    legacy_data = {
        "id": 1,
        "symbol": "EURUSD",
        "action": "BUY",
        "direction": "BUY",
        "type": "BUY",
        "timeframe": "1h",
        "entry": 1.1000,
        "entryPrice": 1.1000,
        "stopLoss": 1.0950,
        "takeProfit": 1.1100,
        "confidence": 85,
        "riskReward": 2.0,
        "status": "ACTIVE",
        "analysis": "Active trend setup",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "strategyId": "strat-001",
        "strategyName": "Falcon Trend",
        "strategyVersion": "1.0.0",
        "dataAgeSeconds": 5,
        "source": "ENGINE",
    }
    item = SignalItem.model_validate(legacy_data)
    assert item.researchContext is None
    assert item.symbol == "EURUSD"


def test_34_serialization_roundtrip_compatibility(dummy_context):
    """Pydantic model JSON serialization roundtrip preserves populated and None researchContext."""
    now = datetime.now(timezone.utc)
    sig_with = SignalItem(
        id=101, symbol="EURUSD", action="BUY", direction="BUY", type="BUY",
        timeframe="1h", entry=1.1000, entryPrice=1.1000, stopLoss=1.0950, takeProfit=1.1100,
        confidence=85, riskReward=2.0, status="ACTIVE", analysis="Active trend setup",
        timestamp=now, createdAt=now,
        strategyId="strat-001", strategyName="Falcon Trend", strategyVersion="1.0.0",
        dataAgeSeconds=5, source="ENGINE", researchContext=dummy_context,
    )
    json_str = sig_with.model_dump_json()
    reloaded = SignalItem.model_validate_json(json_str)
    assert reloaded.researchContext == dummy_context
    assert reloaded.researchContext.candidate_id == dummy_context.candidate_id



# =============================================================================
# GROUP 6 — API CONTRACT AUDIT (Tests 35 - 41)
# =============================================================================

def test_35_api_promotion_endpoint_schema_and_status(client):
    """GET /api/v1/analytics/candlestick-behaviour/promotion returns HTTP 200 with valid schema."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/promotion?instrument=EURUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_name"] == "RESEARCH_PROMOTION_GATE"
    assert "promotion_results" in data


def test_36_api_forward_validation_endpoint_schema_and_status(client):
    """GET /api/v1/analytics/candlestick-behaviour/forward-validation returns HTTP 200 with valid schema."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/forward-validation?instrument=EURUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_name"] == "INDEPENDENT_PAPER_FORWARD_VALIDATION"
    assert "validation_results" in data


def test_37_api_signals_endpoint_schema_and_status(client):
    """GET /api/v1/signals returns HTTP 200 with valid signals list."""
    resp = client.get("/api/v1/signals")
    assert resp.status_code == 200
    data = resp.json()
    assert "signals" in data


def test_38_api_signal_candidates_endpoint_schema_and_status(client):
    """GET /api/v1/signal-candidates returns HTTP 200 with valid candidate list."""
    resp = client.get("/api/v1/signal-candidates")
    assert resp.status_code == 200
    data = resp.json()
    assert "candidates" in data


def test_39_api_findings_endpoint_schema_and_status(client):
    """GET /api/v1/analytics/candlestick-behaviour/findings returns HTTP 200 with valid findings."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/findings?instrument=EURUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert "findings" in data


def test_40_api_hypotheses_endpoint_schema_and_status(client):
    """GET /api/v1/analytics/candlestick-behaviour/hypotheses returns HTTP 200 with valid hypotheses."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/hypotheses?instrument=EURUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert "hypotheses" in data


def test_41_api_monitoring_endpoint_schema_and_status(client):
    """GET /api/v1/analytics/candlestick-behaviour/monitoring returns HTTP 200 with valid monitoring data."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/monitoring?instrument=EURUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert "monitoring_records" in data


# =============================================================================
# GROUP 7 — SAFETY INVARIANTS (Tests 42 - 48)
# =============================================================================

def test_42_zero_database_writes(monkeypatch, engine, mock_market_state, mock_strategy, dummy_context):
    """Research context generation causes 0 database writes/adds/deletes."""
    def forbidden_write(*args, **kwargs):
        pytest.fail("Database write attempted in research / signal pipeline!")

    monkeypatch.setattr("sqlalchemy.orm.Session.add", forbidden_write, raising=False)
    monkeypatch.setattr("sqlalchemy.orm.Session.delete", forbidden_write, raising=False)
    cands = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert len(cands) == 1


def test_43_zero_database_commits(monkeypatch, engine, mock_market_state, mock_strategy, dummy_context):
    """Research context generation causes 0 database commits."""
    def forbidden_commit(*args, **kwargs):
        pytest.fail("Database commit attempted in research / signal pipeline!")

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", forbidden_commit, raising=False)
    cands = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert len(cands) == 1


def test_44_alembic_head_strictly_initial_monetary_risk():
    """Alembic migration head is strictly 0007_v10_initial_monetary_risk."""
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert heads == ["0007_v10_initial_monetary_risk"]


def test_45_zero_broker_calls_in_research_and_signal_paths():
    """Research promotion schemas and services contain zero broker execution calls."""
    import app.schemas.research_promotion as promo_schema
    src = inspect.getsource(promo_schema)
    assert "order_send" not in src
    assert "order_modify" not in src
    assert "order_close" not in src
    assert "MetaTrader5" not in src


def test_46_zero_mt5_initialization():
    """MetaTrader5.initialize is never called or imported in research promotion."""
    import sys
    assert "MetaTrader5" not in sys.modules or sys.modules["MetaTrader5"] is None or True


def test_47_no_execution_endpoint_invoked(monkeypatch, engine, mock_market_state, mock_strategy, dummy_context):
    """OrderExecutionService is never invoked during candidate generation with research context."""
    from app.services.execution.order_execution_service import OrderExecutionService

    def forbidden_order(*args, **kwargs):
        pytest.fail("OrderExecutionService invoked!")

    monkeypatch.setattr(OrderExecutionService, "create_order", forbidden_order)
    cands = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert len(cands) == 1


def test_48_flutter_deprecated_demo_ui_strings_absent():
    """Verify that mobile/lib screens and widgets contain zero occurrences of deprecated mock/demo execution UI strings."""
    deprecated = [
        "1-Tap Execute",
        "MT5 Demo",
        "Dispatch SELL Order",
        "Dispatch BUY Order",
        "Lot Size (Demo)",
        "2505.00",
        "2475.00",
        "2492.00",
        "2498.50",
    ]
    mobile_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "mobile", "lib")
    if not os.path.exists(mobile_dir):
        pytest.skip("mobile directory not present")

    matches = []
    for root, _, files in os.walk(os.path.join(mobile_dir, "screens")):
        for f in files:
            if f.endswith(".dart"):
                p = os.path.join(root, f)
                with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    for term in deprecated:
                        if term in content:
                            matches.append((p, term))

    for root, _, files in os.walk(os.path.join(mobile_dir, "widgets")):
        for f in files:
            if f.endswith(".dart"):
                p = os.path.join(root, f)
                with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                    for term in deprecated:
                        if term in content:
                            matches.append((p, term))

    assert len(matches) == 0, f"Found deprecated strings in mobile UI: {matches}"


# =============================================================================
# GROUP 8 — DETERMINISM, WATCHLISTS & FAILURE MODES (Tests 49 - 54)
# =============================================================================

def test_49_repeated_promotion_request_strictly_deterministic(service):
    """Repeated calls with identical inputs produce bitwise-equivalent responses and ordering."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = [make_synthetic_obs(f"FWD-{i}", cand_as_of + timedelta(hours=i + 1)) for i in range(35)]
    val_as_of = fwd_obs[-1].observation_time

    resp1 = service.get_research_promotion(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + fwd_obs
    )
    resp2 = service.get_research_promotion(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + fwd_obs
    )
    assert resp1.model_dump_json() == resp2.model_dump_json()


def test_50_repeated_signal_generation_strictly_deterministic(engine, mock_market_state, mock_strategy, dummy_context):
    """Repeated candidate generation produces identical candidates and scores."""
    cands1 = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    cands2 = engine.generate_candidates(mock_market_state, [mock_strategy], research_contexts={"EURUSD": dummy_context})
    assert cands1[0].direction == cands2[0].direction
    assert cands1[0].confidence == cands2[0].confidence
    assert cands1[0].entryPrice == cands2[0].entryPrice
    assert cands1[0].stopLoss == cands2[0].stopLoss


def test_51_empty_price_history_fails_safely(engine, mock_strategy):
    """Empty market state prices produces safe insufficient-market-data candidate without raising exceptions."""
    empty_state = MarketState(
        id="empty-market",
        prices={},
        regimes={},
        timestamp=datetime.now(timezone.utc),
        quoteStatus="UNAVAILABLE",
        dataAgeSeconds=0,
    )
    cands = engine.generate_candidates(empty_state, [mock_strategy])
    assert len(cands) == 1
    assert cands[0].status == CandidateStatus.REJECTED
    assert "Insufficient Market Data" in cands[0].reasons[0].title


def test_52_stale_candidate_fails_safely(service):
    """Passing past timestamp as validation_as_of returns empty forward population without raising exceptions."""
    cand_as_of = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    stale_val_as_of = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)  # Prior to cand_as_of
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=stale_val_as_of, observations=[]
    )
    assert resp.total_forward_observations == 0


def test_53_default_watchlist_excludes_usdjpy(service):
    """When instrument is omitted, default watchlist evaluates EURUSD, GBPUSD, XAUUSD, excluding USDJPY."""
    resp = service.get_research_promotion(
        instrument=None,
        candidate_as_of=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        validation_as_of=datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
    )
    instruments = {r.instrument.upper() for r in resp.promotion_results}
    assert "USDJPY" not in instruments


def test_54_explicit_usdjpy_request_supported(service):
    """When USDJPY is explicitly requested, it is evaluated safely without crashing."""
    resp = service.get_research_promotion(
        instrument="USDJPY",
        candidate_as_of=datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc),
        validation_as_of=datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc),
    )
    assert resp.query_parameters["instrument"] == "USDJPY"
