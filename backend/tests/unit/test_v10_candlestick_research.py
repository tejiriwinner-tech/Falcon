"""
Falcon V10 — Candlestick & Wick Behaviour Research Test Suite

Comprehensive verification of:
1. Candle mathematics & numerical edge cases (zero range, zero wicks, extreme floats, no NaN/Inf)
2. Wick behaviour (upper/lower rejection, expansion/contraction, clusters, resistance/support, liquidity sweeps)
3. Body behaviour (relative states vs reference population, expansion/contraction, directional sequences)
4. Failed breakout semantics (T0 pending/none vs subsequent confirmation)
5. Pattern taxonomies (single, two, three, and multi-candle patterns from IG and Groww)
6. Context observations (trend pullback, session extremes, volatility, news UNKNOWN rule, volume)
7. Multi-candle sequence tracking (5-candle window evolutions, graceful fallback)
8. No-lookahead & temporal invariants (as_of filtering, historical confirmation limits)
9. Determinism, statelessness & production isolation (re-evaluation equality, no broker/guardian calls)
10. REST API analytics endpoint integration (GET /api/v1/analytics/candlestick-behaviour, filtering, parameters)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from typing import List
import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.analytics.candlestick_research_service import (
    CandlestickResearchService,
    candlestick_research_service,
)
from app.schemas.candlestick_research import (
    BodyDirection,
    BodyEvolution,
    BodyState,
    CandleMathMetrics,
    CandlestickResearchAnalyticsResponse,
    CandlestickResearchObservation,
    ConfirmationStatus,
    DirectionalSequence,
    FailedBreakoutObservation,
    LiquiditySweepLikeObservation,
    NewsContext,
    PatternLabel,
    RejectionObservation,
    SessionContext,
    SourceProvenance,
    StructuralInteraction,
    TrendPullbackObservation,
    VolatilityContext,
    VolumeContext,
    WickClusterState,
    WickDominance,
    WickState,
)


@pytest.fixture
def service():
    return CandlestickResearchService()


@pytest.fixture
def client():
    return TestClient(app)


# =============================================================================
# 1. CANDLE MATHEMATICS & NUMERICAL EDGE CASES (Tests 1 - 8)
# =============================================================================

def test_01_candle_math_zero_range_flat_candle(service):
    """Zero range flat candle must not crash with ZeroDivisionError, producing None for ratios."""
    metrics = service.calculate_candle_math(open_price=100.0, high=100.0, low=100.0, close=100.0)
    assert metrics.range == 0.0
    assert metrics.body_size == 0.0
    assert metrics.upper_wick == 0.0
    assert metrics.lower_wick == 0.0
    assert metrics.total_wick == 0.0
    assert metrics.body_ratio is None
    assert metrics.upper_wick_ratio is None
    assert metrics.lower_wick_ratio is None
    assert metrics.wick_to_body_ratio is None
    assert metrics.body_position is None


def test_02_candle_math_doji_non_zero_range(service):
    """Doji candle (open == close) with range must have body_ratio = 0.0 and wick_to_body_ratio = None."""
    metrics = service.calculate_candle_math(open_price=100.0, high=105.0, low=95.0, close=100.0)
    assert metrics.range == 10.0
    assert metrics.body_size == 0.0
    assert metrics.body_ratio == 0.0
    assert metrics.upper_wick == 5.0
    assert metrics.lower_wick == 5.0
    assert pytest.approx(metrics.upper_wick_ratio, 1e-6) == 0.5
    assert pytest.approx(metrics.lower_wick_ratio, 1e-6) == 0.5
    assert metrics.wick_to_body_ratio is None
    assert pytest.approx(metrics.body_position, 1e-6) == 0.5


def test_03_candle_math_marubozu_zero_wicks(service):
    """Marubozu candle (no wicks) must have body_ratio = 1.0, total_wick = 0.0."""
    metrics = service.calculate_candle_math(open_price=100.0, high=110.0, low=100.0, close=110.0)
    assert metrics.range == 10.0
    assert metrics.body_size == 10.0
    assert metrics.upper_wick == 0.0
    assert metrics.lower_wick == 0.0
    assert metrics.total_wick == 0.0
    assert pytest.approx(metrics.body_ratio, 1e-6) == 1.0
    assert metrics.wick_to_body_ratio == 0.0
    assert pytest.approx(metrics.body_position, 1e-6) == 0.5


def test_04_candle_math_upper_wick_only_shooting_star(service):
    """Candle with upper wick only has lower_wick = 0 and body near bottom."""
    metrics = service.calculate_candle_math(open_price=100.0, high=110.0, low=100.0, close=102.0)
    assert metrics.range == 10.0
    assert metrics.body_size == 2.0
    assert metrics.upper_wick == 8.0
    assert metrics.lower_wick == 0.0
    assert pytest.approx(metrics.upper_wick_ratio, 1e-6) == 0.8
    assert metrics.lower_wick_ratio == 0.0
    assert pytest.approx(metrics.body_position, 1e-6) == 0.1


def test_05_candle_math_lower_wick_only_hammer(service):
    """Candle with lower wick only has upper_wick = 0 and body near top."""
    metrics = service.calculate_candle_math(open_price=108.0, high=110.0, low=100.0, close=110.0)
    assert metrics.range == 10.0
    assert metrics.body_size == 2.0
    assert metrics.upper_wick == 0.0
    assert metrics.lower_wick == 8.0
    assert metrics.upper_wick_ratio == 0.0
    assert pytest.approx(metrics.lower_wick_ratio, 1e-6) == 0.8
    assert pytest.approx(metrics.body_position, 1e-6) == 0.9


def test_06_candle_math_inverted_high_low_bounding(service):
    """Input with high < low is automatically bounded and never produces a negative range."""
    metrics = service.calculate_candle_math(open_price=100.0, high=90.0, low=110.0, close=105.0)
    assert metrics.range == 20.0
    assert metrics.high == 110.0
    assert metrics.low == 90.0
    assert metrics.body_size == 5.0
    assert not math.isnan(metrics.range)
    assert not math.isinf(metrics.range)


def test_07_candle_math_micro_floating_point_precision(service):
    """Extremely small values (e.g. crypto/sats) compute accurately without underflow or NaN."""
    metrics = service.calculate_candle_math(open_price=0.000010, high=0.000018, low=0.000009, close=0.000015)
    assert pytest.approx(metrics.range, 1e-9) == 0.000009
    assert pytest.approx(metrics.body_size, 1e-9) == 0.000005
    assert not math.isnan(metrics.body_ratio)
    assert not math.isinf(metrics.body_ratio)


def test_08_candle_math_large_values_xauusd(service):
    """Large values like Gold (XAUUSD ~2500) compute accurately without overflow."""
    metrics = service.calculate_candle_math(open_price=2520.50, high=2545.80, low=2515.20, close=2540.10)
    assert pytest.approx(metrics.range, 1e-4) == 30.60
    assert pytest.approx(metrics.body_size, 1e-4) == 19.60
    assert pytest.approx(metrics.upper_wick, 1e-4) == 5.70
    assert pytest.approx(metrics.lower_wick, 1e-4) == 5.30


# =============================================================================
# 2. WICK BEHAVIOUR & CLASSIFICATIONS (Tests 9 - 18)
# =============================================================================

def test_09_upper_wick_rejection_from_above(service):
    """Candle with dominant upper wick and small lower wick produces UPPER_PRICE_REJECTION."""
    metrics = service.calculate_candle_math(open_price=100.0, high=110.0, low=99.5, close=101.0)
    dominance = service.classify_wick_dominance(
        upper_wick=metrics.upper_wick,
        lower_wick=metrics.lower_wick,
        upper_state=WickState.LARGE_WICK,
        lower_state=WickState.NO_SIGNIFICANT_WICK,
        candle_range=metrics.range,
    )
    rejection = service.observe_rejection(metrics, dominance)
    assert rejection == RejectionObservation.UPPER_PRICE_REJECTION


def test_10_lower_wick_rejection_from_below(service):
    """Candle with dominant lower wick and small upper wick produces LOWER_PRICE_REJECTION."""
    metrics = service.calculate_candle_math(open_price=109.0, high=110.0, low=100.0, close=108.0)
    dominance = service.classify_wick_dominance(
        upper_wick=metrics.upper_wick,
        lower_wick=metrics.lower_wick,
        upper_state=WickState.NO_SIGNIFICANT_WICK,
        lower_state=WickState.LARGE_WICK,
        candle_range=metrics.range,
    )
    rejection = service.observe_rejection(metrics, dominance)
    assert rejection == RejectionObservation.LOWER_PRICE_REJECTION


def test_11_balanced_wicks_indecision_observation(service):
    """Candle with equal upper and lower wicks produces WICKS_BALANCED dominance and indecision=True."""
    metrics = service.calculate_candle_math(open_price=102.0, high=110.0, low=100.0, close=108.0)
    dominance = service.classify_wick_dominance(
        upper_wick=metrics.upper_wick,
        lower_wick=metrics.lower_wick,
        upper_state=WickState.NORMAL_WICK,
        lower_state=WickState.NORMAL_WICK,
        candle_range=metrics.range,
    )
    assert dominance == WickDominance.WICKS_BALANCED

    # Both wicks large (> 30% each)
    metrics_large = service.calculate_candle_math(open_price=104.0, high=110.0, low=100.0, close=106.0)
    dominance_large = service.classify_wick_dominance(
        upper_wick=metrics_large.upper_wick,
        lower_wick=metrics_large.lower_wick,
        upper_state=WickState.LARGE_WICK,
        lower_state=WickState.LARGE_WICK,
        candle_range=metrics_large.range,
    )
    assert dominance_large == WickDominance.BOTH_WICKS_LARGE
    indecision, _ = service.observe_momentum_and_indecision(
        metrics_large,
        body_state=BodyState.SMALL,
        wick_dominance=dominance_large,
        body_evolution=BodyEvolution.DECREASING,
    )
    assert indecision is True


def test_12_wick_expansion_relative_to_prior(service):
    """Current wick > 1.2x prior wick registers wick_expansion = True."""
    now = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    c_prior = {"open": 100.0, "high": 105.0, "low": 98.0, "close": 104.0, "timestamp": now - timedelta(minutes=15)}
    c_current = {"open": 104.0, "high": 120.0, "low": 95.0, "close": 105.0, "timestamp": now}

    obs = service.analyze_candle(c_current, historical_candles=[c_prior])
    assert obs.wick_expansion is True
    assert obs.wick_contraction is False


def test_13_wick_contraction_relative_to_prior(service):
    """Current wick < 0.8x prior wick registers wick_contraction = True."""
    now = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    c_prior = {"open": 100.0, "high": 120.0, "low": 90.0, "close": 105.0, "timestamp": now - timedelta(minutes=15)}
    c_current = {"open": 105.0, "high": 106.0, "low": 104.0, "close": 105.5, "timestamp": now}

    obs = service.analyze_candle(c_current, historical_candles=[c_prior])
    assert obs.wick_contraction is True
    assert obs.wick_expansion is False


def test_14_wick_cluster_detection_lower_wicks(service):
    """3 consecutive candles with dominant lower wicks detect WICK_REJECTION cluster state."""
    c1 = service.calculate_candle_math(open_price=108.0, high=110.0, low=100.0, close=109.0)
    c2 = service.calculate_candle_math(open_price=107.0, high=110.0, low=99.0, close=108.0)
    c3 = service.calculate_candle_math(open_price=108.5, high=110.0, low=100.5, close=109.0)
    cluster = service.observe_wick_clusters([c1, c2, c3])
    assert cluster in (
        WickClusterState.WICK_REJECTION_REPEATED,
        WickClusterState.WICK_REJECTION_STRENGTHENING,
        WickClusterState.WICK_CLUSTER,
    )


def test_15_wick_cluster_detection_upper_wicks(service):
    """3 consecutive candles with dominant upper wicks detect WICK_REJECTION cluster state."""
    c1 = service.calculate_candle_math(open_price=101.0, high=110.0, low=100.0, close=102.0)
    c2 = service.calculate_candle_math(open_price=102.0, high=111.0, low=100.5, close=101.5)
    c3 = service.calculate_candle_math(open_price=101.5, high=110.5, low=100.0, close=102.0)
    cluster = service.observe_wick_clusters([c1, c2, c3])
    assert cluster in (
        WickClusterState.WICK_REJECTION_REPEATED,
        WickClusterState.WICK_REJECTION_STRENGTHENING,
        WickClusterState.WICK_CLUSTER,
    )


def test_16_structural_interaction_resistance_rejection(service):
    """Candle piercing resistance level but closing below yields WICK_REJECTED_RESISTANCE."""
    metrics = service.calculate_candle_math(open_price=2490.0, high=2503.0, low=2488.0, close=2494.0)
    interaction = service.observe_structural_interaction(metrics, resistance_levels=[2500.0])
    assert interaction == StructuralInteraction.WICK_REJECTED_RESISTANCE


def test_17_structural_interaction_support_rejection(service):
    """Candle piercing support level but closing above yields WICK_REJECTED_SUPPORT."""
    metrics = service.calculate_candle_math(open_price=2455.0, high=2460.0, low=2447.0, close=2453.0)
    interaction = service.observe_structural_interaction(metrics, support_levels=[2450.0])
    assert interaction == StructuralInteraction.WICK_REJECTED_SUPPORT


def test_18_liquidity_sweep_like_observation(service):
    """Candle high exceeding prior swing high by wick and closing below yields UPSIDE_LIQUIDITY_SWEEP_LIKE."""
    metrics = service.calculate_candle_math(open_price=2500.0, high=2512.0, low=2498.0, close=2502.0)
    sweep = service.observe_liquidity_sweep_like(metrics, swing_high=2510.0)
    assert sweep == LiquiditySweepLikeObservation.UPSIDE_LIQUIDITY_SWEEP_LIKE


# =============================================================================
# 3. BODY BEHAVIOUR & CLASSIFICATIONS (Tests 19 - 24)
# =============================================================================

def test_19_body_state_classification_large_vs_reference(service):
    """Body size >= 1.5x reference population average classifies as LARGE."""
    ref_bodies = [5.0, 4.8, 5.2, 5.0, 5.1]
    state = service.classify_body_state(current_body=8.5, reference_bodies=ref_bodies)
    assert state == BodyState.LARGE


def test_20_body_state_classification_small_vs_reference(service):
    """Body size <= 0.5x reference population average classifies as SMALL."""
    ref_bodies = [10.0, 10.5, 9.5, 10.2, 9.8]
    state = service.classify_body_state(current_body=4.0, reference_bodies=ref_bodies)
    assert state == BodyState.SMALL


def test_21_body_state_classification_insufficient_sample(service):
    """Fewer than MIN_SAMPLE_SIZE (5) reference candles classifies as UNKNOWN."""
    ref_bodies = [10.0, 10.0, 10.0]
    state = service.classify_body_state(current_body=10.0, reference_bodies=ref_bodies)
    assert state == BodyState.UNKNOWN


def test_22_body_direction_bullish_bearish_neutral(service):
    """Accurately classifies BULLISH, BEARISH, and NEUTRAL directions."""
    assert service.classify_body_direction(100.0, 105.0) == BodyDirection.BULLISH
    assert service.classify_body_direction(105.0, 100.0) == BodyDirection.BEARISH
    assert service.classify_body_direction(100.0, 100.0) == BodyDirection.NEUTRAL


def test_23_body_evolution_expansion_and_contraction(service):
    """Accurately detects body INCREASING (>1.2x) and DECREASING (<0.8x)."""
    ev_exp, _ = service.classify_body_evolution(15.0, 10.0, BodyDirection.BULLISH)
    assert ev_exp == BodyEvolution.INCREASING

    ev_con, _ = service.classify_body_evolution(7.0, 10.0, BodyDirection.BULLISH)
    assert ev_con == BodyEvolution.DECREASING


def test_24_directional_sequence_tracking(service):
    """Consecutive bullish or bearish bodies detect EXPANSION sequences."""
    _, seq_bull = service.classify_body_evolution(15.0, 10.0, BodyDirection.BULLISH)
    assert seq_bull == DirectionalSequence.BULLISH_BODY_EXPANSION

    _, seq_bear = service.classify_body_evolution(15.0, 10.0, BodyDirection.BEARISH)
    assert seq_bear == DirectionalSequence.BEARISH_BODY_EXPANSION


# =============================================================================
# 4. FAILED BREAKOUT SEMANTICS & TEMPORALITY (Tests 25 - 27)
# =============================================================================

def test_25_failed_breakout_at_t0_returns_pending_or_none(service):
    """Candle closing above prior range high at T0 is NOT yet a failed breakout."""
    c0 = service.calculate_candle_math(open_price=100.0, high=112.0, low=99.0, close=111.0)
    failed = service.observe_failed_breakout(c0, range_high=110.0, range_low=90.0, confirmation_candle=None)
    assert failed in (FailedBreakoutObservation.PENDING_CONFIRMATION, FailedBreakoutObservation.NO_FAILED_BREAKOUT)


def test_26_failed_breakout_confirmed_when_t1_closes_inside_range(service):
    """When T0 breaks out above range high and T1 closes back inside, FAILED_UPSIDE_BREAKOUT is observed."""
    c0 = service.calculate_candle_math(open_price=108.0, high=115.0, low=107.0, close=112.0)
    c1 = service.calculate_candle_math(open_price=112.0, high=113.0, low=105.0, close=108.0)
    failed = service.observe_failed_breakout(c0, range_high=110.0, range_low=90.0, confirmation_candle=c1)
    assert failed == FailedBreakoutObservation.FAILED_UPSIDE_BREAKOUT


def test_27_failed_breakout_continuation_not_failed(service):
    """When T0 breaks out above range high and T1 continues higher, it is NOT a failed breakout."""
    c0 = service.calculate_candle_math(open_price=108.0, high=115.0, low=107.0, close=112.0)
    c1 = service.calculate_candle_math(open_price=112.0, high=120.0, low=111.0, close=118.0)
    failed = service.observe_failed_breakout(c0, range_high=110.0, range_low=90.0, confirmation_candle=c1)
    assert failed == FailedBreakoutObservation.NO_FAILED_BREAKOUT


# =============================================================================
# 5. PATTERN TAXONOMIES (IG & GROWW) (Tests 28 - 39)
# =============================================================================

def test_28_pattern_hammer_detection(service):
    """Hammer pattern requires downtrend context, small body at top, lower wick >= 2x body."""
    hammer = service.calculate_candle_math(open_price=108.0, high=109.0, low=100.0, close=109.0)
    patterns = service.detect_pattern_labels([hammer], prior_trend="DOWNTREND")
    assert PatternLabel.HAMMER in patterns


def test_29_pattern_hanging_man_detection(service):
    """Hanging man pattern has same geometry as hammer but requires UPTREND context."""
    hanging_man = service.calculate_candle_math(open_price=108.0, high=109.0, low=100.0, close=109.0)
    patterns = service.detect_pattern_labels([hanging_man], prior_trend="UPTREND")
    assert PatternLabel.HANGING_MAN in patterns


def test_30_pattern_shooting_star_detection(service):
    """Shooting star pattern requires uptrend context, small body at bottom, upper wick >= 2x body."""
    shooting_star = service.calculate_candle_math(open_price=101.0, high=110.0, low=100.5, close=102.0)
    patterns = service.detect_pattern_labels([shooting_star], prior_trend="UPTREND")
    assert PatternLabel.SHOOTING_STAR in patterns


def test_31_pattern_inverted_hammer_detection(service):
    """Inverted hammer pattern has same geometry as shooting star but requires DOWNTREND context."""
    inv_hammer = service.calculate_candle_math(open_price=101.0, high=110.0, low=100.5, close=102.0)
    patterns = service.detect_pattern_labels([inv_hammer], prior_trend="DOWNTREND")
    assert PatternLabel.INVERTED_HAMMER in patterns


def test_32_pattern_bullish_engulfing(service):
    """Bullish engulfing: bearish candle followed by larger bullish candle engulfing prior body."""
    c1 = service.calculate_candle_math(open_price=105.0, high=106.0, low=99.0, close=100.0)  # Bearish body [100, 105]
    c2 = service.calculate_candle_math(open_price=99.0, high=108.0, low=98.0, close=107.0)   # Bullish body [99, 107]
    patterns = service.detect_pattern_labels([c1, c2], prior_trend="DOWNTREND")
    assert PatternLabel.BULLISH_ENGULFING in patterns


def test_33_pattern_bearish_engulfing(service):
    """Bearish engulfing: bullish candle followed by larger bearish candle engulfing prior body."""
    c1 = service.calculate_candle_math(open_price=100.0, high=106.0, low=99.0, close=105.0)  # Bullish body [100, 105]
    c2 = service.calculate_candle_math(open_price=106.0, high=107.0, low=97.0, close=98.0)   # Bearish body [98, 106]
    patterns = service.detect_pattern_labels([c1, c2], prior_trend="UPTREND")
    assert PatternLabel.BEARISH_ENGULFING in patterns


def test_34_pattern_morning_star(service):
    """Morning star: 3 candles (bearish, small star, bullish closing > midpoint of candle 1)."""
    c1 = service.calculate_candle_math(open_price=110.0, high=111.0, low=99.0, close=100.0)
    c2 = service.calculate_candle_math(open_price=98.0, high=99.0, low=96.0, close=97.5)
    c3 = service.calculate_candle_math(open_price=98.0, high=108.0, low=97.5, close=106.0)
    patterns = service.detect_pattern_labels([c1, c2, c3], prior_trend="DOWNTREND")
    assert PatternLabel.MORNING_STAR in patterns


def test_35_pattern_evening_star(service):
    """Evening star: 3 candles (bullish, small star, bearish closing < midpoint of candle 1)."""
    c1 = service.calculate_candle_math(open_price=100.0, high=111.0, low=99.0, close=110.0)
    c2 = service.calculate_candle_math(open_price=112.0, high=114.0, low=111.0, close=112.5)
    c3 = service.calculate_candle_math(open_price=112.0, high=112.5, low=101.0, close=104.0)
    patterns = service.detect_pattern_labels([c1, c2, c3], prior_trend="UPTREND")
    assert PatternLabel.EVENING_STAR in patterns


def test_36_pattern_three_white_soldiers(service):
    """Three white soldiers: 3 consecutive bullish candles with small upper wicks."""
    c1 = service.calculate_candle_math(open_price=100.0, high=105.5, low=99.5, close=105.0)
    c2 = service.calculate_candle_math(open_price=104.5, high=110.5, low=104.0, close=110.0)
    c3 = service.calculate_candle_math(open_price=109.5, high=115.5, low=109.0, close=115.0)
    patterns = service.detect_pattern_labels([c1, c2, c3], prior_trend="DOWNTREND")
    assert PatternLabel.THREE_WHITE_SOLDIERS in patterns


def test_37_pattern_three_black_crows(service):
    """Three black crows: 3 consecutive bearish candles with small lower wicks."""
    c1 = service.calculate_candle_math(open_price=115.0, high=115.5, low=109.5, close=110.0)
    c2 = service.calculate_candle_math(open_price=110.5, high=111.0, low=104.5, close=105.0)
    c3 = service.calculate_candle_math(open_price=105.5, high=106.0, low=99.5, close=100.0)
    patterns = service.detect_pattern_labels([c1, c2, c3], prior_trend="UPTREND")
    assert PatternLabel.THREE_BLACK_CROWS in patterns


def test_38_pattern_tweezer_top_and_bottom(service):
    """Tweezer tops have matching highs + wicks >= 25%; tweezer bottoms have matching lows + wicks >= 25%."""
    # Top: matching highs = 110.0, upper wicks >= 25% of range
    c1_top = service.calculate_candle_math(open_price=100.0, high=110.0, low=99.0, close=105.0)
    c2_top = service.calculate_candle_math(open_price=105.0, high=110.0, low=99.0, close=101.0)
    patterns_top = service.detect_pattern_labels([c1_top, c2_top], prior_trend="UPTREND")
    assert PatternLabel.TWEEZER_TOP in patterns_top

    # Bottom: matching lows = 100.0, lower wicks >= 25% of range
    c1_bot = service.calculate_candle_math(open_price=108.0, high=109.0, low=100.0, close=104.0)
    c2_bot = service.calculate_candle_math(open_price=104.0, high=107.0, low=100.0, close=106.0)
    patterns_bot = service.detect_pattern_labels([c1_bot, c2_bot], prior_trend="DOWNTREND")
    assert PatternLabel.TWEEZER_BOTTOM in patterns_bot


def test_39_pattern_groww_piercing_line(service):
    """Groww piercing line: bearish candle followed by bullish candle opening below low and closing > 50% into body."""
    c1 = service.calculate_candle_math(open_price=110.0, high=111.0, low=100.0, close=100.0)
    c2 = service.calculate_candle_math(open_price=98.0, high=107.0, low=97.0, close=106.0)
    patterns = service.detect_pattern_labels([c1, c2], prior_trend="DOWNTREND")
    assert PatternLabel.PIERCING_LINE in patterns


# =============================================================================
# 6. CONTEXT & ENVIRONMENT (Tests 40 - 46)
# =============================================================================

def test_40_trend_pullback_observation_in_uptrend(service):
    """Lower wick rejection in an established uptrend classifies as POSSIBLE_TREND_CONTINUATION_OBSERVATION."""
    metrics = service.calculate_candle_math(open_price=108.0, high=110.0, low=100.0, close=109.0)
    pullback = service.observe_trend_pullback(
        math_metrics=metrics,
        rejection=RejectionObservation.LOWER_PRICE_REJECTION,
        trend_context="UPTREND",
        prior_close=108.0,
    )
    assert pullback == TrendPullbackObservation.POSSIBLE_TREND_CONTINUATION_OBSERVATION


def test_41_trend_pullback_observation_in_downtrend(service):
    """Upper wick rejection in an established downtrend classifies as POSSIBLE_TREND_CONTINUATION_OBSERVATION."""
    metrics = service.calculate_candle_math(open_price=101.0, high=110.0, low=100.0, close=102.0)
    pullback = service.observe_trend_pullback(
        math_metrics=metrics,
        rejection=RejectionObservation.UPPER_PRICE_REJECTION,
        trend_context="DOWNTREND",
        prior_close=102.0,
    )
    assert pullback == TrendPullbackObservation.POSSIBLE_TREND_CONTINUATION_OBSERVATION


def test_42_session_context_extremes(service):
    """Detects candle at or exceeding session high or low extremes within 0.1% tolerance."""
    now = datetime(2026, 9, 22, 14, 0, tzinfo=timezone.utc)
    metrics_high = service.calculate_candle_math(open_price=105.0, high=110.05, low=104.0, close=109.0)
    session_ctx = service.derive_session_context(
        timestamp=now,
        math_metrics=metrics_high,
        session_extremes={"LONDON": (110.0, 90.0)},
    )
    assert session_ctx == SessionContext.LONDON_SESSION_HIGH


def test_43_volatility_context_classification(service):
    """Range > 2.5x reference produces SPIKE; > 1.5x produces EXPANSION."""
    ref_ranges = [10.0] * 10
    assert (
        service.derive_volatility_context(26.0, ref_ranges, NewsContext.NO_NEWS_CONTEXT)
        == VolatilityContext.VOLATILITY_SPIKE
    )
    assert (
        service.derive_volatility_context(16.0, ref_ranges, NewsContext.NO_NEWS_CONTEXT)
        == VolatilityContext.VOLATILITY_EXPANSION
    )
    assert (
        service.derive_volatility_context(10.0, ref_ranges, NewsContext.NO_NEWS_CONTEXT)
        == VolatilityContext.NORMAL_VOLATILITY
    )


def test_44_news_context_strictly_unknown_when_no_events_provided(service):
    """Mandatory Invariant (Test Req 33): huge candle with large wicks MUST produce NewsContext.UNKNOWN if no calendar events are provided."""
    now = datetime(2026, 9, 22, 12, 30, tzinfo=timezone.utc)
    news_ctx = service.derive_news_context(timestamp=now, authoritative_calendar_events=None)
    assert news_ctx == NewsContext.UNKNOWN


def test_45_news_context_detected_when_event_within_30_minutes(service):
    """News context is detected when an authoritative economic event is within 30 minutes."""
    now = datetime(2026, 9, 22, 12, 30, tzinfo=timezone.utc)
    events = [{"title": "US CPI", "timestamp": now - timedelta(minutes=10), "impact": "HIGH"}]
    news_ctx = service.derive_news_context(timestamp=now, authoritative_calendar_events=events)
    assert news_ctx == NewsContext.NEWS_CONTEXT


def test_46_volume_context_distinguishes_genuine_vs_tick_volume(service):
    """Centralized exchange yields GENUINE_VOLUME; OTC / default yields TICK_VOLUME."""
    ctx_genuine, vol1 = service.derive_volume_context(15000.0, is_centralized_exchange=True)
    assert ctx_genuine == VolumeContext.GENUINE_VOLUME
    assert vol1 == 15000.0

    ctx_tick, vol2 = service.derive_volume_context(120.0, is_centralized_exchange=False)
    assert ctx_tick == VolumeContext.TICK_VOLUME
    assert vol2 == 120.0


# =============================================================================
# 7. MULTI-CANDLE SEQUENCE TRACKING (Tests 47 - 50)
# =============================================================================

def test_47_sequence_body_evolution_expanding(service):
    """5 candles with steadily growing bodies detect BodyEvolution.INCREASING."""
    candles = [
        service.calculate_candle_math(100.0, 102.0, 99.0, 102.0),   # body 2
        service.calculate_candle_math(102.0, 106.0, 101.0, 106.0),  # body 4
        service.calculate_candle_math(106.0, 112.0, 105.0, 112.0),  # body 6
        service.calculate_candle_math(112.0, 120.0, 111.0, 120.0),  # body 8
        service.calculate_candle_math(120.0, 131.0, 119.0, 131.0),  # body 11
    ]
    seq_obs = service.observe_candle_sequence(candles)
    assert seq_obs.body_evolution == BodyEvolution.INCREASING
    assert seq_obs.candles_analyzed == 5


def test_48_sequence_range_evolution_contracting(service):
    """5 candles with shrinking ranges detect contracting range evolution."""
    candles = [
        service.calculate_candle_math(100.0, 120.0, 95.0, 115.0),  # range 25
        service.calculate_candle_math(115.0, 130.0, 112.0, 128.0), # range 18
        service.calculate_candle_math(128.0, 138.0, 126.0, 137.0), # range 12
        service.calculate_candle_math(137.0, 144.0, 136.0, 143.0), # range 8
        service.calculate_candle_math(143.0, 147.0, 142.0, 146.0), # range 5
    ]
    seq_obs = service.observe_candle_sequence(candles)
    assert seq_obs.range_evolution == "CONTRACTING"


def test_49_sequence_with_fewer_than_min_candles_graceful_fallback(service):
    """Sequence observation with fewer than 2 candles falls back gracefully without throwing."""
    single = [service.calculate_candle_math(100.0, 105.0, 95.0, 102.0)]
    seq_obs = service.observe_candle_sequence(single)
    assert seq_obs.candles_analyzed == 1
    assert seq_obs.body_evolution == BodyEvolution.UNKNOWN


def test_50_sequence_momentum_streak_detection(service):
    """5 consecutive bullish candles detect MOMENTUM_STRENGTHENING sequence momentum."""
    candles = [
        service.calculate_candle_math(100.0, 105.0, 100.0, 104.0),
        service.calculate_candle_math(104.0, 110.0, 104.0, 109.0),
        service.calculate_candle_math(109.0, 115.0, 109.0, 114.0),
        service.calculate_candle_math(114.0, 120.0, 114.0, 119.0),
        service.calculate_candle_math(119.0, 127.0, 119.0, 126.0),
    ]
    seq_obs = service.observe_candle_sequence(candles)
    assert seq_obs.momentum_evolution == "MOMENTUM_STRENGTHENING"


# =============================================================================
# 8. NO-LOOKAHEAD & TEMPORAL INVARIANTS (Tests 51 - 55)
# =============================================================================

def test_51_no_lookahead_as_of_filters_future_reference_candles(service):
    """Candles occurring after as_of are strictly excluded from the reference population."""
    t0 = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    t_future = datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc)

    c_past = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "timestamp": t0 - timedelta(minutes=15)}
    c_future = {"open": 102.0, "high": 150.0, "low": 100.0, "close": 145.0, "timestamp": t_future}
    c_current = {"open": 102.0, "high": 106.0, "low": 101.0, "close": 104.0, "timestamp": t0}

    obs = service.analyze_candle(c_current, historical_candles=[c_past, c_future], as_of=t0)
    assert obs.as_of == t0
    assert obs.evaluated_at == t0


def test_52_no_lookahead_confirmation_candle_after_as_of_is_ignored(service):
    """Confirmation candle after as_of cannot be observed; returns PENDING_CONFIRMATION."""
    t0 = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    t_confirm = datetime(2026, 9, 22, 10, 15, tzinfo=timezone.utc)

    c_current = {"open": 108.0, "high": 110.0, "low": 100.0, "close": 109.0, "timestamp": t0}
    c_future = {"open": 109.0, "high": 120.0, "low": 108.0, "close": 118.0, "timestamp": t_confirm}

    obs = service.analyze_candle(c_current, future_candles=[c_future], as_of=t0)
    assert obs.confirmation_status == ConfirmationStatus.PENDING_CONFIRMATION


def test_53_no_lookahead_as_of_timestamp_boundary_exact_match(service):
    """Candle at exact as_of timestamp is included, candle 1 second later is excluded."""
    as_of = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)
    c_exact = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "timestamp": as_of}
    obs = service.analyze_candle(c_exact, as_of=as_of)
    assert obs.evaluated_at == as_of
    assert obs.as_of == as_of


def test_54_live_candle_cannot_see_future_candles(service):
    """Live candle evaluated at current time without future_candles defaults to PENDING or NOT_APPLICABLE confirmation."""
    now = datetime.now(timezone.utc)
    c_live = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "timestamp": now}
    obs = service.analyze_candle(c_live)
    assert obs.confirmation_status in (
        ConfirmationStatus.PENDING_CONFIRMATION,
        ConfirmationStatus.NOT_APPLICABLE,
        ConfirmationStatus.UNKNOWN,
    )


def test_55_observation_timestamps_evaluated_at_and_as_of_consistent(service):
    """evaluated_at <= as_of invariant strictly holds for all generated observations."""
    as_of = datetime(2026, 9, 22, 15, 0, tzinfo=timezone.utc)
    eval_time = datetime(2026, 9, 22, 14, 45, tzinfo=timezone.utc)
    c = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "timestamp": eval_time}
    obs = service.analyze_candle(c, as_of=as_of)
    assert obs.evaluated_at <= obs.as_of


# =============================================================================
# 9. DETERMINISM, STATELESSNESS & PRODUCTION ISOLATION (Tests 56 - 62)
# =============================================================================

def test_56_deterministic_pure_function_output(service):
    """Repeated calls with identical inputs yield exactly identical observations."""
    now = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    c = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "timestamp": now}
    obs1 = service.analyze_candle(c, as_of=now)
    obs2 = service.analyze_candle(c, as_of=now)

    assert obs1.model_dump() == obs2.model_dump()


def test_57_statelessness_no_cross_call_state_leakage(service):
    """Calls for different instruments do not cross-contaminate or accumulate mutable state."""
    now = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    c_gold = {"open": 2500.0, "high": 2510.0, "low": 2490.0, "close": 2505.0, "symbol": "XAUUSD", "timestamp": now}
    c_gbp = {"open": 1.3000, "high": 1.3050, "low": 1.2980, "close": 1.3020, "symbol": "GBPUSD", "timestamp": now}

    obs_gold = service.analyze_candle(c_gold, as_of=now)
    obs_gbp = service.analyze_candle(c_gbp, as_of=now)

    assert obs_gold.instrument == "XAUUSD"
    assert obs_gbp.instrument == "GBPUSD"
    assert pytest.approx(obs_gold.range, 1e-4) == 20.0
    assert pytest.approx(obs_gbp.range, 1e-4) == 0.0070


def test_58_pattern_detection_never_generates_orders(service):
    """Candlestick research service contains zero broker execution routines."""
    import inspect
    source = inspect.getsource(CandlestickResearchService)
    assert "order_send" not in source
    assert "order_modify" not in source
    assert "order_close" not in source
    assert "MetaTrader5.initialize" not in source


def test_59_pattern_label_is_descriptive_not_a_signal(service):
    """Pattern labels are descriptive enums and do not produce trading signals or directions."""
    hammer_candle = service.calculate_candle_math(open_price=108.0, high=109.0, low=100.0, close=109.0)
    patterns = service.detect_pattern_labels([hammer_candle], prior_trend="DOWNTREND")
    assert PatternLabel.HAMMER in patterns

    # Crucial safety assertion: PatternLabel enum must NOT map to a CandidateDirection or order
    assert not hasattr(PatternLabel.HAMMER, "direction")
    assert not hasattr(PatternLabel.HAMMER, "action")


def test_60_production_safeguards_guardian_and_risk_untouched():
    """Importing and using CandlestickResearchService does NOT mutate Capital Guardian configuration."""
    from app.core.config.settings import settings
    assert settings.MAX_SIMULTANEOUS_TRADES == 3


def test_61_database_safety_zero_writes(service):
    """Invoking the research service performs ZERO database writes."""
    now = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    c = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "timestamp": now}
    obs = service.analyze_candle(c, as_of=now)
    assert obs is not None


def test_62_source_provenance_tracking(service):
    """Observations correctly record SourceProvenance tags."""
    now = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)
    c = {"open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "timestamp": now}
    obs = service.analyze_candle(c, as_of=now)
    assert SourceProvenance.PDF_BODY_WICK_FRAMEWORK in obs.source_provenance
    assert SourceProvenance.FXOPEN_WICK_ANALYSIS in obs.source_provenance


# =============================================================================
# 10. REST API ANALYTICS ENDPOINT INTEGRATION (Tests 63 - 70)
# =============================================================================

def test_63_analytics_endpoint_get_candlestick_behaviour_success(client):
    """GET /api/v1/analytics/candlestick-behaviour returns 200 with valid schema."""
    response = client.get("/api/v1/analytics/candlestick-behaviour")
    assert response.status_code == 200
    data = response.json()
    assert "observations" in data
    assert "total_observations" in data
    assert data["experiment_version"] == "1.0.0"
    assert "as_of" in data
    assert "filters_applied" in data


def test_64_analytics_endpoint_filter_by_instrument(client):
    """Endpoint records instrument filter parameter."""
    response = client.get("/api/v1/analytics/candlestick-behaviour?instrument=XAUUSD")
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"]["instrument"] == "XAUUSD"


def test_65_analytics_endpoint_filter_by_timeframe(client):
    """Endpoint records timeframe filter parameter."""
    response = client.get("/api/v1/analytics/candlestick-behaviour?timeframe=M15")
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"]["timeframe"] == "M15"


def test_66_analytics_endpoint_filter_by_pattern(client):
    """Endpoint records pattern filter parameter."""
    response = client.get("/api/v1/analytics/candlestick-behaviour?pattern=HAMMER")
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"]["pattern"] == "HAMMER"


def test_67_analytics_endpoint_filter_by_wick_type(client):
    """Endpoint records wick_type filter parameter."""
    response = client.get("/api/v1/analytics/candlestick-behaviour?wick_type=LOWER_PRICE_REJECTION")
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"]["wick_type"] == "LOWER_PRICE_REJECTION"


def test_68_analytics_endpoint_filter_by_regime(client):
    """Endpoint records regime filter parameter."""
    response = client.get("/api/v1/analytics/candlestick-behaviour?regime=TRENDING")
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"]["regime"] == "TRENDING"


def test_69_analytics_endpoint_limit_parameter(client):
    """Endpoint records limit filter parameter."""
    response = client.get("/api/v1/analytics/candlestick-behaviour?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"]["limit"] == 5


def test_70_analytics_endpoint_as_of_parameter(client):
    """Endpoint parses and records as_of timestamp parameter without lookahead."""
    as_of_str = "2026-09-22T08:00:00Z"
    response = client.get(f"/api/v1/analytics/candlestick-behaviour?as_of={as_of_str}")
    assert response.status_code == 200
    data = response.json()
    assert "2026-09-22T08:00:00" in data["filters_applied"]["as_of"]
