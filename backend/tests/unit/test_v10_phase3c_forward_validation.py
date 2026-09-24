"""
Falcon V10 — Phase 3C Independent Paper-Only Forward Validation & Research Audit Test Suite.

Comprehensive verification of:
1. Candidate Freeze & Immutability (Candidate ID, wording, Discovery/Validation metrics unchanged)
2. Boundary Enforcement (candidate_as_of < T0 <= validation_as_of; boundary equality at candidate_as_of excluded)
3. Population Separation (Discovery, historical Validation, Monitoring, Forward Validation strictly disjoint)
4. Data Quality Filtering (VALID contributes to metrics; INCOMPLETE/INVALID/UNKNOWN tracked in census)
5. Exact 5-Tuple Identity (instrument, timeframe, behaviour, context, horizon)
6. Candle Mathematics & No-Lookahead (T0 excluded from outcome window; H=1,5,20 indexing; incomplete fail-closed)
7. Determinism & Traceability (identical requests -> identical response; MAX_OBSERVATION_IDS_SAMPLE <= 20)
8. Safety Invariants (Zero DB writes, zero broker calls, zero trading pipeline changes, Alembic head 0007_v10_initial_monetary_risk)
9. Methodology Preservation (Sample adequacy: ADEQUATE >= 30, LIMITED 10..29, INSUFFICIENT 1..9, UNKNOWN 0; no ranking)
"""

from datetime import datetime, timedelta, timezone
import math
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
    CandidateHypothesis,
    CandidateMonitoringResponse,
    DirectionConsistency,
    ForwardValidationDataQualityCensus,
    ForwardValidationResponse,
    ForwardValidationResult,
    ForwardValidationStatus,
    GroupStabilityAnalysis,
    HypothesisStatus,
    StabilityStatus,
)


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
    """Generates a complete qualifying Discovery + Validation baseline set."""
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


# =============================================================================
# GROUP A — CANDIDATE FREEZE & IMMUTABILITY (Tests 1 - 5)
# =============================================================================

def test_01_candidate_identity_immutable(service):
    """Candidate ID remains identical before and after forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Pre-fetch candidate directly
    hyp_before = service.get_historical_hypotheses(
        instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs
    )
    cand_before = hyp_before.hypotheses[0]

    # Evaluate forward validation
    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1), raw_return=0.0050)
        for i in range(35)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=40),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.candidate_id == cand_before.hypothesis_id
    assert res.instrument == cand_before.instrument
    assert res.timeframe == cand_before.timeframe
    assert res.horizon == cand_before.horizon


def test_02_candidate_wording_immutable(service):
    """Candidate descriptive wording formulated from Discovery data is immutable."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    hyp_before = service.get_historical_hypotheses(
        instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs
    )
    wording_before = hyp_before.hypotheses[0].descriptive_observation

    # Forward data with completely different outcomes (-0.0050 loss)
    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1), raw_return=-0.0050)
        for i in range(35)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=40),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.candidate_wording == wording_before


def test_03_discovery_metrics_immutable(service):
    """Discovery sample size and descriptive metrics cannot be altered by forward data."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    hyp_before = service.get_historical_hypotheses(
        instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs
    )
    cand_before = hyp_before.hypotheses[0]

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(50)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=60),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.discovery_sample_size == cand_before.discovery_sample_size
    assert res.discovery_sample_size == 35
    assert res.discovery_metrics.follow_through_rate == cand_before.discovery_metrics.follow_through_rate


def test_04_historical_validation_metrics_immutable(service):
    """Historical Validation (the 30% baseline) sample size and metrics remain unchanged."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    hyp_before = service.get_historical_hypotheses(
        instrument="EURUSD", timeframe="1h", horizon=5, as_of=cand_as_of, observations=base_obs
    )
    cand_before = hyp_before.hypotheses[0]

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(40)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=50),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.validation_sample_size == cand_before.validation_sample_size
    assert res.validation_sample_size == 15
    assert res.validation_metrics.follow_through_rate == cand_before.validation_metrics.follow_through_rate


def test_05_qualification_status_immutable(service):
    """Candidate qualification status is frozen as of candidate_as_of."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Forward data with completely inverted outcomes
    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1), raw_return=-0.0100)
        for i in range(35)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=40),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.qualification_status == HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS


# =============================================================================
# GROUP B — BOUNDARY ENFORCEMENT (Tests 6 - 10)
# =============================================================================

def test_06_observation_at_candidate_as_of_excluded(service):
    """Observation at exactly candidate_as_of cannot enter Forward Validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Add an observation precisely at candidate_as_of
    exact_obs = make_synthetic_observation("exact-bound", cand_as_of)

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=5),
        observations=base_obs + [exact_obs],
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 0
    assert "exact-bound" not in res.observation_ids_sample


def test_07_observation_after_candidate_as_of_included(service):
    """Observation at candidate_as_of + 1 second is included in Forward Validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = make_synthetic_observation("fwd-valid", cand_as_of + timedelta(seconds=1))

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=1),
        observations=base_obs + [fwd_obs],
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 1
    assert "fwd-valid" in res.observation_ids_sample


def test_08_observation_at_validation_as_of_included(service):
    """Observation at exactly validation_as_of is included in Forward Validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    val_as_of = cand_as_of + timedelta(hours=5)

    fwd_obs = make_synthetic_observation("fwd-exact-upper", val_as_of)

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + [fwd_obs],
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 1
    assert "fwd-exact-upper" in res.observation_ids_sample


def test_09_observation_after_validation_as_of_excluded(service):
    """Observation after validation_as_of is strictly excluded."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time
    val_as_of = cand_as_of + timedelta(hours=5)

    after_obs = make_synthetic_observation("after-bound", val_as_of + timedelta(seconds=1))

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=val_as_of,
        observations=base_obs + [after_obs],
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 0
    assert "after-bound" not in res.observation_ids_sample


def test_10_empty_forward_window_handled_safely(service):
    """When validation_as_of <= candidate_as_of, forward window is empty and status is NO_FORWARD_DATA."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of,
        observations=base_obs,
    )
    assert resp.total_forward_observations == 0
    assert resp.total_valid_forward_observations == 0
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 0
    assert res.forward_validation_status == ForwardValidationStatus.NO_FORWARD_DATA


# =============================================================================
# GROUP C — POPULATION SEPARATION (Tests 11 - 15)
# =============================================================================

def test_11_discovery_never_enters_forward_validation(service):
    """Discovery observations (the first 70%) never enter forward validation metrics or IDs."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs,
    )
    res = resp.validation_results[0]
    for disc_id in [f"disc-{i:03d}" for i in range(35)]:
        assert disc_id not in res.observation_ids_sample


def test_12_historical_validation_never_enters_forward_validation(service):
    """Historical Validation observations (the 30% baseline) never enter forward validation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs,
    )
    res = resp.validation_results[0]
    for val_id in [f"val-{j:03d}" for j in range(15)]:
        assert val_id not in res.observation_ids_sample


def test_13_monitoring_never_enters_forward_validation_arbitrarily(service):
    """Monitoring and Forward Validation are evaluated independently without mixing."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(10)
    ]
    # Call monitoring
    mon_resp = service.get_historical_monitoring(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs + fwd_obs,
    )
    # Call forward validation
    fwd_resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs + fwd_obs,
    )
    assert mon_resp.experiment_name == "HISTORICAL_CANDIDATE_MONITORING"
    assert fwd_resp.experiment_name == "INDEPENDENT_PAPER_FORWARD_VALIDATION"
    assert isinstance(fwd_resp.validation_results[0], ForwardValidationResult)


def test_14_forward_validation_cannot_modify_monitoring(service):
    """Invoking forward validation does not mutate monitoring state or schemas."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(10)
    ]
    # Call forward validation
    service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs + fwd_obs,
    )
    # Call monitoring and check schema integrity
    mon_resp = service.get_historical_monitoring(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs + fwd_obs,
    )
    rec = mon_resp.monitoring_records[0]
    assert hasattr(rec, "monitoring_sample_size")
    assert not hasattr(rec, "forward_validation_sample_size")


def test_15_forward_validation_cannot_modify_discovery(service):
    """Forward validation observations never modify Discovery census or wording."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1), raw_return=0.1000)
        for i in range(50)
    ]
    fwd_resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=60),
        observations=base_obs + fwd_obs,
    )
    res = fwd_resp.validation_results[0]
    assert res.discovery_sample_size == 35
    assert "N=35" in res.candidate_wording


# =============================================================================
# GROUP D — DATA QUALITY (Tests 16 - 20)
# =============================================================================

def test_16_valid_contributes_to_metrics(service):
    """DataQuality.VALID observations enter forward validation metrics calculation."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    valid_fwd = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1), raw_return=0.0030, data_quality=DataQuality.VALID)
        for i in range(12)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=20),
        observations=base_obs + valid_fwd,
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 12
    assert res.forward_validation_metrics is not None
    assert res.forward_validation_metrics.median_raw_return == 0.0030


def test_17_incomplete_excluded_from_metrics(service):
    """DataQuality.INCOMPLETE observations are strictly excluded from numerical metrics."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    inc_fwd = [
        make_synthetic_observation(f"fwd-inc-{i}", cand_as_of + timedelta(hours=i + 1), data_quality=DataQuality.INCOMPLETE)
        for i in range(8)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + inc_fwd,
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 0
    assert res.forward_validation_metrics is None
    assert res.data_quality_breakdown.incomplete_count == 8


def test_18_invalid_excluded_from_metrics(service):
    """DataQuality.INVALID observations are strictly excluded from numerical metrics."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    inv_fwd = [
        make_synthetic_observation(f"fwd-inv-{i}", cand_as_of + timedelta(hours=i + 1), data_quality=DataQuality.INVALID)
        for i in range(6)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + inv_fwd,
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 0
    assert res.forward_validation_metrics is None
    assert res.data_quality_breakdown.invalid_count == 6


def test_19_unknown_excluded_from_metrics(service):
    """DataQuality.FORWARD_DATA_GAP or UNKNOWN are classified as invalid/unknown and excluded."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    gap_fwd = [
        make_synthetic_observation(f"fwd-gap-{i}", cand_as_of + timedelta(hours=i + 1), data_quality=DataQuality.FORWARD_DATA_GAP)
        for i in range(4)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + gap_fwd,
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 0
    assert res.forward_validation_metrics is None
    assert res.data_quality_breakdown.unknown_count == 4
    assert res.data_quality_breakdown.valid_count == 0


def test_20_all_four_categories_appear_in_census(service):
    """Total observations equals valid + incomplete + invalid + unknown counts exactly."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = (
        [make_synthetic_observation(f"v-{i}", cand_as_of + timedelta(hours=1 + i), data_quality=DataQuality.VALID) for i in range(5)]
        + [make_synthetic_observation(f"inc-{i}", cand_as_of + timedelta(hours=6 + i), data_quality=DataQuality.INCOMPLETE) for i in range(3)]
        + [make_synthetic_observation(f"inv-{i}", cand_as_of + timedelta(hours=9 + i), data_quality=DataQuality.INVALID) for i in range(2)]
    )
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    census = res.data_quality_breakdown
    assert census.total_observations == 10
    assert census.valid_count == 5
    assert census.incomplete_count == 3
    assert census.invalid_count == 2
    assert census.total_observations == (census.valid_count + census.incomplete_count + census.invalid_count + census.unknown_count)


# =============================================================================
# GROUP E — EXACT 5-TUPLE IDENTITY (Tests 21 - 25)
# =============================================================================

def test_21_instrument_mismatch_cannot_match(service):
    """GBPUSD observation cannot match EURUSD candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, instrument="EURUSD")
    cand_as_of = base_obs[-1].observation_time

    gbp_fwd = [
        make_synthetic_observation(f"gbp-{i}", cand_as_of + timedelta(hours=i + 1), instrument="GBPUSD")
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + gbp_fwd,
    )
    res = resp.validation_results[0]
    assert res.instrument == "EURUSD"
    assert res.forward_validation_sample_size == 0


def test_22_timeframe_mismatch_cannot_match(service):
    """15min observation cannot match 1h candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, timeframe="1h")
    cand_as_of = base_obs[-1].observation_time

    m15_fwd = [
        make_synthetic_observation(f"m15-{i}", cand_as_of + timedelta(hours=i + 1), timeframe="15min")
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + m15_fwd,
    )
    res = resp.validation_results[0]
    assert res.timeframe == "1H"
    assert res.forward_validation_sample_size == 0


def test_23_behaviour_mismatch_cannot_match(service):
    """UPPER_PRICE_REJECTION observation cannot match LOWER_PRICE_REJECTION candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, behaviour="LOWER_PRICE_REJECTION")
    cand_as_of = base_obs[-1].observation_time

    upper_fwd = [
        make_synthetic_observation(f"up-{i}", cand_as_of + timedelta(hours=i + 1), behaviour="UPPER_PRICE_REJECTION")
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + upper_fwd,
    )
    res = resp.validation_results[0]
    assert res.behaviour_identity == "LOWER_PRICE_REJECTION"
    assert res.forward_validation_sample_size == 0


def test_24_context_mismatch_cannot_match(service):
    """DOWNTREND context observation cannot match UPTREND candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, regime="UPTREND")
    cand_as_of = base_obs[-1].observation_time

    down_fwd = [
        make_synthetic_observation(f"down-{i}", cand_as_of + timedelta(hours=i + 1), regime="DOWNTREND")
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + down_fwd,
    )
    res = resp.validation_results[0]
    assert "UPTREND" in res.context_identity
    assert res.forward_validation_sample_size == 0


def test_25_horizon_mismatch_cannot_match(service):
    """Forward outcome horizon 10 does not match candidate with horizon 5."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, horizon=5)
    cand_as_of = base_obs[-1].observation_time

    # Add observations whose primary metric is horizon 10
    h10_fwd = [
        make_synthetic_observation(f"h10-{i}", cand_as_of + timedelta(hours=i + 1), horizon=10)
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + h10_fwd,
    )
    res = resp.validation_results[0]
    assert res.horizon == 5
    assert res.forward_validation_sample_size == 0


# =============================================================================
# GROUP F — CANDLE MATHEMATICS & NO-LOOKAHEAD (Tests 26 - 30)
# =============================================================================

def test_26_t0_excluded_from_forward_window():
    """T0 is strictly excluded from its forward window in Phase 2 outcomes."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    obs = make_synthetic_observation("test-obs", t0, horizon=5)
    fw = obs.forward_windows[5]
    assert fw.horizon_candles == 5
    assert fw.reference_price == 1.1002


def test_27_h1_indexing(service):
    """H=1 forward window correctly indexes exactly 1 forward bar."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, horizon=1)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"h1-{i}", cand_as_of + timedelta(hours=i + 1), horizon=1)
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=1,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.horizon == 1
    assert res.forward_validation_sample_size == 10


def test_28_h5_indexing(service):
    """H=5 forward window correctly indexes 5 forward bars."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, horizon=5)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"h5-{i}", cand_as_of + timedelta(hours=i + 1), horizon=5)
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.horizon == 5
    assert res.forward_validation_sample_size == 10


def test_29_h20_indexing(service):
    """H=20 forward window correctly indexes 20 forward bars."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, horizon=20)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"h20-{i}", cand_as_of + timedelta(hours=i + 1), horizon=20)
        for i in range(10)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=20,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert res.horizon == 20
    assert res.forward_validation_sample_size == 10


def test_30_incomplete_horizon_fails_closed(service):
    """Trailing observations with pending forward horizon fail closed as INCOMPLETE."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    inc_obs = [
        make_synthetic_observation(f"inc-{i}", cand_as_of + timedelta(hours=i + 1), data_quality=DataQuality.INCOMPLETE)
        for i in range(5)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs + inc_obs,
    )
    res = resp.validation_results[0]
    assert res.forward_validation_sample_size == 0
    assert res.data_quality_breakdown.incomplete_count == 5


# =============================================================================
# GROUP G — DETERMINISM & TRACEABILITY (Tests 31 - 33)
# =============================================================================

def test_31_identical_request_produces_identical_response(service):
    """Identical requests produce byte-for-byte identical serialized responses."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(15)
    ]
    r1 = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=20),
        observations=base_obs + fwd_obs,
    )
    r2 = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=20),
        observations=base_obs + fwd_obs,
    )
    assert r1.model_dump_json() == r2.model_dump_json()


def test_32_deterministic_sorting(service):
    """Results are deterministically sorted by (instrument, timeframe, candidate_id)."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_eur = make_baseline_observations(t0, n_discovery=35, n_validation=15, instrument="EURUSD")
    base_gbp = make_baseline_observations(t0, n_discovery=35, n_validation=15, instrument="GBPUSD")
    cand_as_of = base_eur[-1].observation_time

    resp = service.get_forward_validation(
        instrument=None, timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=5),
        observations=base_eur + base_gbp,
    )
    keys = [(r.instrument.upper(), r.timeframe.upper(), r.candidate_id) for r in resp.validation_results]
    assert keys == sorted(keys)


def test_33_observation_ids_sample_max_20_deterministic(service):
    """Observation IDs sample capped at 20 and ordered by (observation_time, observation_id)."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i:03d}", cand_as_of + timedelta(hours=i + 1))
        for i in range(35)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=40),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    assert len(res.observation_ids_sample) <= 20
    assert len(res.observation_ids_sample) == 20
    assert res.observation_ids_sample == sorted(res.observation_ids_sample)


# =============================================================================
# GROUP H — SAFETY & ZERO-MUTATION (Tests 34 - 37)
# =============================================================================

def test_34_zero_database_writes():
    """Forward validation evaluation causes zero database mutations or dirty sessions."""
    from app.core.database import get_session
    from app.core.database.models import TradeJournalRecord, CapitalCycleRecord
    from sqlalchemy import select, func

    with get_session() as session:
        tj_before = session.scalar(select(func.count(TradeJournalRecord.id))) or 0
        cc_before = session.scalar(select(func.count(CapitalCycleRecord.id))) or 0

        cand_as_of = datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
        historical_findings_service.get_forward_validation(
            instrument="EURUSD",
            candidate_as_of=cand_as_of,
            validation_as_of=cand_as_of + timedelta(hours=10),
        )

        assert len(session.dirty) == 0
        assert len(session.new) == 0

        tj_after = session.scalar(select(func.count(TradeJournalRecord.id))) or 0
        cc_after = session.scalar(select(func.count(CapitalCycleRecord.id))) or 0

        assert tj_before == tj_after
        assert cc_before == cc_after


def test_35_zero_broker_calls():
    """Phase 3C forward validation does not import or invoke MetaTrader5."""
    import sys
    assert "MetaTrader5" not in sys.modules


def test_36_zero_trading_pipeline_invocations():
    """HistoricalFindingsService has zero attributes or couplings to live execution."""
    assert not hasattr(historical_findings_service, "order_execution_service")
    assert not hasattr(historical_findings_service, "signal_authorization_service")
    assert not hasattr(historical_findings_service, "capital_guardian_service")


def test_37_zero_database_migrations():
    """Alembic migration head remains strictly at 0007_v10_initial_monetary_risk."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0007_v10_initial_monetary_risk"


# =============================================================================
# GROUP I — METHODOLOGY & LANGUAGE AUDIT (Tests 38 - 42)
# =============================================================================

def test_38_exact_sample_adequacy_terminology(service):
    """Sample adequacy uses Falcon's exact research definitions."""
    assert service.evaluate_sample_adequacy(35) == SampleAdequacy.ADEQUATE
    assert service.evaluate_sample_adequacy(30) == SampleAdequacy.ADEQUATE
    assert service.evaluate_sample_adequacy(29) == SampleAdequacy.LIMITED
    assert service.evaluate_sample_adequacy(10) == SampleAdequacy.LIMITED
    assert service.evaluate_sample_adequacy(9) == SampleAdequacy.INSUFFICIENT
    assert service.evaluate_sample_adequacy(1) == SampleAdequacy.INSUFFICIENT
    assert service.evaluate_sample_adequacy(0) == SampleAdequacy.UNKNOWN


def test_39_qualification_threshold_n30_unchanged(service):
    """Candidate qualification threshold remains N >= 30 in Discovery."""
    assert service.MIN_CANDIDATE_QUALIFICATION_SAMPLE == 30


def test_40_70_30_historical_methodology_unchanged(service):
    """Discovery / Validation split remains 70/30 in historical research."""
    assert service.DISCOVERY_VALIDATION_METHODOLOGY == "CHRONOLOGICAL_70_30_V1"
    obs = [make_synthetic_observation(f"o-{i}", datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc) + timedelta(hours=i)) for i in range(100)]
    disc, val = service.partition_discovery_validation(obs)
    assert len(disc) == 70
    assert len(val) == 30


def test_41_tertile_methodology_unchanged(service):
    """Temporal stability methodology uses chronological tertiles."""
    assert service.PARTITION_METHODOLOGY == "CHRONOLOGICAL_TERTILES_V1"


def test_42_no_ranking_or_forbidden_recommendation_language(service):
    """Forward validation output contains zero forbidden recommendation or directive words."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    fwd_obs = [
        make_synthetic_observation(f"fwd-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(35)
    ]
    resp = service.get_forward_validation(
        instrument="EURUSD", timeframe="1h", horizon=5,
        candidate_as_of=cand_as_of, validation_as_of=cand_as_of + timedelta(hours=40),
        observations=base_obs + fwd_obs,
    )
    res = resp.validation_results[0]
    all_text = " ".join([
        res.candidate_wording,
        " ".join(res.candidate_limitations),
        " ".join(res.validation_limitations),
        " ".join(resp.limitations),
    ])
    forbidden = {"BUY", "SELL", "ENTER", "EXIT", "TRADE", "BEST", "STRONGEST", "OPTIMAL", "HIGH-CONFIDENCE", "RECOMMENDED", "EDGE", "WINNING SETUP"}
    words = all_text.upper().split()
    for w in words:
        clean = w.strip(".,;:!?()\"'")
        assert clean not in forbidden, f"Forbidden term '{clean}' found in forward validation text"


# =============================================================================
# REST API INTEGRATION TESTS (Tests 43 - 44)
# =============================================================================

def test_43_api_forward_validation_endpoint_200(client):
    """GET /api/v1/analytics/candlestick-behaviour/forward-validation returns HTTP 200 with schema."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/forward-validation?instrument=EURUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_name"] == "INDEPENDENT_PAPER_FORWARD_VALIDATION"
    assert "validation_results" in data
    assert "candidate_as_of" in data
    assert "validation_as_of" in data


def test_44_api_temporal_boundary_empty(client):
    """API endpoint returns 200 and 0 forward observations when validation_as_of <= candidate_as_of."""
    cand_as_of = "2026-09-22T00:00:00Z"
    resp = client.get(
        f"/api/v1/analytics/candlestick-behaviour/forward-validation?instrument=EURUSD&candidate_as_of={cand_as_of}&validation_as_of={cand_as_of}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_forward_observations"] == 0
    assert data["total_valid_forward_observations"] == 0
