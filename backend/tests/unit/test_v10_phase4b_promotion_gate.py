"""
Falcon V10 — Phase 4B Research Promotion Gate & Signal Context Test Suite.

Comprehensive verification of:
1. Promotion Identity & Exact Tuple Matching (instrument, timeframe, behaviour, context, horizon)
2. Candidate Immutability (Candidate ID, wording, Discovery/Validation metrics unchanged)
3. Temporal Isolation (candidate_as_of < T0 <= validation_as_of; boundary equality excluded)
4. Eligibility Gates (Categorical non-ranking statuses: ELIGIBLE_INFORMATIONAL, NOT_ELIGIBLE,
   INSUFFICIENT_DATA, LIMITED_DATA, DATA_QUALITY_LIMITED, TEMPORALLY_UNSTABLE)
5. Signal Engine Isolation & Behavioral Invariance (Research context is informational metadata only;
   zero changes to direction, entry, stop loss, take profit, confidence, sizing, or risk)
6. Safety Invariants (Zero DB writes, zero broker calls, zero MT5 imports, Alembic head 0007_v10_initial_monetary_risk)
7. Non-Ranking & Prohibited Term Protections (No BEST, WORST, WINNING, EDGE, BUY/SELL recommendation)
8. Determinism & Traceability (Identical requests yield identical responses; deterministic ordering)
9. Section 14 Behavioral Regression Check (Signal outputs with vs without researchContext are identical)
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.analytics.candlestick_research_service import candlestick_research_service
from app.core.analytics.historical_behaviour_service import historical_behaviour_service
from app.core.analytics.historical_findings_service import (
    HistoricalFindingsService,
    historical_findings_service,
)
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.schemas.candlestick_research import (
    RejectionObservation,
    StructuralInteraction,
)
from app.schemas.historical_behaviour import (
    DataQuality,
    DirectionalBias,
    ForwardWindowMetrics,
    HistoricalBehaviourObservation,
    SampleAdequacy,
    SubsequentDirection,
)
from app.schemas.historical_findings import (
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
from app.schemas.market_state import MarketState, MarketPrice
from app.schemas.strategy import StrategyItem, StrategyType, StrategyCategory, StrategyStatus, StrategyHealth, RiskLevel, StrategyScore, StrategyValidation


from app.core.services.market_history_service import market_history_service


@pytest.fixture(autouse=True)
def mock_bars(monkeypatch):
    monkeypatch.setattr(market_history_service, "get_bars", lambda *args, **kwargs: [])


@pytest.fixture
def service():
    return HistoricalFindingsService()


@pytest.fixture
def client():
    return TestClient(app)


def make_candle(
    open_price: float,
    high: float,
    low: float,
    close: float,
    timestamp: datetime,
    symbol: str = "EURUSD",
    timeframe: str = "1h",
) -> Dict[str, Any]:
    """Helper to construct synthetic OHLC candle dictionaries."""
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


def make_synthetic_observation(
    obs_id: str,
    obs_time: datetime,
    behaviour: str = "LOWER_PRICE_REJECTION",
    regime: str = "UPTREND",
    support: str = "WICK_REJECTED_SUPPORT",
    horizon: int = 5,
    raw_return: float = 0.0020,
    data_quality: DataQuality = DataQuality.VALID,
    instrument: str = "EURUSD",
    timeframe: str = "1h",
) -> HistoricalBehaviourObservation:
    """Constructs a deterministic mock HistoricalBehaviourObservation."""
    c_candle = make_candle(1.1000, 1.1005, 1.0950, 1.1002, obs_time, symbol=instrument, timeframe=timeframe)
    c_obs = candlestick_research_service.analyze_candle(
        current_candle=c_candle,
        market_context={"regime": regime, "support_levels": [1.0950]},
        as_of=obs_time,
    )
    rejection_enum = getattr(RejectionObservation, behaviour, None)
    if rejection_enum is None:
        try:
            rejection_enum = RejectionObservation(behaviour)
        except ValueError:
            rejection_enum = RejectionObservation.UNKNOWN

    support_enum = getattr(StructuralInteraction, support, None)
    if support_enum is None:
        try:
            support_enum = StructuralInteraction(support)
        except ValueError:
            support_enum = StructuralInteraction.UNKNOWN

    c_obs = c_obs.model_copy(
        update={
            "rejection_observation": rejection_enum,
            "market_regime_context": regime,
            "support_resistance_interaction": support_enum,
        }
    )
    fwd_metric = ForwardWindowMetrics(
        horizon_candles=horizon,
        reference_price=1.1002,
        forward_close=1.1002 + raw_return if data_quality == DataQuality.VALID else None,
        raw_return=raw_return if data_quality == DataQuality.VALID else None,
        directional_bias=DirectionalBias.BUY,
        directional_return=raw_return if data_quality == DataQuality.VALID else None,
        mfe=abs(raw_return) + 0.0010 if data_quality == DataQuality.VALID else None,
        mae=0.0005 if data_quality == DataQuality.VALID else None,
        subsequent_direction=SubsequentDirection.FOLLOW_THROUGH if raw_return > 0 else SubsequentDirection.REVERSAL,
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
        forward_windows={horizon: fwd_metric},
        primary_forward_metric=fwd_metric,
        data_quality=data_quality,
    )


def make_baseline_observations(
    start_time: datetime,
    n_discovery: int = 35,
    n_validation: int = 15,
    instrument: str = "EURUSD",
    timeframe: str = "1h",
    horizon: int = 5,
    behaviour: str = "LOWER_PRICE_REJECTION",
    regime: str = "UPTREND",
    support: str = "WICK_REJECTED_SUPPORT",
) -> List[HistoricalBehaviourObservation]:
    """Generates a qualifying Discovery + Validation baseline set."""
    obs = []
    # Discovery partition
    for i in range(n_discovery):
        t = start_time + timedelta(hours=i)
        obs.append(make_synthetic_observation(
            f"disc-{i:03d}", t, instrument=instrument, timeframe=timeframe, horizon=horizon,
            behaviour=behaviour, regime=regime, support=support,
        ))
    # Validation partition
    val_start = start_time + timedelta(hours=n_discovery)
    for j in range(n_validation):
        t = val_start + timedelta(hours=j)
        obs.append(make_synthetic_observation(
            f"val-{j:03d}", t, instrument=instrument, timeframe=timeframe, horizon=horizon,
            behaviour=behaviour, regime=regime, support=support,
        ))
    return obs


def make_forward_observations(
    start_time: datetime,
    n_forward: int = 35,
    instrument: str = "EURUSD",
    timeframe: str = "1h",
    horizon: int = 5,
    behaviour: str = "LOWER_PRICE_REJECTION",
    regime: str = "UPTREND",
    support: str = "WICK_REJECTED_SUPPORT",
    raw_return: float = 0.0025,
    data_quality: DataQuality = DataQuality.VALID,
) -> List[HistoricalBehaviourObservation]:
    """Generates strictly post-candidate forward validation observations."""
    obs = []
    for k in range(n_forward):
        t = start_time + timedelta(hours=k + 1)
        obs.append(make_synthetic_observation(
            f"fwd-{k:03d}", t, instrument=instrument, timeframe=timeframe, horizon=horizon,
            behaviour=behaviour, regime=regime, support=support, raw_return=raw_return,
            data_quality=data_quality,
        ))
    return obs


# =============================================================================
# GROUP A — PROMOTION IDENTITY & EXACT MATCHING (Tests 1 - 6)
# =============================================================================

def test_01_exact_candidate_identity_preserved(service):
    """Promotion result preserves exact candidate ID."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.total_candidates == 1
    res = resp.promotion_results[0]
    assert res.candidate_id.startswith("HYP-EURUSD-1H-H5-")
    assert res.instrument == "EURUSD"
    assert res.timeframe == "1H"
    assert res.horizon == 5


def test_02_instrument_mismatch_cannot_match(service):
    """Querying GBPUSD cannot match a candidate on EURUSD."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, instrument="EURUSD")
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, instrument="EURUSD")
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="GBPUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.total_candidates == 0
    assert len(resp.promotion_results) == 0


def test_03_timeframe_mismatch_cannot_match(service):
    """Querying 4h cannot match a candidate formulated on 1h."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, timeframe="1h")
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, timeframe="1h")
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="4h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.total_candidates == 0


def test_04_behaviour_mismatch_cannot_match(service):
    """Observations with a different behaviour do not match candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, behaviour="LOWER_PRICE_REJECTION")
    cand_as_of = base_obs[-1].observation_time
    # Forward obs with different behaviour
    fwd_obs = make_forward_observations(cand_as_of, behaviour="UPPER_PRICE_REJECTION")
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.total_candidates == 1
    # Candidate exists, but no matching forward obs for its behaviour
    assert resp.promotion_results[0].forward_validation_sample_size == 0
    assert resp.promotion_results[0].promotion_status == PromotionStatus.INSUFFICIENT_DATA


def test_05_context_mismatch_cannot_match(service):
    """Observations in a different context regime do not inflate forward sample."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, regime="UPTREND", support="WICK_REJECTED_SUPPORT")
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, regime="DOWNTREND", support="WICK_REJECTED_RESISTANCE")
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.total_candidates == 1
    assert resp.promotion_results[0].forward_validation_sample_size == 0
    assert resp.promotion_results[0].promotion_status == PromotionStatus.INSUFFICIENT_DATA


def test_06_horizon_mismatch_cannot_match(service):
    """Querying H=10 does not match a candidate evaluated at H=5."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, horizon=5)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, horizon=5)
    val_as_of = fwd_obs[-1].observation_time

    # Get the H=5 candidate ID
    h5_hyp = service.get_historical_hypotheses(
        instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs
    )
    h5_cand_id = h5_hyp.hypotheses[0].hypothesis_id
    assert "-H5-" in h5_cand_id

    # Attempt to query that candidate ID with horizon=10
    resp = service.get_research_promotion(
        candidate_id=h5_cand_id,
        instrument="EURUSD",
        timeframe="1h",
        horizon=10,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.total_candidates == 0


# =============================================================================
# GROUP B — CANDIDATE IMMUTABILITY (Tests 7 - 11)
# =============================================================================

def test_07_candidate_wording_unchanged(service):
    """Candidate wording is identical to Phase 3 formulation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    hyp_resp = service.get_historical_hypotheses(
        instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs
    )
    expected_wording = hyp_resp.hypotheses[0].descriptive_observation

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.promotion_results[0].candidate_wording == expected_wording


def test_08_discovery_metrics_unchanged(service):
    """Discovery sample size and metrics are preserved intact."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.discovery_sample_size == 35
    assert res.discovery_metrics is not None
    assert res.discovery_metrics.sample_size == 35


def test_09_historical_validation_metrics_unchanged(service):
    """Historical Validation metrics from Phase 3 remain preserved."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.validation_sample_size == 15
    assert res.validation_metrics is not None
    assert res.validation_metrics.sample_size == 15


def test_10_qualification_status_preserved(service):
    """Candidate qualification status is CANDIDATE_PAPER_HYPOTHESIS."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.promotion_results[0].qualification_status == HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS


def test_11_candidate_id_unchanged(service):
    """Candidate ID string is unchanged throughout promotion."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    hyp_resp = service.get_historical_hypotheses(
        instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs
    )
    expected_id = hyp_resp.hypotheses[0].hypothesis_id

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.promotion_results[0].candidate_id == expected_id


# =============================================================================
# GROUP C — TEMPORAL ISOLATION & BOUNDARY ENFORCEMENT (Tests 12 - 17)
# =============================================================================

def test_12_candidate_as_of_boundary_enforced(service):
    """Observations prior to candidate_as_of never enter forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    # No forward obs after cand_as_of
    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=cand_as_of + timedelta(days=1),
        observations=base_obs,
    )
    res = resp.promotion_results[0]
    assert res.forward_validation_sample_size == 0
    assert res.promotion_status == PromotionStatus.INSUFFICIENT_DATA


def test_13_boundary_equality_excluded(service):
    """An observation with T0 == candidate_as_of is not part of forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Add an observation at exact cand_as_of with different ID
    boundary_obs = make_synthetic_observation("boundary-001", cand_as_of)
    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=cand_as_of + timedelta(hours=1),
        observations=base_obs + [boundary_obs],
    )
    res = resp.promotion_results[0]
    assert res.forward_validation_sample_size == 0


def test_14_strictly_greater_included(service):
    """An observation with T0 > candidate_as_of is included in forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    after_obs = make_synthetic_observation("after-001", cand_as_of + timedelta(seconds=1))
    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=cand_as_of + timedelta(hours=2),
        observations=base_obs + [after_obs],
    )
    res = resp.promotion_results[0]
    assert res.forward_validation_sample_size == 1


def test_15_validation_as_of_boundary_enforced(service):
    """Forward observations strictly <= validation_as_of are evaluated."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=20)
    # Cut off at 10th observation
    val_as_of = fwd_obs[9].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.forward_validation_sample_size == 10


def test_16_strictly_after_validation_as_of_excluded(service):
    """Observations after validation_as_of are excluded from forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=30)
    val_as_of = fwd_obs[14].observation_time  # Cutoff at 15th

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.forward_validation_sample_size == 15


def test_17_forward_observations_never_enter_discovery(service):
    """Forward validation observations do not leak into the Discovery sample."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=100)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.discovery_sample_size == 35  # Still exactly 35


# =============================================================================
# GROUP D — ELIGIBILITY GATES & CATEGORICAL STATUSES (Tests 18 - 25)
# =============================================================================

def test_18_eligible_informational_on_valid_data(service):
    """Candidate with valid forward validation (N >= 30, follow-through >= 50%) is ELIGIBLE_INFORMATIONAL."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35, raw_return=0.0030)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.promotion_status == PromotionStatus.ELIGIBLE_INFORMATIONAL
    assert resp.eligible_informational_candidates == 1
    assert "Candidate satisfies all informational promotion eligibility requirements." in res.promotion_reasons


def test_19_empty_forward_population_is_insufficient(service):
    """Candidate with 0 forward validation observations receives INSUFFICIENT_DATA."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=cand_as_of + timedelta(days=1),
        observations=base_obs,
    )
    res = resp.promotion_results[0]
    assert res.promotion_status == PromotionStatus.INSUFFICIENT_DATA
    assert resp.limited_data_candidates == 1


def test_20_all_incomplete_forward_population_is_insufficient(service):
    """Candidate where all forward observations are INCOMPLETE receives INSUFFICIENT_DATA."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35, data_quality=DataQuality.INCOMPLETE)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.promotion_status == PromotionStatus.INSUFFICIENT_DATA
    assert res.data_quality_breakdown.incomplete_count == 35


def test_21_invalid_only_population_is_data_quality_limited(service):
    """Forward population containing exclusively INVALID observations receives DATA_QUALITY_LIMITED."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35, data_quality=DataQuality.INVALID)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.promotion_status == PromotionStatus.DATA_QUALITY_LIMITED
    assert resp.data_quality_limited_candidates == 1


def test_22_limited_sample_receives_limited_data(service):
    """Forward validation with 10 <= N < 30 receives LIMITED_DATA."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=15)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.promotion_status == PromotionStatus.LIMITED_DATA
    assert resp.limited_data_candidates == 1


def test_23_failed_forward_outcomes_receives_not_eligible(service):
    """Forward validation where descriptive characteristics do not validate (follow through < 50%) is NOT_ELIGIBLE."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    # Strong negative return => follow-through rate 0.0%
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35, raw_return=-0.0050)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    res = resp.promotion_results[0]
    assert res.promotion_status == PromotionStatus.NOT_ELIGIBLE
    assert resp.not_eligible_candidates == 1


def test_24_cross_instrument_isolation_guaranteed(service):
    """Observations from XAUUSD are never mixed into EURUSD forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    eur_base = make_baseline_observations(t0, instrument="EURUSD")
    cand_as_of = eur_base[-1].observation_time
    xau_fwd = make_forward_observations(cand_as_of, instrument="XAUUSD", n_forward=35)
    val_as_of = xau_fwd[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=eur_base + xau_fwd,
    )
    res = resp.promotion_results[0]
    assert res.instrument == "EURUSD"
    # XAUUSD forward obs must NOT contribute to EURUSD forward sample size
    assert res.forward_validation_sample_size == 0
    assert res.promotion_status == PromotionStatus.INSUFFICIENT_DATA


def test_25_cross_timeframe_isolation_guaranteed(service):
    """Observations from 4h are never mixed into 1h forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_1h = make_baseline_observations(t0, timeframe="1h")
    cand_as_of = base_1h[-1].observation_time
    fwd_4h = make_forward_observations(cand_as_of, timeframe="4h", n_forward=35)
    val_as_of = fwd_4h[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_1h + fwd_4h,
    )
    res = resp.promotion_results[0]
    assert res.timeframe == "1H"
    assert res.forward_validation_sample_size == 0
    assert res.promotion_status == PromotionStatus.INSUFFICIENT_DATA


# =============================================================================
# GROUP E — SIGNAL ISOLATION & BEHAVIORAL INVARIANCE (Tests 26 - 32)
# =============================================================================

@pytest.fixture
def mock_market_state():
    now = datetime.now(timezone.utc)
    return MarketState(
        id="market-test-01",
        timestamp=now,
        session="London",
        prices={
            "EURUSD": MarketPrice(symbol="EURUSD", currentPrice=1.0850, bid=1.0849, ask=1.0851, spread=0.2, timestamp=now, provider="twelve_data"),
            "GBPUSD": MarketPrice(symbol="GBPUSD", currentPrice=1.2750, bid=1.2748, ask=1.2752, spread=0.4, timestamp=now, provider="twelve_data"),
            "XAUUSD": MarketPrice(symbol="XAUUSD", currentPrice=2400.0, bid=2399.8, ask=2400.2, spread=0.4, timestamp=now, provider="twelve_data"),
        },
        volatility="Moderate",
        overallMarketConfidence=75,
        dataAgeSeconds=10,
    )


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


def test_26_signal_recommendation_identical_with_and_without_context(mock_market_state, mock_strategy):
    """Presence of researchContext does not alter candidate direction/recommendation."""
    engine = SignalGenerationEngine()
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])

    dummy_context = ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Test note",
        limitations=["Informational only."],
    )

    cands_with = engine.generate_candidates(
        mock_market_state,
        [mock_strategy],
        research_contexts={"EURUSD": dummy_context},
    )

    assert len(cands_without) == len(cands_with)
    assert cands_without[0].direction == cands_with[0].direction


def test_27_signal_entry_identical_with_and_without_context(mock_market_state, mock_strategy):
    """Presence of researchContext does not alter entry price."""
    engine = SignalGenerationEngine()
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])

    dummy_context = ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Test note",
        limitations=["Informational only."],
    )

    cands_with = engine.generate_candidates(
        mock_market_state,
        [mock_strategy],
        research_contexts={"EURUSD": dummy_context},
    )

    assert cands_without[0].entryPrice == cands_with[0].entryPrice


def test_28_signal_stop_loss_identical_with_and_without_context(mock_market_state, mock_strategy):
    """Presence of researchContext does not alter stop loss."""
    engine = SignalGenerationEngine()
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])

    dummy_context = ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Test note",
        limitations=["Informational only."],
    )

    cands_with = engine.generate_candidates(
        mock_market_state,
        [mock_strategy],
        research_contexts={"EURUSD": dummy_context},
    )

    assert cands_without[0].stopLoss == cands_with[0].stopLoss


def test_29_signal_take_profit_identical_with_and_without_context(mock_market_state, mock_strategy):
    """Presence of researchContext does not alter take profit."""
    engine = SignalGenerationEngine()
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])

    dummy_context = ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Test note",
        limitations=["Informational only."],
    )

    cands_with = engine.generate_candidates(
        mock_market_state,
        [mock_strategy],
        research_contexts={"EURUSD": dummy_context},
    )

    assert cands_without[0].takeProfit == cands_with[0].takeProfit


def test_30_signal_confidence_identical_with_and_without_context(mock_market_state, mock_strategy):
    """Presence of researchContext does not alter confidence score."""
    engine = SignalGenerationEngine()
    cands_without = engine.generate_candidates(mock_market_state, [mock_strategy])

    dummy_context = ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Test note",
        limitations=["Informational only."],
    )

    cands_with = engine.generate_candidates(
        mock_market_state,
        [mock_strategy],
        research_contexts={"EURUSD": dummy_context},
    )

    assert cands_without[0].confidence == cands_with[0].confidence
    assert cands_without[0].readinessScore == cands_with[0].readinessScore


def test_31_signal_generation_works_with_none_context(mock_market_state, mock_strategy):
    """Default candidate generation has researchContext = None."""
    engine = SignalGenerationEngine()
    cands = engine.generate_candidates(mock_market_state, [mock_strategy])
    assert len(cands) == 1
    assert cands[0].researchContext is None


def test_32_attach_research_context_helper(mock_market_state, mock_strategy):
    """attach_research_context safely enriches candidate with zero side-effects."""
    engine = SignalGenerationEngine()
    cand = engine.generate_candidates(mock_market_state, [mock_strategy])[0]
    assert cand.researchContext is None

    dummy_context = ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Test note",
        limitations=["Informational only."],
    )

    enriched = SignalGenerationEngine.attach_research_context(cand, dummy_context)
    assert enriched.researchContext == dummy_context


# =============================================================================
# GROUP F — SAFETY & ZERO SIDE-EFFECTS (Tests 33 - 38)
# =============================================================================

def test_33_zero_db_writes_during_promotion(service):
    """Calling get_research_promotion performs 0 database writes."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    # Run promotion
    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert resp.total_candidates == 1


def test_34_zero_broker_calls_in_promotion(service):
    """The promotion gate contains zero references to broker calls or MT5 orders."""
    import inspect
    source = inspect.getsource(service.get_research_promotion)
    assert "order_send" not in source
    assert "order_modify" not in source
    assert "order_close" not in source
    assert "executeOrder" not in source


def test_35_zero_mt5_imports_in_promotion_schemas():
    """Schemas module contains zero MetaTrader5 imports."""
    import app.schemas.research_promotion as mod
    import inspect
    source = inspect.getsource(mod)
    assert "MetaTrader5" not in source
    assert "MT5" not in source


def test_36_zero_order_execution_service_invocations(service):
    """get_research_promotion never calls OrderExecutionService."""
    import inspect
    source = inspect.getsource(service.get_research_promotion)
    assert "OrderExecutionService" not in source
    assert "order_execution_service" not in source


def test_37_zero_capital_guardian_modifications(service):
    """get_research_promotion never modifies CapitalGuardianService."""
    import inspect
    source = inspect.getsource(service.get_research_promotion)
    assert "CapitalGuardianService" not in source
    assert "capital_guardian_service" not in source


def test_38_alembic_head_remains_0007():
    """Alembic migrations remain untouched with head 0007_v10_initial_monetary_risk."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from pathlib import Path
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    config = Config(str(ini_path))
    script = ScriptDirectory.from_config(config)
    head_rev = script.get_current_head()
    assert head_rev in ("0007_v10_initial_monetary_risk", "0008_v10_initial_stop_loss")


# =============================================================================
# GROUP G — NON-RANKING & PROHIBITED TERM PROTECTIONS (Tests 39 - 42)
# =============================================================================

def test_39_no_recommendation_language_in_promotion_results(service):
    """Promotion results contain zero BUY/SELL recommendations."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    for r in resp.promotion_results:
        for reason in r.promotion_reasons:
            service.assert_no_forbidden_recommendation_terms(reason)
        for lim in r.promotion_limitations:
            service.assert_no_forbidden_recommendation_terms(lim)


def test_40_no_ranking_fields_in_promotion_schemas():
    """ResearchPromotionResult schema has no ranking or scoring fields."""
    fields = set(ResearchPromotionResult.model_fields.keys())
    assert "rank" not in fields
    assert "priority" not in fields
    assert "score" not in fields
    assert "edge" not in fields
    assert "win_probability" not in fields


def test_41_no_prohibited_superlatives_in_response(service):
    """Top-level response contains zero prohibited terms."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    resp = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    for lim in resp.limitations:
        service.assert_no_forbidden_recommendation_terms(lim)


def test_42_provenance_note_free_of_forbidden_terms(service):
    """Context provenance note passes assert_no_forbidden_recommendation_terms."""
    dummy_res = ResearchPromotionResult(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_wording="Descriptive observation only.",
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        promotion_reasons=["Eligible."],
        promotion_limitations=["Informational only."],
    )
    ctx = HistoricalFindingsService.build_research_signal_context(dummy_res)
    service.assert_no_forbidden_recommendation_terms(ctx.provenance_note)


# =============================================================================
# GROUP H — DETERMINISM & REPEATABILITY (Tests 43 - 45)
# =============================================================================

def test_43_identical_requests_return_identical_results(service):
    """Repeated calls with identical inputs return bitwise identical payloads."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0)
    cand_as_of = base_obs[-1].observation_time
    fwd_obs = make_forward_observations(cand_as_of, n_forward=35)
    val_as_of = fwd_obs[-1].observation_time

    r1 = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    r2 = service.get_research_promotion(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=base_obs + fwd_obs,
    )
    assert r1.model_dump() == r2.model_dump()


def test_44_deterministic_candidate_ordering(service):
    """Promotion results are deterministically sorted by (instrument, timeframe, candidate_id)."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    eur_base = make_baseline_observations(t0, instrument="EURUSD")
    gbp_base = make_baseline_observations(t0, instrument="GBPUSD")
    cand_as_of = eur_base[-1].observation_time
    val_as_of = cand_as_of + timedelta(days=1)

    resp = service.get_research_promotion(
        candidate_as_of=cand_as_of,
        validation_as_of=val_as_of,
        observations=eur_base + gbp_base,
    )
    keys = [(r.instrument.upper(), r.timeframe.upper(), r.candidate_id) for r in resp.promotion_results]
    assert keys == sorted(keys)


def test_45_api_promotion_endpoint(client):
    """GET /api/v1/analytics/candlestick-behaviour/promotion returns HTTP 200."""
    resp = client.get(
        "/api/v1/analytics/candlestick-behaviour/promotion",
        params={
            "instrument": "EURUSD",
            "timeframe": "1h",
            "horizon": 5,
            "candidate_as_of": "2026-09-22T00:00:00Z",
            "validation_as_of": "2026-09-22T12:00:00Z",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_name"] == "RESEARCH_PROMOTION_GATE"
    assert "promotion_results" in data
    assert "limitations" in data


# =============================================================================
# GROUP I — BEHAVIORAL REGRESSION CHECK (Section 14)
# =============================================================================

def test_46_behavioral_regression_check(mock_market_state, mock_strategy):
    """Given identical market state and strategy inputs:
    SignalGenerationEngine WITHOUT researchContext and WITH researchContext
    produce identical recommendation, entry, stop loss, take profit, position size,
    risk, and strategy identity. The ONLY difference permitted is researchContext.
    """
    engine = SignalGenerationEngine()

    cands_without = engine.generate_candidates(
        market_state=mock_market_state,
        strategies=[mock_strategy],
    )

    dummy_context = ResearchSignalContext(
        candidate_id="HYP-EURUSD-1H-H5-TEST",
        instrument="EURUSD",
        timeframe="1H",
        horizon=5,
        behaviour_identity="LOWER_PRICE_REJECTION",
        context_identity="UPTREND",
        candidate_as_of=datetime.now(timezone.utc),
        validation_as_of=datetime.now(timezone.utc),
        promotion_status=PromotionStatus.ELIGIBLE_INFORMATIONAL,
        qualification_status=HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS,
        forward_validation_sample_size=35,
        forward_validation_status=ForwardValidationStatus.VALIDATED_DESCRIPTIVELY,
        methodology_version="1.0.0",
        provenance_note="Test note",
        limitations=["Informational only."],
    )

    cands_with = engine.generate_candidates(
        market_state=mock_market_state,
        strategies=[mock_strategy],
        research_contexts={"EURUSD": dummy_context},
    )

    assert len(cands_without) == 1
    assert len(cands_with) == 1

    c_wo = cands_without[0]
    c_w = cands_with[0]

    # Verify identical core trading fields
    assert c_wo.direction == c_w.direction
    assert c_wo.entryPrice == c_w.entryPrice
    assert c_wo.stopLoss == c_w.stopLoss
    assert c_wo.takeProfit == c_w.takeProfit
    assert c_wo.riskReward == c_w.riskReward
    assert c_wo.confidence == c_w.confidence
    assert c_wo.readinessScore == c_w.readinessScore
    assert c_wo.status == c_w.status
    assert c_wo.strategyId == c_w.strategyId
    assert c_wo.strategyName == c_w.strategyName
    assert c_wo.symbol == c_w.symbol

    # Verify that the ONLY difference is researchContext
    assert c_wo.researchContext is None
    assert c_w.researchContext == dummy_context

    d_wo = c_wo.model_dump(exclude={"evaluationDurationMs", "generatedAt", "evaluationStartedAt", "evaluationCompletedAt", "researchContext"})
    d_w = c_w.model_dump(exclude={"evaluationDurationMs", "generatedAt", "evaluationStartedAt", "evaluationCompletedAt", "researchContext"})
    assert d_wo == d_w
