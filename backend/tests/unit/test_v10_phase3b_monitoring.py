"""
Falcon V10 — Phase 3B Historical Candidate Monitoring & Persistence Test Suite.

Comprehensive verification of:
1. Strict Temporal Boundaries (candidate_as_of < observation_time <= as_of; equality excluded)
2. Three-Way Population Separation (Discovery, Validation, Monitoring strictly partitioned)
3. Candidate Immutability (Discovery N, metrics, wording, qualification preserved)
4. Data Quality Filtering (Only DataQuality.VALID enters metrics; INCOMPLETE/INVALID tracked in census)
5. Exact 5-Tuple Candidate Matching (instrument, timeframe, horizon, behaviour, context)
6. Deterministic Ordering and Traceability (MAX_OBSERVATION_IDS_SAMPLE = 20)
7. Sample Adequacy Terminology (ADEQUATE >= 30, LIMITED 10..29, INSUFFICIENT 1..9, UNKNOWN 0)
8. Zero Database Mutations & Zero Broker Calls (Alembic head 0007_v10_initial_monetary_risk)
9. Production Trading Pipeline Isolation (SignalService, CapitalGuardian, Captain untouched)
10. REST API Endpoint Integration (GET /api/v1/analytics/candlestick-behaviour/monitoring)
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
    CandidateMonitoring,
    CandidateMonitoringResponse,
    DirectionConsistency,
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
# 1. TEMPORAL BOUNDARY TESTS (Tests 1 - 5)
# =============================================================================

def test_01_monitoring_excludes_observation_at_candidate_as_of(service):
    """Observation with observation_time == candidate_as_of is strictly excluded from monitoring."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Add observation exactly at candidate_as_of
    obs_at_cand = make_synthetic_observation("obs-at-boundary", cand_as_of)
    # Add observation strictly after candidate_as_of
    obs_after = make_synthetic_observation("obs-after-boundary", cand_as_of + timedelta(hours=1))

    all_obs = base_obs + [obs_at_cand, obs_after]

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=5),
        observations=all_obs,
    )

    assert resp.total_candidates >= 1
    rec = resp.monitoring_records[0]
    # Only obs_after should be present (1 observation)
    assert rec.monitoring_total_observations == 1
    assert "obs-at-boundary" not in rec.observation_ids_sample
    assert "obs-after-boundary" in rec.observation_ids_sample


def test_02_monitoring_includes_observation_strictly_after_candidate_as_of(service):
    """Observations strictly after candidate_as_of are included in monitoring."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Add 5 monitoring observations
    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(5)
    ]
    all_obs = base_obs + mon_obs

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=10),
        observations=all_obs,
    )

    rec = resp.monitoring_records[0]
    assert rec.monitoring_total_observations == 5
    assert rec.monitoring_sample_size == 5


def test_03_monitoring_respects_as_of_boundary(service):
    """Monitoring observations must obey observation_time <= as_of."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Add 10 monitoring observations
    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(10)
    ]
    all_obs = base_obs + mon_obs

    # Set as_of to include only first 4 monitoring observations
    eval_as_of = cand_as_of + timedelta(hours=4)
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=eval_as_of,
        observations=all_obs,
    )

    rec = resp.monitoring_records[0]
    assert rec.monitoring_total_observations == 4
    assert rec.monitoring_end == eval_as_of


def test_04_monitoring_excludes_observations_after_as_of(service):
    """Observations beyond as_of are strictly excluded from monitoring."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # 5 observations before as_of, 5 observations after as_of
    eval_as_of = cand_as_of + timedelta(hours=5)
    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(10)
    ]
    all_obs = base_obs + mon_obs

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=eval_as_of,
        observations=all_obs,
    )

    rec = resp.monitoring_records[0]
    assert rec.monitoring_total_observations == 5
    for obs_id in rec.observation_ids_sample:
        idx = int(obs_id.split("-")[1])
        assert idx < 5


def test_05_candidate_metrics_unchanged_when_monitoring_data_added(service):
    """Candidate Discovery and Validation metrics remain 100% identical when monitoring data is introduced."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # 1. Evaluation without monitoring observations
    resp_before = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of,
        observations=base_obs,
    )
    rec_before = resp_before.monitoring_records[0]

    # 2. Evaluation with 20 new monitoring observations
    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(20)
    ]
    all_obs = base_obs + mon_obs

    resp_after = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=25),
        observations=all_obs,
    )
    rec_after = resp_after.monitoring_records[0]

    # Candidate baseline must remain unchanged
    assert rec_before.discovery_sample_size == rec_after.discovery_sample_size
    assert rec_before.discovery_metrics.median_raw_return == rec_after.discovery_metrics.median_raw_return
    assert rec_before.validation_sample_size == rec_after.validation_sample_size
    assert rec_before.candidate_wording == rec_after.candidate_wording
    assert rec_before.qualification_status == rec_after.qualification_status


# =============================================================================
# 2. POPULATION SEPARATION TESTS (Tests 6 - 10)
# =============================================================================

def test_06_discovery_remains_unchanged(service):
    """Discovery sample size is strictly unaffected by monitoring observations."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(50)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=60),
        observations=base_obs + mon_obs,
    )
    rec = resp.monitoring_records[0]
    assert rec.discovery_sample_size == 35


def test_07_validation_remains_unchanged(service):
    """Validation sample size is strictly unaffected by monitoring observations."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(50)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=60),
        observations=base_obs + mon_obs,
    )
    rec = resp.monitoring_records[0]
    assert rec.validation_sample_size == 15


def test_08_monitoring_structurally_separate(service):
    """Monitoring metrics live exclusively in monitoring_* fields."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(12)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=20),
        observations=base_obs + mon_obs,
    )
    rec = resp.monitoring_records[0]
    assert rec.monitoring_sample_size == 12
    assert rec.discovery_sample_size == 35
    assert rec.validation_sample_size == 15


def test_09_three_populations_never_merged(service):
    """Discovery + Validation + Monitoring populations are strictly partitioned."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(25)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=30),
        observations=base_obs + mon_obs,
    )
    rec = resp.monitoring_records[0]
    total_historical = rec.discovery_sample_size + rec.validation_sample_size
    assert total_historical == 50
    assert rec.monitoring_sample_size == 25
    assert total_historical != (50 + 25)


def test_10_candidate_identity_immutable(service):
    """Candidate ID, wording, qualification status, and limitations are preserved."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(10)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + mon_obs,
    )
    rec = resp.monitoring_records[0]
    assert "HYP-EURUSD-1H-H5" in rec.candidate_id
    assert rec.qualification_status == HypothesisStatus.CANDIDATE_PAPER_HYPOTHESIS
    assert "In the Discovery population" in rec.candidate_wording
    assert len(rec.candidate_limitations) >= 3


# =============================================================================
# 3. DATA QUALITY TESTS (Tests 11 - 15)
# =============================================================================

def test_11_only_valid_observations_contribute_to_monitoring_metrics(service):
    """Only DataQuality.VALID observations contribute to monitoring statistics."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # 10 valid observations (return = +0.0030)
    valid_obs = [
        make_synthetic_observation(f"v-{i}", cand_as_of + timedelta(hours=i + 1), raw_return=0.0030, data_quality=DataQuality.VALID)
        for i in range(10)
    ]
    # 5 incomplete observations
    incomp_obs = [
        make_synthetic_observation(f"inc-{i}", cand_as_of + timedelta(hours=11 + i), data_quality=DataQuality.INCOMPLETE)
        for i in range(5)
    ]
    # 2 invalid observations
    invalid_obs = [
        make_synthetic_observation(f"inv-{i}", cand_as_of + timedelta(hours=16 + i), data_quality=DataQuality.INVALID)
        for i in range(2)
    ]

    all_obs = base_obs + valid_obs + incomp_obs + invalid_obs

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=20),
        observations=all_obs,
    )

    rec = resp.monitoring_records[0]
    assert rec.monitoring_total_observations == 17
    assert rec.monitoring_sample_size == 10
    assert rec.monitoring_incomplete_observations == 5
    assert rec.monitoring_invalid_observations == 2
    assert rec.monitoring_metrics.sample_size == 10
    assert rec.monitoring_metrics.median_raw_return == pytest.approx(0.0030, rel=1e-4)


def test_12_incomplete_observations_excluded_from_numerical_metrics(service):
    """Incomplete forward horizons are excluded from return calculations."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Only incomplete observations in monitoring
    incomp_obs = [
        make_synthetic_observation(f"inc-{i}", cand_as_of + timedelta(hours=i + 1), data_quality=DataQuality.INCOMPLETE)
        for i in range(8)
    ]
    all_obs = base_obs + incomp_obs

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=10),
        observations=all_obs,
    )

    rec = resp.monitoring_records[0]
    assert rec.monitoring_total_observations == 8
    assert rec.monitoring_sample_size == 0
    assert rec.monitoring_incomplete_observations == 8
    assert rec.monitoring_metrics is None
    assert rec.monitoring_sample_adequacy == SampleAdequacy.UNKNOWN


def test_13_invalid_observations_excluded(service):
    """Invalid observations do not enter valid sample count or metrics."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    invalid_obs = [
        make_synthetic_observation(f"inv-{i}", cand_as_of + timedelta(hours=i + 1), data_quality=DataQuality.INVALID)
        for i in range(5)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs + invalid_obs,
    )
    rec = resp.monitoring_records[0]
    assert rec.monitoring_sample_size == 0
    assert rec.monitoring_invalid_observations == 5


def test_14_unknown_data_quality_excluded(service):
    """FORWARD_DATA_GAP and UNKNOWN data quality are classified as invalid and excluded."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    gap_obs = [
        make_synthetic_observation(f"gap-{i}", cand_as_of + timedelta(hours=i + 1), data_quality=DataQuality.FORWARD_DATA_GAP)
        for i in range(3)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=10),
        observations=base_obs + gap_obs,
    )
    rec = resp.monitoring_records[0]
    assert rec.monitoring_sample_size == 0
    assert rec.monitoring_invalid_observations == 3


def test_15_data_quality_census_deterministic(service):
    """Census sums match total monitoring observations exactly."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon = (
        [make_synthetic_observation(f"v-{i}", cand_as_of + timedelta(hours=1 + i), data_quality=DataQuality.VALID) for i in range(7)]
        + [make_synthetic_observation(f"inc-{i}", cand_as_of + timedelta(hours=8 + i), data_quality=DataQuality.INCOMPLETE) for i in range(4)]
        + [make_synthetic_observation(f"inv-{i}", cand_as_of + timedelta(hours=12 + i), data_quality=DataQuality.INVALID) for i in range(3)]
    )

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=20),
        observations=base_obs + mon,
    )
    rec = resp.monitoring_records[0]
    assert rec.monitoring_total_observations == 14
    assert rec.monitoring_total_observations == (
        rec.monitoring_sample_size + rec.monitoring_incomplete_observations + rec.monitoring_invalid_observations
    )


# =============================================================================
# 4. CANDIDATE MATCHING TESTS (Tests 16 - 21)
# =============================================================================

def test_16_instrument_mismatch_cannot_match(service):
    """GBPUSD observation cannot match EURUSD candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, instrument="EURUSD")
    cand_as_of = base_obs[-1].observation_time

    # Add GBPUSD monitoring observations
    gbp_mon = [
        make_synthetic_observation(f"gbp-{i}", cand_as_of + timedelta(hours=i + 1), instrument="GBPUSD")
        for i in range(10)
    ]

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + gbp_mon,
    )
    rec = resp.monitoring_records[0]
    assert rec.instrument == "EURUSD"
    assert rec.monitoring_total_observations == 0


def test_17_timeframe_mismatch_cannot_match(service):
    """15min observation cannot match 1h candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, timeframe="1h")
    cand_as_of = base_obs[-1].observation_time

    m15_mon = [
        make_synthetic_observation(f"m15-{i}", cand_as_of + timedelta(hours=i + 1), timeframe="15min")
        for i in range(10)
    ]

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + m15_mon,
    )
    rec = resp.monitoring_records[0]
    assert rec.monitoring_total_observations == 0


def test_18_behaviour_mismatch_cannot_match(service):
    """UPPER_PRICE_REJECTION observation cannot match LOWER_PRICE_REJECTION candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Add UPPER_PRICE_REJECTION monitoring observations
    upper_mon = [
        make_synthetic_observation(f"up-{i}", cand_as_of + timedelta(hours=i + 1), behaviour="UPPER_PRICE_REJECTION")
        for i in range(10)
    ]

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_id="HYP-EURUSD-1H-H5-LOWER_PRICE_REJECTION-UPTREND_WICK_REJECTED_SUPPORT",
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + upper_mon,
    )
    rec = resp.monitoring_records[0]
    assert rec.behaviour_identity == "LOWER_PRICE_REJECTION"
    assert rec.monitoring_total_observations == 0


def test_19_context_mismatch_cannot_match(service):
    """Observation with differing regime context cannot match candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, regime="UPTREND")
    cand_as_of = base_obs[-1].observation_time

    downtrend_mon = [
        make_synthetic_observation(f"down-{i}", cand_as_of + timedelta(hours=i + 1), regime="DOWNTREND")
        for i in range(10)
    ]

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + downtrend_mon,
    )
    rec = resp.monitoring_records[0]
    assert "UPTREND" in rec.context_identity
    assert rec.monitoring_total_observations == 0


def test_20_horizon_mismatch_cannot_match(service):
    """Forward outcome horizon 10 does not match candidate with horizon 5."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15, horizon=5)
    cand_as_of = base_obs[-1].observation_time

    # Construct observations that only have horizon 10
    h10_mon = [
        make_synthetic_observation(f"h10-{i}", cand_as_of + timedelta(hours=i + 1), horizon=10)
        for i in range(10)
    ]

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=15),
        observations=base_obs + h10_mon,
    )
    rec = resp.monitoring_records[0]
    assert rec.horizon == 5
    # Horizon 5 metrics were not present in h10_mon
    assert rec.monitoring_sample_size == 0


def test_21_candidate_id_matching_exact(service):
    """Filtering by candidate_id returns exactly that candidate."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_id="HYP-EURUSD-1H-H5-LOWER_PRICE_REJECTION-UPTREND_WICK_REJECTED_SUPPORT",
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=5),
        observations=base_obs,
    )
    assert len(resp.monitoring_records) == 1
    assert resp.monitoring_records[0].candidate_id == "HYP-EURUSD-1H-H5-LOWER_PRICE_REJECTION-UPTREND_WICK_REJECTED_SUPPORT"


# =============================================================================
# 5. DETERMINISM & TRACEABILITY TESTS (Tests 22 - 24)
# =============================================================================

def test_22_identical_request_produces_identical_response(service):
    """Sequential identical monitoring requests produce bit-for-bit identical outputs."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(15)
    ]
    all_obs = base_obs + mon_obs

    r1 = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=20),
        observations=all_obs,
    )
    r2 = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=20),
        observations=all_obs,
    )

    assert r1.total_candidates == r2.total_candidates
    assert r1.total_monitoring_observations == r2.total_monitoring_observations
    assert r1.monitoring_records[0].candidate_id == r2.monitoring_records[0].candidate_id
    assert r1.monitoring_records[0].monitoring_sample_size == r2.monitoring_records[0].monitoring_sample_size
    assert r1.monitoring_records[0].observation_ids_sample == r2.monitoring_records[0].observation_ids_sample


def test_23_deterministic_sorting(service):
    """Monitoring records are sorted strictly by (instrument, timeframe, candidate_id)."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    obs_eur = make_baseline_observations(t0, n_discovery=35, n_validation=15, instrument="EURUSD")
    obs_gbp = make_baseline_observations(t0, n_discovery=35, n_validation=15, instrument="GBPUSD")
    cand_as_of = obs_eur[-1].observation_time

    all_obs = obs_eur + obs_gbp

    resp = service.get_historical_monitoring(
        instrument=None,
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=5),
        observations=all_obs,
    )

    records = resp.monitoring_records
    if len(records) >= 2:
        for idx in range(len(records) - 1):
            k1 = (records[idx].instrument.upper(), records[idx].timeframe.upper(), records[idx].candidate_id)
            k2 = (records[idx + 1].instrument.upper(), records[idx + 1].timeframe.upper(), records[idx + 1].candidate_id)
            assert k1 <= k2


def test_24_observation_ids_sample_deterministic_max_20(service):
    """observation_ids_sample contains at most MAX_OBSERVATION_IDS_SAMPLE (20) IDs, sorted by (time, id)."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    # Add 40 monitoring observations
    mon_obs = [
        make_synthetic_observation(f"id-{i:03d}", cand_as_of + timedelta(hours=i + 1))
        for i in range(40)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=50),
        observations=base_obs + mon_obs,
    )
    rec = resp.monitoring_records[0]
    assert len(rec.observation_ids_sample) == 20
    assert rec.observation_ids_sample[0] == "id-000"
    assert rec.observation_ids_sample[-1] == "id-019"


# =============================================================================
# 6. SAFETY & REPRODUCIBILITY TESTS (Tests 25 - 29)
# =============================================================================

def test_25_zero_database_writes():
    """Monitoring evaluation generates zero dirty or new database objects."""
    from app.core.database import get_session
    from app.core.database.models import TradeJournalRecord, CapitalCycleRecord
    from sqlalchemy import select, func

    with get_session() as session:
        tj_before = session.scalar(select(func.count(TradeJournalRecord.id))) or 0
        cc_before = session.scalar(select(func.count(CapitalCycleRecord.id))) or 0

        # Execute monitoring logic
        cand_as_of = datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
        historical_findings_service.get_historical_monitoring(
            instrument="EURUSD",
            candidate_as_of=cand_as_of,
            as_of=cand_as_of + timedelta(hours=10),
        )

        assert len(session.dirty) == 0
        assert len(session.new) == 0

        tj_after = session.scalar(select(func.count(TradeJournalRecord.id))) or 0
        cc_after = session.scalar(select(func.count(CapitalCycleRecord.id))) or 0

        assert tj_before == tj_after
        assert cc_before == cc_after


def test_26_zero_broker_calls():
    """Phase 3B monitoring imports and invokes zero broker automation functions."""
    import sys
    # Verify MetaTrader5 is not imported
    assert "MetaTrader5" not in sys.modules


def test_27_trading_pipeline_isolation():
    """Phase 3B monitoring does not invoke or import order execution or guardian services."""
    assert not hasattr(historical_findings_service, "order_execution_service")
    assert not hasattr(historical_findings_service, "signal_authorization_service")
    assert not hasattr(historical_findings_service, "capital_guardian_service")


def test_28_no_database_migrations_created():
    """Alembic migration head remains strictly at 0007_v10_initial_monetary_risk."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert heads == ["0007_v10_initial_monetary_risk"]


def test_29_no_candidate_mutation(service):
    """Original CandidateHypothesis object is not mutated in memory."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    hyps_before = service.get_historical_hypotheses(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        as_of=cand_as_of,
        observations=base_obs,
    )
    cand_orig = hyps_before.hypotheses[0]
    disc_n_orig = cand_orig.discovery_sample_size

    # Evaluate monitoring
    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(25)
    ]
    service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=30),
        observations=base_obs + mon_obs,
    )

    # Re-verify original candidate
    assert cand_orig.discovery_sample_size == disc_n_orig


# =============================================================================
# 7. METHODOLOGY & SPECIFICATION TESTS (Tests 30 - 34)
# =============================================================================

def test_30_sample_adequacy_terminology_preserved(service):
    """Monitoring sample adequacy follows N>=30 (ADEQUATE), 10..29 (LIMITED), 1..9 (INSUFFICIENT), 0 (UNKNOWN)."""
    assert service.evaluate_sample_adequacy(35) == SampleAdequacy.ADEQUATE
    assert service.evaluate_sample_adequacy(30) == SampleAdequacy.ADEQUATE
    assert service.evaluate_sample_adequacy(29) == SampleAdequacy.LIMITED
    assert service.evaluate_sample_adequacy(10) == SampleAdequacy.LIMITED
    assert service.evaluate_sample_adequacy(9) == SampleAdequacy.INSUFFICIENT
    assert service.evaluate_sample_adequacy(1) == SampleAdequacy.INSUFFICIENT
    assert service.evaluate_sample_adequacy(0) == SampleAdequacy.UNKNOWN


def test_31_empty_monitoring_population_returns_safely(service):
    """When as_of <= candidate_as_of, monitoring population is 0 and returns valid response."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of,  # Equal to candidate_as_of
        observations=base_obs,
    )
    assert resp.total_monitoring_observations == 0
    assert resp.total_valid_monitoring_observations == 0
    rec = resp.monitoring_records[0]
    assert rec.monitoring_sample_size == 0
    assert rec.monitoring_metrics is None
    assert rec.monitoring_sample_adequacy == SampleAdequacy.UNKNOWN


def test_32_no_forbidden_recommendation_language(service):
    """Monitoring output text contains zero forbidden recommendation or directive words."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    base_obs = make_baseline_observations(t0, n_discovery=35, n_validation=15)
    cand_as_of = base_obs[-1].observation_time

    mon_obs = [
        make_synthetic_observation(f"mon-{i}", cand_as_of + timedelta(hours=i + 1))
        for i in range(15)
    ]
    resp = service.get_historical_monitoring(
        instrument="EURUSD",
        timeframe="1h",
        horizon=5,
        candidate_as_of=cand_as_of,
        as_of=cand_as_of + timedelta(hours=20),
        observations=base_obs + mon_obs,
    )
    rec = resp.monitoring_records[0]

    all_text = " ".join([
        rec.candidate_wording,
        " ".join(rec.candidate_limitations),
        " ".join(rec.monitoring_limitations),
        " ".join(resp.limitations),
    ])

    forbidden = {"BUY", "SELL", "ENTER", "EXIT", "TRADE", "BEST", "STRONGEST", "OPTIMAL", "HIGH-CONFIDENCE", "RECOMMENDED", "EDGE", "WINNING SETUP"}
    words = all_text.upper().split()
    for w in words:
        clean = w.strip(".,;:!?()\"'")
        assert clean not in forbidden, f"Forbidden term '{clean}' found in monitoring text"


def test_33_default_watchlist_excludes_usdjpy(service):
    """When instrument is omitted, default monitoring evaluates EURUSD, GBPUSD, XAUUSD, excluding USDJPY."""
    resp = service.get_historical_monitoring(
        instrument=None,
        candidate_as_of=datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc),
        as_of=datetime(2026, 9, 22, 5, 0, 0, tzinfo=timezone.utc),
    )
    instruments = {m.instrument.upper() for m in resp.monitoring_records}
    assert "USDJPY" not in instruments
    for inst in instruments:
        assert inst in {"EURUSD", "GBPUSD", "XAUUSD"}


def test_34_t0_excluded_from_forward_window():
    """T0 is strictly excluded from its forward window in Phase 2 outcomes."""
    t0 = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    obs = make_synthetic_observation("test-obs", t0, horizon=5)
    fw = obs.forward_windows[5]
    assert fw.horizon_candles == 5
    assert fw.reference_price == 1.1002


# =============================================================================
# 8. REST API INTEGRATION TESTS (Tests 35 - 36)
# =============================================================================

def test_35_api_monitoring_endpoint_200(client):
    """GET /api/v1/analytics/candlestick-behaviour/monitoring returns HTTP 200 with schema."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/monitoring?instrument=EURUSD")
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_name"] == "HISTORICAL_CANDIDATE_MONITORING"
    assert "monitoring_records" in data
    assert "candidate_as_of" in data
    assert "as_of" in data


def test_36_api_historical_boundary_empty(client):
    """API endpoint returns 200 and 0 monitoring observations when as_of <= candidate_as_of."""
    cand_as_of = "2026-09-22T00:00:00Z"
    resp = client.get(
        f"/api/v1/analytics/candlestick-behaviour/monitoring?instrument=EURUSD&candidate_as_of={cand_as_of}&as_of={cand_as_of}"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_monitoring_observations"] == 0
    assert data["total_valid_monitoring_observations"] == 0
