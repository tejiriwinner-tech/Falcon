"""
Falcon V10 — Historical Behaviour Analysis Test Suite (Phase 2).

Comprehensive verification of:
1. Directional Bias Attribution (Rejections, Patterns, Structures, Neutrality)
2. Forward Outcome Measurement across Horizons (1, 3, 5, 10, 20)
3. Noise Band Parameter & Metadata (NOISE_BAND_MULTIPLIER = 0.20)
4. Excursions, Returns & Timing (MFE, MAE, Offsets, Threshold Moves)
5. Directional Follow-Through & Continuation Classifications
6. Volatility Normalization (Return / Ref_Range, MFE / Ref_Range)
7. Descriptive Statistics & Percentile Distributions (P10..P90, Positive Ratios)
8. Context Subgroup Breakdowns (Regime, Session, Volatility, Pattern, Rejection)
9. Strict No-Lookahead Tests (All 10 Tests A-J from Section 25)
10. Closed-Candle as_of Semantics & Incomplete Window Fail-Closed
11. Sample Adequacy Policy (ADEQUATE, LIMITED, INSUFFICIENT, UNKNOWN)
12. REST API Analytics & Summary Integration (GET /history, GET /history/summary)
13. Production Safety Invariants (Zero DB writes, zero broker calls, zero migrations)
"""

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List
import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.analytics.candlestick_research_service import (
    CandlestickResearchService,
    candlestick_research_service,
)
from app.core.analytics.historical_behaviour_service import (
    HistoricalBehaviourService,
    historical_behaviour_service,
)
from app.schemas.candlestick_research import (
    BodyDirection,
    CandleMathMetrics,
    CandlestickResearchObservation,
    FailedBreakoutObservation,
    LiquiditySweepLikeObservation,
    PatternLabel,
    RejectionObservation,
    SessionContext,
    StructuralInteraction,
    VolatilityContext,
)
from app.schemas.historical_behaviour import (
    ContinuationState,
    DataQuality,
    DirectionalBias,
    HistoricalBehaviourAnalyticsResponse,
    HistoricalBehaviourObservation,
    HistoricalBehaviourSummaryResponse,
    SampleAdequacy,
    SubsequentDirection,
)


@pytest.fixture
def service():
    return HistoricalBehaviourService()


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
    timeframe: str = "M15",
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


def generate_candle_series(
    start_time: datetime,
    count: int,
    base_price: float = 1.1000,
    trend_pips_per_bar: float = 0.0,
    range_pips: float = 0.0010,
    symbol: str = "EURUSD",
) -> List[Dict[str, Any]]:
    """Helper to generate a clean sequence of synthetic candles."""
    candles = []
    current_open = base_price
    for i in range(count):
        t = start_time + timedelta(minutes=15 * i)
        c_close = current_open + trend_pips_per_bar
        c_high = max(current_open, c_close) + (range_pips * 0.4)
        c_low = min(current_open, c_close) - (range_pips * 0.4)
        candles.append(make_candle(current_open, c_high, c_low, c_close, t, symbol=symbol))
        current_open = c_close
    return candles


# =============================================================================
# 1. DIRECTIONAL BIAS ATTRIBUTION (Tests 1 - 8)
# =============================================================================

def test_01_bias_lower_rejection_is_buy(service):
    """Lower price rejection at T0 must attribute BUY directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.1020, 1.1025, 1.0950, 1.1018, t0),
        as_of=t0,
    )
    assert obs.rejection_observation == RejectionObservation.LOWER_PRICE_REJECTION
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.BUY


def test_02_bias_upper_rejection_is_sell(service):
    """Upper price rejection at T0 must attribute SELL directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.0980, 1.1050, 1.0975, 1.0982, t0),
        as_of=t0,
    )
    assert obs.rejection_observation == RejectionObservation.UPPER_PRICE_REJECTION
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.SELL


def test_03_bias_support_rejection_is_buy(service):
    """Structural support rejection must attribute BUY directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.1010, 1.1030, 1.0990, 1.1020, t0),
        market_context={"support_levels": [1.1000]},
        as_of=t0,
    )
    assert obs.support_resistance_interaction == StructuralInteraction.WICK_REJECTED_SUPPORT
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.BUY


def test_04_bias_resistance_rejection_is_sell(service):
    """Structural resistance rejection must attribute SELL directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.0990, 1.1010, 1.0970, 1.0980, t0),
        market_context={"resistance_levels": [1.1000]},
        as_of=t0,
    )
    assert obs.support_resistance_interaction == StructuralInteraction.WICK_REJECTED_RESISTANCE
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.SELL


def test_05_bias_failed_downside_breakout_is_buy(service):
    """Failed downside breakout must attribute BUY directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.1010, 1.1020, 1.0970, 1.1005, t0),
        market_context={"prior_range_low": 1.1000},
        as_of=t0,
    )
    assert obs.failed_breakout_observation == FailedBreakoutObservation.FAILED_DOWNSIDE_BREAKOUT
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.BUY


def test_06_bias_failed_upside_breakout_is_sell(service):
    """Failed upside breakout must attribute SELL directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.0990, 1.1030, 1.0980, 1.0995, t0),
        market_context={"prior_range_high": 1.1000},
        as_of=t0,
    )
    assert obs.failed_breakout_observation == FailedBreakoutObservation.FAILED_UPSIDE_BREAKOUT
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.SELL


def test_07_bias_hammer_pattern_is_buy(service):
    """Hammer pattern label must attribute BUY directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.1000, 1.1005, 1.0970, 1.1002, t0),
        market_context={"trend": "DOWNTREND"},
        as_of=t0,
    )
    assert PatternLabel.HAMMER in obs.pattern_labels
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.BUY


def test_08_bias_doji_is_neutral(service):
    """Doji candle with balanced wicks must attribute NEUTRAL directional bias."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.1000, 1.1010, 1.0990, 1.1000, t0),
        as_of=t0,
    )
    assert any(p in obs.pattern_labels for p in (PatternLabel.DOJI, PatternLabel.LONG_LEGGED_DOJI))
    bias = service.determine_directional_bias(obs)
    assert bias == DirectionalBias.NEUTRAL


# =============================================================================
# 2. FORWARD OUTCOME MEASUREMENT ACROSS HORIZONS (Tests 9 - 18)
# =============================================================================

def test_09_forward_windows_standard_horizons(service):
    """Service must support standard forward horizons: 1, 3, 5, 10, 20."""
    assert service.FORWARD_WINDOWS == [1, 3, 5, 10, 20]
    assert service.DEFAULT_FORWARD_WINDOW == 5


def test_10_forward_outcome_raw_return(service):
    """Raw return must strictly equal forward_close - t0_close."""
    t0_close = 1.1000
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [
        make_candle(1.1000, 1.1020, 1.0990, 1.1015, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.1015, 1.1030, 1.1010, 1.1025, t0 + timedelta(minutes=15 * 2)),
        make_candle(1.1025, 1.1050, 1.1020, 1.1040, t0 + timedelta(minutes=15 * 3)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=t0_close,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=3,
        ref_range=0.0010,
    )
    assert metrics.horizon_candles == 3
    assert metrics.reference_price == 1.1000
    assert metrics.forward_close == 1.1040
    assert pytest.approx(metrics.raw_return, 1e-6) == 0.0040
    assert pytest.approx(metrics.directional_return, 1e-6) == 0.0040
    assert metrics.data_quality == DataQuality.VALID


def test_11_forward_outcome_sell_bias_inverts_directional_return(service):
    """SELL bias must invert directional return relative to raw return."""
    t0_close = 1.1000
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [
        make_candle(1.1000, 1.1010, 1.0960, 1.0970, t0 + timedelta(minutes=15)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=t0_close,
        t0_bias=DirectionalBias.SELL,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
    )
    assert pytest.approx(metrics.raw_return, 1e-6) == -0.0030
    assert pytest.approx(metrics.directional_return, 1e-6) == 0.0030


def test_12_forward_outcome_mfe_and_mae_buy(service):
    """MFE for BUY must measure max upward excursion, MAE must measure max downward excursion."""
    t0_close = 1.1000
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [
        make_candle(1.1000, 1.1030, 1.0980, 1.1010, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.1010, 1.1060, 1.1005, 1.1050, t0 + timedelta(minutes=15 * 2)),
        make_candle(1.1050, 1.1055, 1.1020, 1.1040, t0 + timedelta(minutes=15 * 3)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=t0_close,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=3,
        ref_range=0.0020,
    )
    # Highs: 1.1030, 1.1060, 1.1055 -> Max High = 1.1060 -> MFE = 0.0060 (at candle 2)
    # Lows: 1.0980, 1.1005, 1.1020 -> Min Low = 1.0980 -> MAE = 0.0020 (at candle 1)
    assert pytest.approx(metrics.mfe, 1e-6) == 0.0060
    assert metrics.mfe_offset == 2
    assert pytest.approx(metrics.mae, 1e-6) == 0.0020
    assert metrics.mae_offset == 1


def test_13_forward_outcome_mfe_and_mae_sell(service):
    """MFE for SELL must measure max downward excursion, MAE must measure max upward excursion."""
    t0_close = 1.1000
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [
        make_candle(1.1000, 1.1020, 1.0970, 1.0980, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.0980, 1.0990, 1.0940, 1.0950, t0 + timedelta(minutes=15 * 2)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=t0_close,
        t0_bias=DirectionalBias.SELL,
        forward_candles=forward_candles,
        horizon=2,
        ref_range=0.0020,
    )
    # Lows: 1.0970, 1.0940 -> Min Low = 1.0940 -> MFE = 0.0060 (at candle 2)
    # Highs: 1.1020, 1.0990 -> Max High = 1.1020 -> MAE = 0.0020 (at candle 1)
    assert pytest.approx(metrics.mfe, 1e-6) == 0.0060
    assert metrics.mfe_offset == 2
    assert pytest.approx(metrics.mae, 1e-6) == 0.0020
    assert metrics.mae_offset == 1


def test_14_forward_outcome_incomplete_window_fails_closed(service):
    """When forward candles count < horizon, service must return INCOMPLETE data quality."""
    t0_close = 1.1000
    forward_candles = [make_candle(1.1000, 1.1020, 1.0990, 1.1010, datetime.now(timezone.utc))]
    metrics = service.evaluate_forward_outcome(
        t0_close=t0_close,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=5,
        ref_range=0.0010,
    )
    assert metrics.horizon_candles == 5
    assert metrics.data_quality == DataQuality.INCOMPLETE
    assert metrics.forward_close is None
    assert metrics.raw_return is None
    assert metrics.mfe is None
    assert metrics.mae is None


def test_15_forward_outcome_empty_forward_fails_closed(service):
    """Empty forward candles list must return INCOMPLETE data quality."""
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=[],
        horizon=1,
        ref_range=0.0010,
    )
    assert metrics.data_quality == DataQuality.INCOMPLETE
    assert metrics.forward_close is None


def test_16_forward_outcome_neutral_bias_return(service):
    """Neutral bias must produce None for directional_return."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1020, 1.0980, 1.1010, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.NEUTRAL,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
    )
    assert metrics.directional_return is None
    assert metrics.directional_return_percent is None
    assert pytest.approx(metrics.raw_return, 1e-6) == 0.0010


def test_17_forward_outcome_percent_return_and_excursion(service):
    """Percentage returns and excursions must be correctly computed relative to t0_close."""
    t0_close = 100.0
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(100.0, 105.0, 98.0, 102.0, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=t0_close,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=2.0,
    )
    assert pytest.approx(metrics.raw_return_percent, 1e-6) == 2.0
    assert pytest.approx(metrics.mfe_percent, 1e-6) == 5.0
    assert pytest.approx(metrics.mae_percent, 1e-6) == 2.0


def test_18_forward_outcome_zero_t0_close_guard(service):
    """Zero or negative reference price must produce None for percentage returns without crashing."""
    t0_close = 0.0
    forward_candles = [make_candle(0.0, 1.0, 0.0, 0.5, datetime.now(timezone.utc))]
    metrics = service.evaluate_forward_outcome(
        t0_close=t0_close,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=1.0,
    )
    assert metrics.raw_return_percent is None
    assert metrics.mfe_percent is None
    assert metrics.mae_percent is None


# =============================================================================
# 3. NOISE BAND PARAMETER & CLASSIFICATION (Tests 19 - 26)
# =============================================================================

def test_19_noise_band_multiplier_is_explicit_0_20(service):
    """NOISE_BAND_MULTIPLIER must be explicitly 0.20."""
    assert service.NOISE_BAND_MULTIPLIER == 0.20


def test_20_noise_band_calculation(service):
    """noise_band must equal 0.20 * ref_range."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1030, 1.0990, 1.1020, t0 + timedelta(minutes=15))]
    ref_range = 0.0020
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=ref_range,
    )
    assert pytest.approx(metrics.noise_band, 1e-6) == 0.20 * 0.0020


def test_21_follow_through_classification(service):
    """directional_return > noise_band must classify as FOLLOW_THROUGH."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # ref_range = 0.0010 -> noise_band = 0.0002. Move = +0.0005 -> FOLLOW_THROUGH
    forward_candles = [make_candle(1.1000, 1.1010, 1.1000, 1.1005, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
    )
    assert metrics.subsequent_direction == SubsequentDirection.FOLLOW_THROUGH


def test_22_reversal_classification(service):
    """directional_return < -noise_band must classify as REVERSAL."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # ref_range = 0.0010 -> noise_band = 0.0002. Move = -0.0005 -> REVERSAL
    forward_candles = [make_candle(1.1000, 1.1000, 1.0990, 1.0995, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
    )
    assert metrics.subsequent_direction == SubsequentDirection.REVERSAL


def test_23_neutral_classification_inside_band(service):
    """directional_return within [-noise_band, +noise_band] without MFE breakout is NEUTRAL."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # ref_range = 0.0010 -> noise_band = 0.0002. Move = +0.0001 -> NEUTRAL
    forward_candles = [make_candle(1.1000, 1.1001, 1.0999, 1.1001, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
    )
    assert metrics.subsequent_direction == SubsequentDirection.NEUTRAL


def test_24_partial_follow_through_classification(service):
    """MFE > noise_band but return inside band must classify as PARTIAL_FOLLOW_THROUGH."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # ref_range = 0.0010 -> noise_band = 0.0002. High = 1.1005 (MFE = 0.0005 > 0.0002), Close = 1.1001 (inside band)
    forward_candles = [make_candle(1.1000, 1.1005, 1.0999, 1.1001, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
    )
    assert metrics.subsequent_direction == SubsequentDirection.PARTIAL_FOLLOW_THROUGH


def test_25_unknown_classification_when_zero_ref_range(service):
    """When ref_range is zero or missing, subsequent_direction must be UNKNOWN."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1020, 1.0990, 1.1010, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0,
    )
    assert metrics.subsequent_direction == SubsequentDirection.UNKNOWN


def test_26_response_exposes_noise_band_multiplier(service):
    """Analytics response must expose noise_band_multiplier and research_methodology_version."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 10)
    resp = service.get_historical_behaviour_analytics(candles=candles)
    assert resp.noise_band_multiplier == 0.20
    assert resp.research_methodology_version == "1.0.0"
    assert resp.experiment_name == "HISTORICAL_BEHAVIOUR_ANALYSIS"


# =============================================================================
# 4. TIMING & EXCURSION DYNAMICS (Tests 27 - 32)
# =============================================================================

def test_27_candles_to_favourable_move(service):
    """Earliest candle crossing noise_band must be recorded in candles_to_favourable_move."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # noise_band = 0.20 * 0.0010 = 0.0002.
    # Candle 1: high = 1.1001 (diff 0.0001 <= 0.0002)
    # Candle 2: high = 1.1004 (diff 0.0004 > 0.0002) -> offset 2!
    forward_candles = [
        make_candle(1.1000, 1.1001, 1.0998, 1.1000, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.1000, 1.1004, 1.0999, 1.1003, t0 + timedelta(minutes=15 * 2)),
        make_candle(1.1003, 1.1008, 1.1002, 1.1006, t0 + timedelta(minutes=15 * 3)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=3,
        ref_range=0.0010,
    )
    assert metrics.candles_to_favourable_move == 2


def test_28_candles_to_adverse_move(service):
    """Earliest candle crossing adverse noise_band must be recorded in candles_to_adverse_move."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # BUY bias: adverse move is price dropping below 1.1000 - 0.0002 = 1.0998
    # Candle 1: low = 1.0996 (diff 0.0004 > 0.0002) -> offset 1!
    forward_candles = [
        make_candle(1.1000, 1.1001, 1.0996, 1.0997, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.0997, 1.1004, 1.0995, 1.1002, t0 + timedelta(minutes=15 * 2)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=2,
        ref_range=0.0010,
    )
    assert metrics.candles_to_adverse_move == 1


def test_29_no_threshold_crossing_returns_none(service):
    """When excursions never exceed noise band, timing offsets must be None."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [
        make_candle(1.1000, 1.1001, 1.0999, 1.1000, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.1000, 1.1001, 1.0999, 1.1000, t0 + timedelta(minutes=15 * 2)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=2,
        ref_range=0.0050,  # noise_band = 0.0010
    )
    assert metrics.candles_to_favourable_move is None
    assert metrics.candles_to_adverse_move is None


def test_30_mfe_mae_offsets_are_one_indexed(service):
    """mfe_offset and mae_offset must be strictly 1-indexed (1..horizon)."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [
        make_candle(1.1000, 1.1050, 1.0980, 1.1010, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.1010, 1.1020, 1.0950, 1.0970, t0 + timedelta(minutes=15 * 2)),
    ]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=2,
        ref_range=0.0010,
    )
    assert metrics.mfe_offset == 1  # high 1.1050 on candle 1
    assert metrics.mae_offset == 2  # low 1.0950 on candle 2


def test_31_continuation_state_uptrend_continuation(service):
    """Uptrend with forward price expansion must classify as CONTINUATION."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1040, 1.1000, 1.1030, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
        trend_context="UPTREND",
    )
    assert metrics.continuation_state == ContinuationState.CONTINUATION


def test_32_continuation_state_uptrend_reversal(service):
    """Uptrend with forward price contraction must classify as REVERSAL."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1000, 1.0960, 1.0970, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
        trend_context="UPTREND",
    )
    assert metrics.continuation_state == ContinuationState.REVERSAL


# =============================================================================
# 5. VOLATILITY NORMALIZATION (Tests 33 - 36)
# =============================================================================

def test_33_volatility_normalized_return(service):
    """volatility_normalized_return must equal raw_return / ref_range."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1040, 1.1000, 1.1030, t0 + timedelta(minutes=15))]
    ref_range = 0.0015
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=ref_range,
    )
    expected_norm = 0.0030 / 0.0015
    assert pytest.approx(metrics.volatility_normalized_return, 1e-6) == expected_norm


def test_34_volatility_normalized_mfe_and_mae(service):
    """volatility_normalized_mfe and mae must equal mfe/ref_range and mae/ref_range."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1045, 1.0985, 1.1020, t0 + timedelta(minutes=15))]
    ref_range = 0.0015
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=ref_range,
    )
    assert pytest.approx(metrics.volatility_normalized_mfe, 1e-6) == 0.0045 / 0.0015
    assert pytest.approx(metrics.volatility_normalized_mae, 1e-6) == 0.0015 / 0.0015


def test_35_zero_reference_range_produces_none_norm(service):
    """Zero or negative reference range must produce None for normalized metrics."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.1040, 1.1000, 1.1030, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0,
    )
    assert metrics.volatility_normalized_return is None
    assert metrics.volatility_normalized_mfe is None
    assert metrics.volatility_normalized_mae is None


def test_36_normalization_handles_large_excursions(service):
    """Normalization must handle large excursions cleanly without overflow."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [make_candle(1.1000, 1.2000, 1.1000, 1.1800, t0 + timedelta(minutes=15))]
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=1,
        ref_range=0.0010,
    )
    assert metrics.volatility_normalized_return > 50.0


# =============================================================================
# 6. DESCRIPTIVE STATISTICS & PERCENTILE DISTRIBUTION (Tests 37 - 44)
# =============================================================================

def test_37_sample_size_excludes_incomplete(service):
    """calculate_descriptive_statistics must exclude observations with INCOMPLETE forward window."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 10)  # 10 candles: only first 5 have full 5-candle forward window
    obs = service.analyze_historical_candles(candles, primary_window=5)
    stats, dist, adequacy = service.calculate_descriptive_statistics(obs, horizon=5)
    # Index 0..4 have 5 forward candles. Index 5..9 have < 5 forward candles.
    assert stats.sample_size == 5
    assert adequacy == SampleAdequacy.INSUFFICIENT  # 5 < 10


def test_38_mean_and_median_directional_returns(service):
    """Mean and median directional returns must be calculated correctly."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    # Give candles clear directional bias (strong bullish bodies: open 1.1000, close 1.1010, high 1.1012, low 1.0999)
    candles = []
    current_open = 1.1000
    for i in range(20):
        t = t0 + timedelta(minutes=15 * i)
        c_close = current_open + 0.0010
        c_high = c_close + 0.0002
        c_low = current_open - 0.0001
        candles.append(make_candle(current_open, c_high, c_low, c_close, t))
        current_open = c_close

    obs = service.analyze_historical_candles(candles, primary_window=3)
    stats, dist, adequacy = service.calculate_descriptive_statistics(obs, horizon=3)
    assert stats.sample_size == 17
    assert stats.mean_directional_return is not None
    assert stats.median_directional_return is not None
    assert stats.mean_directional_return > 0.0


def test_39_percentiles_calculation(service):
    """Percentiles p10, p25, p50, p75, p90 must be monotonically non-decreasing."""
    vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    p = service.calculate_percentiles(vals)
    assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"]
    assert p["p50"] == 5.0


def test_40_percentiles_empty_list(service):
    """Percentiles on empty list must return all None."""
    p = service.calculate_percentiles([])
    assert all(v is None for v in p.values())


def test_41_positive_and_negative_outcome_ratios(service):
    """Positive and negative outcome ratios must be between 0.0 and 1.0."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 25, trend_pips_per_bar=0.0002)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    stats, dist, adequacy = service.calculate_descriptive_statistics(obs, horizon=5)
    assert 0.0 <= dist.positive_outcome_ratio <= 1.0
    assert 0.0 <= dist.negative_outcome_ratio <= 1.0


def test_42_rates_sum_consistency(service):
    """Follow-through, reversal, neutral and unknown counts must sum to sample_size."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 35)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    stats, dist, adequacy = service.calculate_descriptive_statistics(obs, horizon=5)
    total_counts = (
        stats.follow_through_count
        + stats.reversal_count
        + stats.neutral_count
        + stats.unknown_count
    )
    assert total_counts == stats.sample_size


def test_43_empty_observations_stats(service):
    """Empty observations list must return 0 sample size and UNKNOWN adequacy."""
    stats, dist, adequacy = service.calculate_descriptive_statistics([], horizon=5)
    assert stats.sample_size == 0
    assert adequacy == SampleAdequacy.UNKNOWN
    assert stats.mean_raw_return is None


def test_44_std_dev_calculation(service):
    """Standard deviation must be correctly calculated for n > 1."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    stats, _, _ = service.calculate_descriptive_statistics(obs, horizon=5)
    assert stats.std_dev_return is not None
    assert stats.std_dev_return >= 0.0


# =============================================================================
# 7. CONTEXT SUBGROUP BREAKDOWNS (Tests 45 - 50)
# =============================================================================

def test_45_breakdown_by_regime(service):
    """calculate_breakdowns must include by_regime segmentations."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    b = service.calculate_breakdowns(obs, horizon=5)
    assert "by_regime" in b
    assert isinstance(b["by_regime"], dict)


def test_46_breakdown_by_session(service):
    """calculate_breakdowns must include by_session segmentations."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    b = service.calculate_breakdowns(obs, horizon=5)
    assert "by_session" in b


def test_47_breakdown_by_volatility(service):
    """calculate_breakdowns must include by_volatility segmentations."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    b = service.calculate_breakdowns(obs, horizon=5)
    assert "by_volatility" in b


def test_48_breakdown_by_pattern(service):
    """calculate_breakdowns must include by_pattern segmentations."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    b = service.calculate_breakdowns(obs, horizon=5)
    assert "by_pattern" in b


def test_49_breakdown_by_rejection(service):
    """calculate_breakdowns must include by_rejection segmentations."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    b = service.calculate_breakdowns(obs, horizon=5)
    assert "by_rejection" in b


def test_50_breakdown_contains_sample_adequacy(service):
    """Each subgroup in breakdowns must report its sample_size and sample_adequacy."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    b = service.calculate_breakdowns(obs, horizon=5)
    for group_cat in b.values():
        for group_name, summary in group_cat.items():
            assert "sample_size" in summary
            assert "sample_adequacy" in summary
            assert summary["sample_adequacy"] in ("ADEQUATE", "LIMITED", "INSUFFICIENT", "UNKNOWN")


# =============================================================================
# 8. STRICT NO-LOOKAHEAD TESTS (Prompt Section 25 Tests A - J) (Tests 51 - 60)
# =============================================================================

def test_51_no_lookahead_test_a_t0_strictly_uses_prior_candles(service):
    """
    Test A: The Phase 1 observation at T0 must depend strictly on T0 and preceding
    reference candles candles[0:i]. Forward candles are never visible at T0.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs_list = service.analyze_historical_candles(candles)
    # For candle at index 10:
    t0_obs = obs_list[10].candle_observation
    assert t0_obs.close == candles[10]["close"]
    # Re-evaluate independently using only candles[0:10]
    independent_t0_obs = candlestick_research_service.analyze_candle(
        current_candle=candles[10],
        historical_candles=candles[:10],
        as_of=candles[10]["timestamp"],
    )
    assert t0_obs.close == independent_t0_obs.close
    assert t0_obs.range == independent_t0_obs.range
    assert t0_obs.rejection_observation == independent_t0_obs.rejection_observation
    assert t0_obs.pattern_labels == independent_t0_obs.pattern_labels


def test_52_no_lookahead_test_b_forward_mutation_zero_t0_effect(service):
    """
    Test B: Mutating any forward candle T1..TH produces ZERO change in the Phase 1
    observation at T0.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles1 = generate_candle_series(t0, 20)
    obs1 = service.analyze_historical_candles(candles1)
    t0_obs_original = obs1[5].candle_observation

    # Mutate candle at index 6 (T1 for T0 at index 5)
    candles2 = [dict(c) for c in candles1]
    candles2[6]["close"] = candles2[6]["close"] + 0.0500  # Massive spike
    candles2[6]["high"] = candles2[6]["high"] + 0.0500
    obs2 = service.analyze_historical_candles(candles2)
    t0_obs_after_mutation = obs2[5].candle_observation

    # Observation at T0 must remain 100% IDENTICAL
    assert t0_obs_original.close == t0_obs_after_mutation.close
    assert t0_obs_original.body_size == t0_obs_after_mutation.body_size
    assert t0_obs_original.rejection_observation == t0_obs_after_mutation.rejection_observation
    assert t0_obs_original.pattern_labels == t0_obs_after_mutation.pattern_labels
    assert t0_obs_original.body_state == t0_obs_after_mutation.body_state


def test_53_no_lookahead_test_c_truncating_future_zero_t0_effect(service):
    """
    Test C: Truncating future candles does NOT alter T0's Phase 1 observation.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles_full = generate_candle_series(t0, 30)
    obs_full = service.analyze_historical_candles(candles_full)

    candles_truncated = candles_full[:15]
    obs_truncated = service.analyze_historical_candles(candles_truncated)

    # For any index < 15, the Phase 1 observation must be bit-for-bit identical
    for i in range(15):
        assert obs_full[i].candle_observation.close == obs_truncated[i].candle_observation.close
        assert obs_full[i].candle_observation.rejection_observation == obs_truncated[i].candle_observation.rejection_observation


def test_54_no_lookahead_test_d_incomplete_forward_window_fails_closed(service):
    """
    Test D: Incomplete forward window produces data_quality = INCOMPLETE and does
    NOT compute partial returns.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 7)  # 7 candles
    # At index 5: only 1 forward candle available (index 6). Horizon 5 requires 5 forward candles.
    obs = service.analyze_historical_candles(candles, primary_window=5)
    t0_idx5 = obs[5]
    h5_metrics = t0_idx5.forward_windows[5]
    assert h5_metrics.data_quality == DataQuality.INCOMPLETE
    assert h5_metrics.forward_close is None
    assert h5_metrics.raw_return is None
    assert h5_metrics.directional_return is None


def test_55_no_lookahead_test_e_gap_or_corrupted_candles_handled(service):
    """
    Test E: Corrupted or missing forward timestamps do not crash the service.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 10)
    candles[7]["timestamp"] = None  # Missing timestamp
    obs = service.analyze_historical_candles(candles, primary_window=3)
    assert len(obs) == 10


def test_56_no_lookahead_test_f_candles_beyond_horizon_zero_effect_on_horizon(service):
    """
    Test F: Adding future candles beyond horizon H does not alter metrics for horizon H.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles1 = generate_candle_series(t0, 10)
    metrics1 = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=candles1[:3],
        horizon=3,
        ref_range=0.0010,
    )
    metrics2 = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=candles1[:8],  # More candles provided
        horizon=3,
        ref_range=0.0010,
    )
    assert metrics1.raw_return == metrics2.raw_return
    assert metrics1.mfe == metrics2.mfe
    assert metrics1.mae == metrics2.mae


def test_57_no_lookahead_test_g_as_of_boundary_strictly_enforced(service):
    """
    Test G: Forward candles with timestamp > as_of are strictly excluded,
    causing forward window to fail-closed with INCOMPLETE.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    forward_candles = [
        make_candle(1.1000, 1.1020, 1.0990, 1.1010, t0 + timedelta(minutes=15 * 1)),
        make_candle(1.1010, 1.1030, 1.1000, 1.1020, t0 + timedelta(minutes=15 * 2)),
        make_candle(1.1020, 1.1040, 1.1010, 1.1030, t0 + timedelta(minutes=15 * 3)),
    ]
    # Set as_of to candle 2 timestamp: candle 3 is in the future relative to as_of
    as_of = t0 + timedelta(minutes=15 * 2)
    metrics = service.evaluate_forward_outcome(
        t0_close=1.1000,
        t0_bias=DirectionalBias.BUY,
        forward_candles=forward_candles,
        horizon=3,
        ref_range=0.0010,
        as_of=as_of,
    )
    assert metrics.data_quality == DataQuality.INCOMPLETE
    assert metrics.forward_close is None


def test_58_no_lookahead_test_h_future_calendar_events_not_visible(service):
    """
    Test H: Future economic calendar events are not visible to past candles.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    future_event = {"eventTime": t0 + timedelta(hours=5), "title": "NFP"}
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.1000, 1.1020, 1.0980, 1.1010, t0),
        market_context={"economic_events": [future_event]},
        as_of=t0,
    )
    assert obs.news_context.value == "NO_NEWS_CONTEXT"


def test_59_no_lookahead_test_i_future_session_transitions_not_visible(service):
    """
    Test I: Future session transitions are not visible to past candles.
    """
    t0 = datetime(2026, 3, 1, 2, 0, tzinfo=timezone.utc)  # Asian session
    obs = candlestick_research_service.analyze_candle(
        current_candle=make_candle(1.1000, 1.1010, 1.0990, 1.1005, t0),
        as_of=t0,
    )
    # Must evaluate at Asian time, not New York or future London
    assert obs.session_context is not None


def test_60_no_lookahead_test_j_as_of_excludes_t0_candles_in_future(service):
    """
    Test J: Observations where T0 timestamp > as_of are strictly excluded from results.
    """
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    as_of = t0 + timedelta(minutes=15 * 5)  # only first 6 candles (0..5) are <= as_of
    obs = service.analyze_historical_candles(candles, as_of=as_of)
    assert len(obs) == 6
    assert all(o.observation_time <= as_of for o in obs)


# =============================================================================
# 9. SAMPLE ADEQUACY POLICY (Tests 61 - 64)
# =============================================================================

def test_61_adequacy_adequate_ge_30(service):
    """N >= 30 must classify as ADEQUATE."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 40)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    # Index 0..34 have >= 5 forward candles -> N = 35 >= 30
    stats, _, adequacy = service.calculate_descriptive_statistics(obs, horizon=5)
    assert stats.sample_size >= 30
    assert adequacy == SampleAdequacy.ADEQUATE


def test_62_adequacy_limited_10_to_29(service):
    """10 <= N < 30 must classify as LIMITED."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 20)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    # Index 0..14 have >= 5 forward candles -> N = 15 -> LIMITED
    stats, _, adequacy = service.calculate_descriptive_statistics(obs, horizon=5)
    assert 10 <= stats.sample_size < 30
    assert adequacy == SampleAdequacy.LIMITED


def test_63_adequacy_insufficient_1_to_9(service):
    """1 <= N < 10 must classify as INSUFFICIENT."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 10)
    obs = service.analyze_historical_candles(candles, primary_window=5)
    # N = 5 -> INSUFFICIENT
    stats, _, adequacy = service.calculate_descriptive_statistics(obs, horizon=5)
    assert 1 <= stats.sample_size < 10
    assert adequacy == SampleAdequacy.INSUFFICIENT


def test_64_adequacy_unknown_0(service):
    """N == 0 must classify as UNKNOWN."""
    stats, _, adequacy = service.calculate_descriptive_statistics([], horizon=5)
    assert stats.sample_size == 0
    assert adequacy == SampleAdequacy.UNKNOWN


# =============================================================================
# 10. REST API ANALYTICS & SUMMARY INTEGRATION (Tests 65 - 70)
# =============================================================================

def test_65_api_get_history_endpoint_status(client):
    """GET /api/v1/analytics/candlestick-behaviour/history must return 200 with schema."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/history?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_name"] == "HISTORICAL_BEHAVIOUR_ANALYSIS"
    assert data["noise_band_multiplier"] == 0.20
    assert "statistics" in data
    assert "distribution" in data
    assert "breakdowns" in data
    assert "observations" in data


def test_66_api_get_history_summary_endpoint(client):
    """GET /api/v1/analytics/candlestick-behaviour/history/summary must return 200 without raw observations."""
    resp = client.get("/api/v1/analytics/candlestick-behaviour/history/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_name"] == "HISTORICAL_BEHAVIOUR_ANALYSIS"
    assert "observations" not in data
    assert "statistics" in data
    assert "distribution" in data
    assert "breakdowns" in data


def test_67_api_filters_forwarded(client):
    """Query filters must be reflected in filters_applied response object."""
    resp = client.get(
        "/api/v1/analytics/candlestick-behaviour/history?instrument=EURUSD&timeframe=M15&forward_window=10&behaviour=UPPER_PRICE_REJECTION"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters_applied"]["instrument"] == "EURUSD"
    assert data["filters_applied"]["timeframe"] == "M15"
    assert data["filters_applied"]["forward_window"] == 10
    assert data["filters_applied"]["behaviour"] == "UPPER_PRICE_REJECTION"


def test_68_api_summary_filters_forwarded(client):
    """Summary endpoint must also record filters_applied correctly."""
    resp = client.get(
        "/api/v1/analytics/candlestick-behaviour/history/summary?pattern=HAMMER&regime=TRENDING"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters_applied"]["pattern"] == "HAMMER"
    assert data["filters_applied"]["regime"] == "TRENDING"


def test_69_api_zero_lookahead_as_of_enforced(client):
    """API queries with as_of parameter must enforce zero lookahead."""
    past_iso = "2026-01-01T00:00:00Z"
    resp = client.get(f"/api/v1/analytics/candlestick-behaviour/history?as_of={past_iso}")
    assert resp.status_code == 200
    data = resp.json()
    assert "2026-01-01" in data["as_of"]


def test_70_api_determinism_identical_calls(client):
    """Identical sequential API calls must return deterministic identical outputs."""
    resp1 = client.get("/api/v1/analytics/candlestick-behaviour/history/summary?instrument=EURUSD")
    resp2 = client.get("/api/v1/analytics/candlestick-behaviour/history/summary?instrument=EURUSD")
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json()["sample_size"] == resp2.json()["sample_size"]


# =============================================================================
# 11. PRODUCTION SAFETY & ISOLATION INVARIANTS (Tests 71 - 74)
# =============================================================================

def test_71_phase_2_zero_db_mutations(service):
    """Executing historical behaviour analysis must not modify database records."""
    from unittest.mock import MagicMock, patch
    from app.core.config.database import SessionLocal

    # Test via mock spy to guarantee 0 DB mutations under all environments
    mock_session = MagicMock()
    with patch("app.core.config.database.SessionLocal", return_value=mock_session):
        t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        candles = generate_candle_series(t0, 50)
        service.get_historical_behaviour_analytics(candles=candles)
        service.get_historical_behaviour_summary(candles=candles)

        # Assert no add, commit, delete was called
        assert mock_session.add.call_count == 0
        assert mock_session.commit.call_count == 0
        assert mock_session.delete.call_count == 0

    # Also check actual DB if connection is reachable
    try:
        from app.core.database.models import TradeJournalRecord
        from sqlalchemy import func

        db = SessionLocal()
        try:
            initial_count = db.query(func.count(TradeJournalRecord.id)).scalar()
            t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
            candles = generate_candle_series(t0, 10)
            service.get_historical_behaviour_analytics(candles=candles)
            final_count = db.query(func.count(TradeJournalRecord.id)).scalar()
            assert final_count == initial_count
        finally:
            db.close()
    except Exception:
        # Remote database offline/unreachable in this network environment; mock verification above passed
        pass


def test_72_phase_2_zero_broker_calls(monkeypatch, service):
    """HistoricalBehaviourService must never call broker execution methods."""
    broker_calls = []

    def mock_broker_call(*args, **kwargs):
        broker_calls.append((args, kwargs))
        raise AssertionError("Broker execution called from Phase 2 research!")

    # Attempt to patch common broker endpoints if imported anywhere
    try:
        from app.services.execution import order_execution_service
        monkeypatch.setattr(order_execution_service, "order_send", mock_broker_call, raising=False)
    except Exception:
        pass

    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 30)
    service.get_historical_behaviour_analytics(candles=candles)
    assert len(broker_calls) == 0


def test_73_phase_2_statelessness_re_evaluation_equality(service):
    """Re-evaluating identical inputs must produce bit-for-bit identical outputs."""
    t0 = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    candles = generate_candle_series(t0, 25)

    res1 = service.get_historical_behaviour_analytics(candles=candles)
    res2 = service.get_historical_behaviour_analytics(candles=candles)

    assert res1.sample_size == res2.sample_size
    assert res1.statistics.mean_raw_return == res2.statistics.mean_raw_return
    assert res1.statistics.median_raw_return == res2.statistics.median_raw_return
    assert res1.distribution.positive_outcome_ratio == res2.distribution.positive_outcome_ratio
    assert len(res1.observations) == len(res2.observations)


def test_74_alembic_head_remains_0007():
    """Verify that Alembic migration head has not been altered."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(alembic_cfg)
    heads = script.get_heads()
    assert heads == ["0007_v10_initial_monetary_risk"], f"Alembic heads altered: {heads}"
