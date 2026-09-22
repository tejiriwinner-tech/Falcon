"""
Falcon V10 — Candlestick & Wick Behaviour Research Service.

A controlled, deterministic, stateless, read-only observational research service.
Reconciles four research sources into a two-layer representation:
1. RAW CANDLE BEHAVIOUR (OHLC Mathematics, Wicks, Body Dynamics, Context)
2. OPTIONAL DESCRIPTIVE PATTERN LABELS (IG and Groww taxonomies)

Stateless Architecture:
- Zero process-local mutable state as source of truth.
- Computes observations dynamically from authoritative inputs and market context.
- Zero lookahead: strictly enforces evaluated_at <= as_of.
- Zero broker connectivity: completely independent of broker execution APIs.
- Zero database mutations: completely independent of database migrations.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from app.schemas.candlestick_research import (
    BodyDirection,
    BodyEvolution,
    BodyState,
    CandleMathMetrics,
    CandleSequenceObservation,
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


class CandlestickResearchService:
    """
    Stateless, deterministic research service for candlestick and wick behaviour analysis.
    Evaluates raw OHLC geometry, relative statistical classifications, multi-candle
    sequences, and market context without converting observations into trading decisions.
    """

    EXPERIMENT_NAME: str = "CANDLE_BEHAVIOUR_EXPERIMENT"
    EXPERIMENT_VERSION: str = "1.0.0"
    DEFAULT_LOOKBACK: int = 20
    MIN_SAMPLE_SIZE: int = 5

    # -------------------------------------------------------------------------
    # 1. Authoritative Candle Mathematics
    # -------------------------------------------------------------------------

    @staticmethod
    def calculate_candle_math(open_price: float, high: float, low: float, close: float) -> CandleMathMetrics:
        """
        Deterministic OHLC mathematics with explicit zero-division and invalidity guards.
        Never produces NaN or Infinity.
        """
        o = float(open_price)
        h = float(high)
        l = float(low)
        c = float(close)

        # Enforce valid bounding
        actual_high = max(h, o, c, l)
        actual_low = min(l, o, c, h)
        rng = actual_high - actual_low
        body_size = abs(c - o)
        upper_wick = actual_high - max(o, c)
        lower_wick = min(o, c) - actual_low
        total_wick = upper_wick + lower_wick

        if rng > 1e-12:
            body_ratio = body_size / rng
            upper_wick_ratio = upper_wick / rng
            lower_wick_ratio = lower_wick / rng
            # Body position: center of body relative to total range (0.0 = low, 1.0 = high)
            body_center = min(o, c) + (body_size / 2.0)
            body_position = (body_center - actual_low) / rng
        else:
            body_ratio = None
            upper_wick_ratio = None
            lower_wick_ratio = None
            body_position = None

        if body_size > 1e-12:
            wick_to_body_ratio = total_wick / body_size
        else:
            wick_to_body_ratio = None

        return CandleMathMetrics(
            open=o,
            high=actual_high,
            low=actual_low,
            close=c,
            range=rng,
            body_size=body_size,
            body_ratio=body_ratio,
            upper_wick=upper_wick,
            lower_wick=lower_wick,
            upper_wick_ratio=upper_wick_ratio,
            lower_wick_ratio=lower_wick_ratio,
            total_wick=total_wick,
            wick_to_body_ratio=wick_to_body_ratio,
            body_position=body_position,
        )

    # -------------------------------------------------------------------------
    # 2. Contextual Relative Body Classification
    # -------------------------------------------------------------------------

    @classmethod
    def classify_body_state(
        cls,
        current_body: float,
        reference_bodies: List[float],
    ) -> BodyState:
        """
        Classifies body size relative to an explicit reference population of preceding candles.
        Current candle is excluded from reference population.
        Requires at least MIN_SAMPLE_SIZE reference samples.
        """
        if not reference_bodies or len(reference_bodies) < cls.MIN_SAMPLE_SIZE:
            return BodyState.UNKNOWN

        mean_body = sum(reference_bodies) / len(reference_bodies)
        if mean_body <= 1e-12:
            return BodyState.UNKNOWN

        ratio = current_body / mean_body

        if ratio < 0.25:
            return BodyState.VERY_SMALL
        elif ratio < 0.75:
            return BodyState.SMALL
        elif ratio <= 1.35:
            return BodyState.NORMAL
        elif ratio <= 2.0:
            return BodyState.LARGE
        else:
            return BodyState.VERY_LARGE

    @staticmethod
    def classify_body_direction(open_price: float, close: float) -> BodyDirection:
        """Determines directional orientation from open and close."""
        diff = close - open_price
        if abs(diff) <= 1e-8:
            return BodyDirection.NEUTRAL
        elif diff > 0:
            return BodyDirection.BULLISH
        else:
            return BodyDirection.BEARISH

    @staticmethod
    def classify_body_evolution(
        current_body: float,
        prior_body: Optional[float],
        direction: BodyDirection,
    ) -> Tuple[BodyEvolution, DirectionalSequence]:
        """Observes body size change relative to immediate preceding candle."""
        if prior_body is None or prior_body <= 1e-12:
            return BodyEvolution.UNKNOWN, DirectionalSequence.UNKNOWN

        ratio = current_body / prior_body
        if ratio > 1.20:
            evolution = BodyEvolution.INCREASING
            if direction == BodyDirection.BULLISH:
                seq = DirectionalSequence.BULLISH_BODY_EXPANSION
            elif direction == BodyDirection.BEARISH:
                seq = DirectionalSequence.BEARISH_BODY_EXPANSION
            else:
                seq = DirectionalSequence.UNKNOWN
        elif ratio < 0.80:
            evolution = BodyEvolution.DECREASING
            if direction == BodyDirection.BULLISH:
                seq = DirectionalSequence.BULLISH_BODY_CONTRACTION
            elif direction == BodyDirection.BEARISH:
                seq = DirectionalSequence.BEARISH_BODY_CONTRACTION
            else:
                seq = DirectionalSequence.UNKNOWN
        else:
            evolution = BodyEvolution.STABLE
            seq = DirectionalSequence.DIRECTIONAL_BODY_STABILITY

        return evolution, seq

    # -------------------------------------------------------------------------
    # 3. Contextual Relative Wick Classification
    # -------------------------------------------------------------------------

    @classmethod
    def classify_wick_state(
        cls,
        wick_size: float,
        candle_range: float,
        reference_wicks: List[float],
    ) -> WickState:
        """
        Classifies wick size relative to reference population of preceding candle wicks.
        If candle has no significant wick (< 5% of range), returns NO_SIGNIFICANT_WICK.
        """
        if candle_range > 1e-12 and (wick_size / candle_range) < 0.05:
            return WickState.NO_SIGNIFICANT_WICK

        if not reference_wicks or len(reference_wicks) < cls.MIN_SAMPLE_SIZE:
            return WickState.UNKNOWN

        mean_wick = sum(reference_wicks) / len(reference_wicks)
        if mean_wick <= 1e-12:
            return WickState.NO_SIGNIFICANT_WICK if wick_size <= 1e-8 else WickState.UNKNOWN

        ratio = wick_size / mean_wick
        if ratio < 0.35:
            return WickState.SMALL_WICK
        elif ratio <= 1.50:
            return WickState.NORMAL_WICK
        elif ratio <= 2.50:
            return WickState.LARGE_WICK
        else:
            return WickState.EXTREME_WICK

    @staticmethod
    def classify_wick_dominance(
        upper_wick: float,
        lower_wick: float,
        upper_state: WickState,
        lower_state: WickState,
        candle_range: float,
    ) -> WickDominance:
        """Determines directional wick dominance between upper and lower shadows."""
        if candle_range <= 1e-12:
            return WickDominance.WICKS_BALANCED

        upper_ratio = upper_wick / candle_range
        lower_ratio = lower_wick / candle_range

        large_states = (WickState.LARGE_WICK, WickState.EXTREME_WICK)
        if (upper_state in large_states and lower_state in large_states) or (upper_ratio > 0.30 and lower_ratio > 0.30):
            return WickDominance.BOTH_WICKS_LARGE

        if upper_wick > 2.0 * lower_wick and upper_ratio >= 0.25:
            return WickDominance.UPPER_WICK_DOMINANT
        elif lower_wick > 2.0 * upper_wick and lower_ratio >= 0.25:
            return WickDominance.LOWER_WICK_DOMINANT
        else:
            return WickDominance.WICKS_BALANCED

    # -------------------------------------------------------------------------
    # 4. Rejection & Momentum Observations
    # -------------------------------------------------------------------------

    @staticmethod
    def observe_rejection(
        math_metrics: CandleMathMetrics,
        wick_dominance: WickDominance,
    ) -> RejectionObservation:
        """
        Observes price rejection purely from candle geometry.
        Upper rejection: upper wick dominant + body in lower half.
        Lower rejection: lower wick dominant + body in upper half.
        """
        if math_metrics.range <= 1e-12 or math_metrics.body_position is None:
            return RejectionObservation.UNKNOWN

        u_ratio = math_metrics.upper_wick_ratio or 0.0
        l_ratio = math_metrics.lower_wick_ratio or 0.0
        pos = math_metrics.body_position

        if wick_dominance == WickDominance.UPPER_WICK_DOMINANT and u_ratio >= 0.40 and pos <= 0.45:
            return RejectionObservation.UPPER_PRICE_REJECTION
        elif wick_dominance == WickDominance.LOWER_WICK_DOMINANT and l_ratio >= 0.40 and pos >= 0.55:
            return RejectionObservation.LOWER_PRICE_REJECTION
        else:
            return RejectionObservation.NO_CLEAR_REJECTION

    @staticmethod
    def observe_momentum_and_indecision(
        math_metrics: CandleMathMetrics,
        body_state: BodyState,
        wick_dominance: WickDominance,
        body_evolution: BodyEvolution,
    ) -> Tuple[bool, str]:
        """
        Observes indecision (small body with significant wicks)
        and momentum dynamics (expansion vs fading).
        """
        body_ratio = math_metrics.body_ratio or 0.0
        indecision = False
        if body_ratio <= 0.25 and wick_dominance in (WickDominance.BOTH_WICKS_LARGE, WickDominance.WICKS_BALANCED):
            indecision = True

        if body_state in (BodyState.LARGE, BodyState.VERY_LARGE) and body_ratio >= 0.65:
            momentum = "MOMENTUM_EXPANSION"
        elif body_evolution == BodyEvolution.DECREASING and wick_dominance in (WickDominance.UPPER_WICK_DOMINANT, WickDominance.LOWER_WICK_DOMINANT):
            momentum = "MOMENTUM_FADING"
        elif indecision:
            momentum = "MOMENTUM_INDECISION"
        else:
            momentum = "MOMENTUM_STABLE"

        return indecision, momentum

    # -------------------------------------------------------------------------
    # 5. Multi-Candle Wick Clusters
    # -------------------------------------------------------------------------

    @classmethod
    def observe_wick_clusters(
        cls,
        recent_maths: List[CandleMathMetrics],
    ) -> WickClusterState:
        """
        Evaluates consecutive wick behaviour across preceding 2-3 candles.
        Detects repeated rejections, strengthening or weakening clusters.
        """
        if len(recent_maths) < 3:
            return WickClusterState.UNKNOWN

        c1, c2, c3 = recent_maths[-3], recent_maths[-2], recent_maths[-1]

        # Check for lower wick cluster
        l1, l2, l3 = c1.lower_wick, c2.lower_wick, c3.lower_wick
        r1, r2, r3 = c1.range, c2.range, c3.range
        if all(r > 0 for r in (r1, r2, r3)):
            lr1, lr2, lr3 = l1 / r1, l2 / r2, l3 / r3
            if lr1 >= 0.35 and lr2 >= 0.35 and lr3 >= 0.35:
                if l3 > l2 > l1:
                    return WickClusterState.WICK_REJECTION_STRENGTHENING
                elif l3 < l2 < l1:
                    return WickClusterState.WICK_REJECTION_WEAKENING
                else:
                    return WickClusterState.WICK_REJECTION_REPEATED

        # Check for upper wick cluster
        u1, u2, u3 = c1.upper_wick, c2.upper_wick, c3.upper_wick
        if all(r > 0 for r in (r1, r2, r3)):
            ur1, ur2, ur3 = u1 / r1, u2 / r2, u3 / r3
            if ur1 >= 0.35 and ur2 >= 0.35 and ur3 >= 0.35:
                if u3 > u2 > u1:
                    return WickClusterState.WICK_REJECTION_STRENGTHENING
                elif u3 < u2 < u1:
                    return WickClusterState.WICK_REJECTION_WEAKENING
                else:
                    return WickClusterState.WICK_REJECTION_REPEATED

        # 2-candle cluster check
        if len(recent_maths) >= 2:
            prev, curr = recent_maths[-2], recent_maths[-1]
            if prev.range > 0 and curr.range > 0:
                if (prev.lower_wick / prev.range >= 0.35) and (curr.lower_wick / curr.range >= 0.35):
                    return WickClusterState.WICK_CLUSTER
                if (prev.upper_wick / prev.range >= 0.35) and (curr.upper_wick / curr.range >= 0.35):
                    return WickClusterState.WICK_CLUSTER

        return WickClusterState.NO_CLUSTER

    # -------------------------------------------------------------------------
    # 6. Trend Pullback Observation
    # -------------------------------------------------------------------------

    @staticmethod
    def observe_trend_pullback(
        math_metrics: CandleMathMetrics,
        rejection: RejectionObservation,
        trend_context: str,
        prior_close: Optional[float],
    ) -> TrendPullbackObservation:
        """
        Observes whether wick rejection aligns with an existing trend pullback.
        Purely observational; never a trade signal.
        """
        trend_upper = (trend_context or "UNKNOWN").upper()
        if trend_upper in ("UNKNOWN", "NOT_AVAILABLE"):
            return TrendPullbackObservation.UNKNOWN

        is_uptrend = any(t in trend_upper for t in ("UPTREND", "BULLISH"))
        is_downtrend = any(t in trend_upper for t in ("DOWNTREND", "BEARISH"))

        if is_uptrend and rejection == RejectionObservation.LOWER_PRICE_REJECTION:
            if prior_close is not None and math_metrics.low <= prior_close:
                return TrendPullbackObservation.POSSIBLE_TREND_CONTINUATION_OBSERVATION

        if is_downtrend and rejection == RejectionObservation.UPPER_PRICE_REJECTION:
            if prior_close is not None and math_metrics.high >= prior_close:
                return TrendPullbackObservation.POSSIBLE_TREND_CONTINUATION_OBSERVATION

        return TrendPullbackObservation.NO_TREND_PULLBACK

    # -------------------------------------------------------------------------
    # 7. Structural Interaction, Failed Breakout & Liquidity Sweep
    # -------------------------------------------------------------------------

    @staticmethod
    def observe_structural_interaction(
        math_metrics: CandleMathMetrics,
        support_levels: Optional[List[float]] = None,
        resistance_levels: Optional[List[float]] = None,
        swing_highs: Optional[List[float]] = None,
        swing_lows: Optional[List[float]] = None,
        liquidity_zones: Optional[List[Tuple[float, float]]] = None,
    ) -> StructuralInteraction:
        """Observes wick interaction with authoritative structural price levels."""
        has_any_levels = bool(support_levels or resistance_levels or swing_highs or swing_lows or liquidity_zones)
        if not has_any_levels:
            return StructuralInteraction.UNKNOWN

        # 1. Support rejection
        if support_levels:
            for s in support_levels:
                if math_metrics.low <= s <= max(math_metrics.open, math_metrics.close):
                    if math_metrics.close >= s:
                        return StructuralInteraction.WICK_REJECTED_SUPPORT

        # 2. Resistance rejection
        if resistance_levels:
            for r in resistance_levels:
                if min(math_metrics.open, math_metrics.close) <= r <= math_metrics.high:
                    if math_metrics.close <= r:
                        return StructuralInteraction.WICK_REJECTED_RESISTANCE

        # 3. Swing high test
        if swing_highs:
            for sh in swing_highs:
                if abs(math_metrics.high - sh) / sh <= 0.0015:
                    return StructuralInteraction.WICK_TESTED_SWING_HIGH

        # 4. Swing low test
        if swing_lows:
            for sl in swing_lows:
                if abs(math_metrics.low - sl) / sl <= 0.0015:
                    return StructuralInteraction.WICK_TESTED_SWING_LOW

        # 5. Liquidity zone test
        if liquidity_zones:
            for z_low, z_high in liquidity_zones:
                if math_metrics.high >= z_low and math_metrics.low <= z_high:
                    return StructuralInteraction.WICK_TESTED_LIQUIDITY_ZONE

        return StructuralInteraction.NO_STRUCTURAL_INTERACTION

    @staticmethod
    def observe_failed_breakout(
        math_metrics: CandleMathMetrics,
        range_high: Optional[float] = None,
        range_low: Optional[float] = None,
        confirmation_candle: Optional[CandleMathMetrics] = None,
    ) -> FailedBreakoutObservation:
        """
        Strict temporal semantics:
        - At T0 (breakout candle close): If candle penetrated level and closed back inside -> FAILED_BREAKOUT.
        - If candle closed OUTSIDE the level, failure cannot be claimed at T0!
          Requires subsequent confirmation_candle closing back inside -> FAILED_BREAKOUT, else PENDING_CONFIRMATION.
        """
        if range_high is None and range_low is None:
            return FailedBreakoutObservation.UNKNOWN

        # Upside check
        if range_high is not None:
            # Case A: Intrabar failure at T0 (penetrated above, closed below)
            if math_metrics.high > range_high and math_metrics.close <= range_high:
                return FailedBreakoutObservation.FAILED_UPSIDE_BREAKOUT

            # Case B: Closed above at T0 (breakout attempt)
            if math_metrics.close > range_high:
                if confirmation_candle is not None:
                    if confirmation_candle.close < range_high:
                        return FailedBreakoutObservation.FAILED_UPSIDE_BREAKOUT
                    else:
                        return FailedBreakoutObservation.NO_FAILED_BREAKOUT
                return FailedBreakoutObservation.PENDING_CONFIRMATION

        # Downside check
        if range_low is not None:
            # Case A: Intrabar failure at T0 (penetrated below, closed above)
            if math_metrics.low < range_low and math_metrics.close >= range_low:
                return FailedBreakoutObservation.FAILED_DOWNSIDE_BREAKOUT

            # Case B: Closed below at T0
            if math_metrics.close < range_low:
                if confirmation_candle is not None:
                    if confirmation_candle.close > range_low:
                        return FailedBreakoutObservation.FAILED_DOWNSIDE_BREAKOUT
                    else:
                        return FailedBreakoutObservation.NO_FAILED_BREAKOUT
                return FailedBreakoutObservation.PENDING_CONFIRMATION

        return FailedBreakoutObservation.NO_FAILED_BREAKOUT

    @staticmethod
    def observe_liquidity_sweep_like(
        math_metrics: CandleMathMetrics,
        swing_high: Optional[float] = None,
        swing_low: Optional[float] = None,
    ) -> LiquiditySweepLikeObservation:
        """
        Observes liquidity-sweep-like price action.
        Wick extends beyond prior swing level, close returns inside prior level.
        Descriptive classification only.
        """
        if swing_high is None and swing_low is None:
            return LiquiditySweepLikeObservation.UNKNOWN

        if swing_high is not None and math_metrics.high > swing_high and math_metrics.close < swing_high:
            return LiquiditySweepLikeObservation.UPSIDE_LIQUIDITY_SWEEP_LIKE

        if swing_low is not None and math_metrics.low < swing_low and math_metrics.close > swing_low:
            return LiquiditySweepLikeObservation.DOWNSIDE_LIQUIDITY_SWEEP_LIKE

        return LiquiditySweepLikeObservation.NO_LIQUIDITY_SWEEP_LIKE_EVENT

    # -------------------------------------------------------------------------
    # 8. Context Derivations (Session, Volatility, News, Volume)
    # -------------------------------------------------------------------------

    @staticmethod
    def derive_session_context(
        timestamp: Optional[datetime],
        math_metrics: CandleMathMetrics,
        session_extremes: Optional[Dict[str, Tuple[float, float]]] = None,
    ) -> SessionContext:
        """
        Deterministic, timezone-safe session context derivation in UTC.
        Examines whether wicks test or reject established session highs/lows.
        """
        if timestamp is None:
            return SessionContext.UNKNOWN

        # Ensure UTC timezone
        dt = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        dt_utc = dt.astimezone(timezone.utc)

        if not session_extremes:
            return SessionContext.NOT_AVAILABLE

        # Check interaction with session extremes
        for sess, (s_high, s_low) in session_extremes.items():
            sess_upper = sess.upper()
            if "ASIAN" in sess_upper:
                if abs(math_metrics.high - s_high) / s_high <= 0.0010:
                    return SessionContext.ASIAN_SESSION_HIGH
                if abs(math_metrics.low - s_low) / s_low <= 0.0010:
                    return SessionContext.ASIAN_SESSION_LOW
            elif "LONDON" in sess_upper:
                if abs(math_metrics.high - s_high) / s_high <= 0.0010:
                    return SessionContext.LONDON_SESSION_HIGH
                if abs(math_metrics.low - s_low) / s_low <= 0.0010:
                    return SessionContext.LONDON_SESSION_LOW
            elif "NEW YORK" in sess_upper or "NY" in sess_upper:
                if abs(math_metrics.high - s_high) / s_high <= 0.0010:
                    return SessionContext.NEW_YORK_SESSION_HIGH
                if abs(math_metrics.low - s_low) / s_low <= 0.0010:
                    return SessionContext.NEW_YORK_SESSION_LOW

        return SessionContext.WITHIN_SESSION_RANGE

    @classmethod
    def derive_volatility_context(
        cls,
        candle_range: float,
        reference_ranges: List[float],
        news_context: NewsContext,
    ) -> VolatilityContext:
        """Derives volatility context relative to reference range population."""
        if not reference_ranges or len(reference_ranges) < cls.MIN_SAMPLE_SIZE:
            return VolatilityContext.UNKNOWN

        mean_range = sum(reference_ranges) / len(reference_ranges)
        if mean_range <= 1e-12:
            return VolatilityContext.UNKNOWN

        ratio = candle_range / mean_range

        if news_context == NewsContext.NEWS_CONTEXT and ratio >= 2.0:
            return VolatilityContext.NEWS_VOLATILITY_CONTEXT
        elif ratio > 2.50:
            return VolatilityContext.VOLATILITY_SPIKE
        elif ratio > 1.50:
            return VolatilityContext.VOLATILITY_EXPANSION
        else:
            return VolatilityContext.NORMAL_VOLATILITY

    @staticmethod
    def derive_news_context(
        timestamp: Optional[datetime],
        authoritative_calendar_events: Optional[List[Any]],
    ) -> NewsContext:
        """
        Evaluates news context strictly from authoritative calendar events.
        Never infers news from candle size or volatility alone.
        If calendar events list is None: returns UNKNOWN.
        """
        if authoritative_calendar_events is None:
            return NewsContext.UNKNOWN

        if not authoritative_calendar_events or timestamp is None:
            return NewsContext.NO_NEWS_CONTEXT

        dt = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)

        # Check if an event occurred within 30 minutes of candle timestamp
        for ev in authoritative_calendar_events:
            ev_time = None
            if isinstance(ev, dict):
                ev_time = (
                    ev.get("eventTime")
                    or ev.get("event_time")
                    or ev.get("publishedAt")
                    or ev.get("timestamp")
                    or ev.get("time")
                )
            else:
                ev_time = getattr(
                    ev,
                    "eventTime",
                    getattr(
                        ev,
                        "event_time",
                        getattr(ev, "publishedAt", getattr(ev, "timestamp", getattr(ev, "time", None))),
                    ),
                )
            if ev_time is not None:
                ev_dt = ev_time if ev_time.tzinfo else ev_time.replace(tzinfo=timezone.utc)
                if abs((dt - ev_dt).total_seconds()) <= 30 * 60:
                    return NewsContext.NEWS_CONTEXT

        return NewsContext.NO_NEWS_CONTEXT

    @staticmethod
    def derive_volume_context(
        volume: Optional[float],
        is_centralized_exchange: bool = False,
    ) -> Tuple[VolumeContext, Optional[float]]:
        """Distinguishes genuine exchange volume from Forex tick volume."""
        if volume is None or volume <= 0:
            return VolumeContext.NOT_AVAILABLE, None

        if is_centralized_exchange:
            return VolumeContext.GENUINE_VOLUME, volume
        else:
            return VolumeContext.TICK_VOLUME, volume

    # -------------------------------------------------------------------------
    # 9. Follow-Through Confirmation
    # -------------------------------------------------------------------------

    @staticmethod
    def evaluate_confirmation(
        rejection: RejectionObservation,
        current_close: float,
        future_candles: Optional[List[CandleMathMetrics]],
        as_of: Optional[datetime] = None,
    ) -> ConfirmationStatus:
        """
        Evaluates whether subsequent price action confirmed the rejection.
        Strict no-lookahead: future_candles must only include candles up to as_of.
        """
        if rejection in (RejectionObservation.NO_CLEAR_REJECTION, RejectionObservation.UNKNOWN):
            return ConfirmationStatus.NOT_APPLICABLE

        if not future_candles:
            return ConfirmationStatus.PENDING_CONFIRMATION

        next_candle = future_candles[0]

        if rejection == RejectionObservation.LOWER_PRICE_REJECTION:
            if next_candle.close > current_close:
                return ConfirmationStatus.CONFIRMED_FOLLOW_THROUGH
            else:
                return ConfirmationStatus.FAILED_FOLLOW_THROUGH

        elif rejection == RejectionObservation.UPPER_PRICE_REJECTION:
            if next_candle.close < current_close:
                return ConfirmationStatus.CONFIRMED_FOLLOW_THROUGH
            else:
                return ConfirmationStatus.FAILED_FOLLOW_THROUGH

        return ConfirmationStatus.UNKNOWN

    # -------------------------------------------------------------------------
    # 10. Pattern Taxonomies (IG and Groww Descriptive Labels)
    # -------------------------------------------------------------------------

    @staticmethod
    def detect_pattern_labels(
        candles: List[CandleMathMetrics],
        prior_trend: Optional[str] = None,
    ) -> List[PatternLabel]:
        """
        Identifies objective geometric candlestick patterns from IG and Groww taxonomies.
        Returned as research taxonomy labels only. Never converted into buy/sell signals.
        """
        if not candles:
            return [PatternLabel.NO_PATTERN]

        labels: List[PatternLabel] = []
        curr = candles[-1]
        rng = curr.range
        if rng <= 1e-12:
            return [PatternLabel.NO_PATTERN]

        body = curr.body_size
        u_wick = curr.upper_wick
        l_wick = curr.lower_wick
        body_pos = curr.body_position or 0.5
        is_bull = curr.close >= curr.open
        is_bear = curr.close < curr.open

        # --- Single-Candle Patterns ---

        # 1. Doji family
        if body / rng <= 0.10:
            if u_wick / rng <= 0.05 and l_wick / rng >= 0.70:
                labels.append(PatternLabel.DRAGONFLY_DOJI)
            elif l_wick / rng <= 0.05 and u_wick / rng >= 0.70:
                labels.append(PatternLabel.GRAVESTONE_DOJI)
            elif u_wick / rng >= 0.35 and l_wick / rng >= 0.35:
                labels.append(PatternLabel.LONG_LEGGED_DOJI)
            else:
                labels.append(PatternLabel.DOJI)

        # 2. Spinning Top
        if 0.10 < body / rng <= 0.30 and u_wick / rng >= 0.25 and l_wick / rng >= 0.25:
            labels.append(PatternLabel.SPINNING_TOP)

        # 3. Hammer & Hanging Man
        if body > 0 and l_wick >= 2.0 * body and u_wick / rng <= 0.12 and body_pos >= 0.65:
            if prior_trend and "DOWN" in prior_trend.upper():
                labels.append(PatternLabel.HAMMER)
            elif prior_trend and "UP" in prior_trend.upper():
                labels.append(PatternLabel.HANGING_MAN)
            else:
                labels.append(PatternLabel.HAMMER)

        # 4. Shooting Star & Inverted Hammer
        if body > 0 and u_wick >= 2.0 * body and l_wick / rng <= 0.12 and body_pos <= 0.35:
            if prior_trend and "UP" in prior_trend.upper():
                labels.append(PatternLabel.SHOOTING_STAR)
            elif prior_trend and "DOWN" in prior_trend.upper():
                labels.append(PatternLabel.INVERTED_HAMMER)
            else:
                labels.append(PatternLabel.SHOOTING_STAR)

        # 5. Bullish Belt Hold
        if is_bull and l_wick / rng <= 0.02 and body / rng >= 0.70:
            labels.append(PatternLabel.BULLISH_BELT_HOLD)

        # --- Two-Candle Patterns ---
        if len(candles) >= 2:
            prev = candles[-2]
            prev_bull = prev.close >= prev.open
            prev_bear = prev.close < prev.open

            # Bullish Engulfing
            if prev_bear and is_bull and curr.open <= prev.close and curr.close >= prev.open and body > prev.body_size:
                labels.append(PatternLabel.BULLISH_ENGULFING)

            # Bearish Engulfing
            if prev_bull and is_bear and curr.open >= prev.close and curr.close <= prev.open and body > prev.body_size:
                labels.append(PatternLabel.BEARISH_ENGULFING)

            # Tweezer Top (matching highs + upper wicks)
            if abs(curr.high - prev.high) / max(curr.high, 1e-8) <= 0.0005:
                if curr.upper_wick_ratio and curr.upper_wick_ratio >= 0.25 and prev.upper_wick_ratio and prev.upper_wick_ratio >= 0.25:
                    labels.append(PatternLabel.TWEEZER_TOP)

            # Tweezer Bottom (matching lows + lower wicks)
            if abs(curr.low - prev.low) / max(curr.low, 1e-8) <= 0.0005:
                if curr.lower_wick_ratio and curr.lower_wick_ratio >= 0.25 and prev.lower_wick_ratio and prev.lower_wick_ratio >= 0.25:
                    labels.append(PatternLabel.TWEEZER_BOTTOM)

            # Bullish Harami (large bear -> inside small bull)
            if prev_bear and is_bull and prev.body_size > body and curr.open >= prev.close and curr.close <= prev.open:
                labels.append(PatternLabel.BULLISH_HARAMI)

            # Bearish Harami (large bull -> inside small bear)
            if prev_bull and is_bear and prev.body_size > body and curr.open <= prev.close and curr.close >= prev.open:
                labels.append(PatternLabel.BEARISH_HARAMI)

            # Piercing Line
            if prev_bear and is_bull and curr.open < prev.low and curr.close > (prev.open + prev.close) / 2.0 and curr.close < prev.open:
                labels.append(PatternLabel.PIERCING_LINE)

            # Bullish Kicker
            if prev_bear and is_bull and curr.open >= prev.open and curr.low >= prev.high:
                labels.append(PatternLabel.BULLISH_KICKER)

            # Bearish Kicker
            if prev_bull and is_bear and curr.open <= prev.open and curr.high <= prev.low:
                labels.append(PatternLabel.BEARISH_KICKER)

            # Meeting Lines
            if prev_bull != is_bull and abs(curr.close - prev.close) / max(curr.close, 1e-8) <= 0.0005 and body > 0 and prev.body_size > 0:
                labels.append(PatternLabel.MEETING_LINES)

            # Inside Bar
            if curr.high <= prev.high and curr.low >= prev.low:
                labels.append(PatternLabel.INSIDE_BAR)

            # Bullish Separating Lines
            if prev_bear and is_bull and abs(curr.open - prev.open) / max(curr.open, 1e-8) <= 0.0005 and is_bull:
                labels.append(PatternLabel.BULLISH_SEPARATING_LINES)

        # --- Three-Candle Patterns ---
        if len(candles) >= 3:
            c1, c2, c3 = candles[-3], candles[-2], candles[-1]
            c1_bull, c1_bear = c1.close >= c1.open, c1.close < c1.open
            c3_bull, c3_bear = c3.close >= c3.open, c3.close < c3.open

            # Morning Star
            if c1_bear and c1.body_size > 0 and c2.body_size / max(c2.range, 1e-8) <= 0.35 and c3_bull:
                if c3.close > (c1.open + c1.close) / 2.0 and c2.close < c1.close:
                    labels.append(PatternLabel.MORNING_STAR)

            # Evening Star
            if c1_bull and c1.body_size > 0 and c2.body_size / max(c2.range, 1e-8) <= 0.35 and c3_bear:
                if c3.close < (c1.open + c1.close) / 2.0 and c2.close > c1.close:
                    labels.append(PatternLabel.EVENING_STAR)

            # Three White Soldiers
            if c1_bull and c2.close >= c2.open and c3_bull:
                if c1.close < c2.close < c3.close and c1.open < c2.open < c3.open:
                    if all((c.upper_wick / max(c.range, 1e-8)) <= 0.20 for c in (c1, c2, c3)):
                        labels.append(PatternLabel.THREE_WHITE_SOLDIERS)

            # Three Black Crows
            if c1_bear and c2.close < c2.open and c3_bear:
                if c1.close > c2.close > c3.close and c1.open > c2.open > c3.open:
                    if all((c.lower_wick / max(c.range, 1e-8)) <= 0.20 for c in (c1, c2, c3)):
                        labels.append(PatternLabel.THREE_BLACK_CROWS)

            # Three Inside Up
            if c1_bear and c2.close >= c2.open and c2.open >= c1.close and c2.close <= c1.open:
                if c3_bull and c3.close > c2.high:
                    labels.append(PatternLabel.THREE_INSIDE_UP)

            # Three Inside Down
            if c1_bull and c2.close < c2.open and c2.open <= c1.close and c2.close >= c1.open:
                if c3_bear and c3.close < c2.low:
                    labels.append(PatternLabel.THREE_INSIDE_DOWN)

            # Three Outside Up
            if c1_bear and c2.close >= c2.open and c2.open <= c1.close and c2.close >= c1.open:
                if c3_bull and c3.close > c2.close:
                    labels.append(PatternLabel.THREE_OUTSIDE_UP)

            # Three Outside Down
            if c1_bull and c2.close < c2.open and c2.open >= c1.close and c2.close <= c1.open:
                if c3_bear and c3.close < c2.close:
                    labels.append(PatternLabel.THREE_OUTSIDE_DOWN)

            # Abandoned Baby (Morning Star with gaps around doji)
            if c1_bear and c2.body_size / max(c2.range, 1e-8) <= 0.10 and c3_bull:
                if c2.high < c1.low and c2.high < c3.low:
                    labels.append(PatternLabel.ABANDONED_BABY)

        # --- Four-Candle Patterns ---
        if len(candles) >= 4:
            p1, p2, p3, p4 = candles[-4], candles[-3], candles[-2], candles[-1]
            # Three-Line Strike (Bullish strike)
            if p1.close >= p1.open and p2.close >= p2.open and p3.close >= p3.open and p4.close < p4.open:
                if p4.open >= p3.close and p4.close <= p1.open:
                    labels.append(PatternLabel.THREE_LINE_STRIKE)

            # Bearish Three-Line Strike
            if p1.close < p1.open and p2.close < p2.open and p3.close < p3.open and p4.close >= p4.open:
                if p4.open <= p3.close and p4.close >= p1.open:
                    labels.append(PatternLabel.BEARISH_THREE_LINE_STRIKE)

        # --- Five-Candle Patterns ---
        if len(candles) >= 5:
            b1, b2, b3, b4, b5 = candles[-5], candles[-4], candles[-3], candles[-2], candles[-1]
            # Rising Three Methods
            if b1.close >= b1.open and b1.body_size > 0 and b5.close >= b5.open:
                if all(c.close < c.open for c in (b2, b3, b4)):
                    if all(b1.low <= c.low and c.high <= b1.high for c in (b2, b3, b4)):
                        if b5.close > b1.high:
                            labels.append(PatternLabel.RISING_THREE_METHODS)

            # Mat Hold
            if b1.close >= b1.open and b5.close >= b5.open:
                if all(b1.low <= c.low for c in (b2, b3, b4)) and b5.close > b1.high:
                    if b2.open > b1.close:
                        labels.append(PatternLabel.MAT_HOLD)

        if not labels:
            labels.append(PatternLabel.NO_PATTERN)

        return labels

    # -------------------------------------------------------------------------
    # 11. Multi-Candle Sequence Observation
    # -------------------------------------------------------------------------

    @classmethod
    def observe_candle_sequence(cls, recent_maths: List[CandleMathMetrics]) -> CandleSequenceObservation:
        """
        Analyzes the rolling sequence across up to 5 preceding candles.
        Tracks body, wick, range, rejection, and momentum evolution.
        """
        count = len(recent_maths)
        if count < 2:
            return CandleSequenceObservation(
                window_size=count,
                body_evolution=BodyEvolution.UNKNOWN,
                candles_analyzed=count,
            )

        bodies = [m.body_size for m in recent_maths]
        wicks = [m.total_wick for m in recent_maths]
        ranges = [m.range for m in recent_maths]

        # Body evolution across window
        if bodies[-1] > bodies[0] * 1.25:
            body_evo = BodyEvolution.INCREASING
        elif bodies[-1] < bodies[0] * 0.75:
            body_evo = BodyEvolution.DECREASING
        else:
            body_evo = BodyEvolution.STABLE

        # Wick evolution across window
        if wicks[-1] > wicks[0] * 1.25:
            wick_evo = "EXPANDING"
        elif wicks[-1] < wicks[0] * 0.75:
            wick_evo = "CONTRACTING"
        else:
            wick_evo = "STABLE"

        # Range evolution
        if ranges[-1] > ranges[0] * 1.25:
            range_evo = "EXPANDING"
        elif ranges[-1] < ranges[0] * 0.75:
            range_evo = "CONTRACTING"
        else:
            range_evo = "STABLE"

        # Momentum evolution
        if body_evo == BodyEvolution.INCREASING and wick_evo != "EXPANDING":
            mom_evo = "MOMENTUM_STRENGTHENING"
        elif body_evo == BodyEvolution.DECREASING and wick_evo == "EXPANDING":
            mom_evo = "MOMENTUM_EXHAUSTION"
        else:
            mom_evo = "MOMENTUM_CONSOLIDATING"

        return CandleSequenceObservation(
            window_size=count,
            body_evolution=body_evo,
            wick_evolution=wick_evo,
            range_evolution=range_evo,
            rejection_evolution="ACTIVE" if wicks[-1] > ranges[-1] * 0.4 else "PASSIVE",
            momentum_evolution=mom_evo,
            sequence_stability="STABLE" if body_evo == BodyEvolution.STABLE else "VOLATILE",
            candles_analyzed=count,
        )

    # -------------------------------------------------------------------------
    # 12. Main Stateless Observation Entry Point
    # -------------------------------------------------------------------------

    def analyze_candle(
        self,
        current_candle: Any,
        historical_candles: Optional[List[Any]] = None,
        market_context: Optional[Dict[str, Any]] = None,
        future_candles: Optional[List[Any]] = None,
        as_of: Optional[datetime] = None,
    ) -> CandlestickResearchObservation:
        """
        Stateless, deterministic analysis of a candle in its market context.
        Zero lookahead: strictly filters historical candles by as_of.
        Returns an immutable, fully qualified CandlestickResearchObservation.
        """
        now = datetime.now(timezone.utc)
        eval_time = as_of or now
        ctx = market_context or {}

        # 1. Parse current candle OHLC
        o = getattr(current_candle, "open", current_candle.get("open") if isinstance(current_candle, dict) else 0.0)
        h = getattr(current_candle, "high", current_candle.get("high") if isinstance(current_candle, dict) else 0.0)
        l = getattr(current_candle, "low", current_candle.get("low") if isinstance(current_candle, dict) else 0.0)
        c = getattr(current_candle, "close", current_candle.get("close") if isinstance(current_candle, dict) else 0.0)
        t_raw = getattr(current_candle, "timestamp", current_candle.get("timestamp") if isinstance(current_candle, dict) else None)
        vol_raw = getattr(current_candle, "volume", current_candle.get("volume") if isinstance(current_candle, dict) else None)

        if isinstance(t_raw, datetime):
            c_timestamp = t_raw if t_raw.tzinfo else t_raw.replace(tzinfo=timezone.utc)
        elif isinstance(t_raw, (int, float)):
            c_timestamp = datetime.fromtimestamp(t_raw, tz=timezone.utc)
        else:
            c_timestamp = eval_time

        # Strict no-lookahead check: current candle timestamp cannot be strictly after as_of
        if as_of is not None and c_timestamp > as_of:
            c_timestamp = as_of

        math_metrics = self.calculate_candle_math(o, h, l, c)

        # 2. Filter historical reference candles: strictly prior to current candle and <= as_of
        ref_maths: List[CandleMathMetrics] = []
        if historical_candles:
            for hc in historical_candles:
                ho = getattr(hc, "open", hc.get("open") if isinstance(hc, dict) else 0.0)
                hh = getattr(hc, "high", hc.get("high") if isinstance(hc, dict) else 0.0)
                hl = getattr(hc, "low", hc.get("low") if isinstance(hc, dict) else 0.0)
                hc_close = getattr(hc, "close", hc.get("close") if isinstance(hc, dict) else 0.0)
                ht_raw = getattr(hc, "timestamp", hc.get("timestamp") if isinstance(hc, dict) else None)
                if isinstance(ht_raw, datetime):
                    ht = ht_raw if ht_raw.tzinfo else ht_raw.replace(tzinfo=timezone.utc)
                elif isinstance(ht_raw, (int, float)):
                    ht = datetime.fromtimestamp(ht_raw, tz=timezone.utc)
                else:
                    ht = None

                # Must precede current candle and respect as_of
                if as_of and ht and ht > as_of:
                    continue
                if ht and ht >= c_timestamp:
                    continue

                ref_maths.append(self.calculate_candle_math(ho, hh, hl, hc_close))

        # Use up to DEFAULT_LOOKBACK reference candles
        lookback_maths = ref_maths[-self.DEFAULT_LOOKBACK:] if ref_maths else []
        ref_bodies = [m.body_size for m in lookback_maths]
        ref_wicks = [m.total_wick for m in lookback_maths]
        ref_ranges = [m.range for m in lookback_maths]

        # 3. Body behaviour
        body_state = self.classify_body_state(math_metrics.body_size, ref_bodies)
        body_direction = self.classify_body_direction(math_metrics.open, math_metrics.close)
        prior_body = ref_bodies[-1] if ref_bodies else None
        prior_close = lookback_maths[-1].close if lookback_maths else None
        body_change, dir_sequence = self.classify_body_evolution(math_metrics.body_size, prior_body, body_direction)

        # 4. Wick behaviour
        upper_wick_state = self.classify_wick_state(math_metrics.upper_wick, math_metrics.range, ref_wicks)
        lower_wick_state = self.classify_wick_state(math_metrics.lower_wick, math_metrics.range, ref_wicks)
        wick_dominance = self.classify_wick_dominance(
            math_metrics.upper_wick, math_metrics.lower_wick, upper_wick_state, lower_wick_state, math_metrics.range
        )

        prior_wick = ref_wicks[-1] if ref_wicks else None
        wick_expansion = bool(prior_wick is not None and prior_wick > 1e-8 and math_metrics.total_wick > prior_wick * 1.20)
        wick_contraction = bool(prior_wick is not None and prior_wick > 1e-8 and math_metrics.total_wick < prior_wick * 0.80)

        cluster_maths = lookback_maths[-2:] + [math_metrics] if len(lookback_maths) >= 2 else []
        wick_cluster_state = self.observe_wick_clusters(cluster_maths)

        # 5. Rejection & Momentum
        rejection_obs = self.observe_rejection(math_metrics, wick_dominance)
        indecision_obs, momentum_obs = self.observe_momentum_and_indecision(
            math_metrics, body_state, wick_dominance, body_change
        )

        # 6. Context Observations
        trend_ctx = ctx.get("trend", "UNKNOWN")
        regime_ctx = ctx.get("regime", "UNKNOWN")
        news_events = ctx.get("economic_events", None)
        news_ctx = self.derive_news_context(c_timestamp, news_events)
        volatility_ctx = self.derive_volatility_context(math_metrics.range, ref_ranges, news_ctx)
        session_extremes = ctx.get("session_extremes", None)
        session_ctx = self.derive_session_context(c_timestamp, math_metrics, session_extremes)
        volume_ctx, vol_val = self.derive_volume_context(vol_raw, ctx.get("is_centralized_exchange", False))

        # 7. Structural Observations
        support_interaction = self.observe_structural_interaction(
            math_metrics,
            support_levels=ctx.get("support_levels"),
            resistance_levels=ctx.get("resistance_levels"),
            swing_highs=ctx.get("swing_highs"),
            swing_lows=ctx.get("swing_lows"),
            liquidity_zones=ctx.get("liquidity_zones"),
        )
        swing_interaction = support_interaction  # Normalized interaction representation
        liquidity_sweep_like = self.observe_liquidity_sweep_like(
            math_metrics,
            swing_high=ctx.get("prior_swing_high"),
            swing_low=ctx.get("prior_swing_low"),
        )

        # 8. Failed Breakout (T0 vs confirmation)
        future_maths: List[CandleMathMetrics] = []
        if future_candles:
            for fc in future_candles:
                fo = getattr(fc, "open", fc.get("open") if isinstance(fc, dict) else 0.0)
                fh = getattr(fc, "high", fc.get("high") if isinstance(fc, dict) else 0.0)
                fl = getattr(fc, "low", fc.get("low") if isinstance(fc, dict) else 0.0)
                fc_close = getattr(fc, "close", fc.get("close") if isinstance(fc, dict) else 0.0)
                ft_raw = getattr(fc, "timestamp", fc.get("timestamp") if isinstance(fc, dict) else None)
                if isinstance(ft_raw, datetime):
                    ft = ft_raw if ft_raw.tzinfo else ft_raw.replace(tzinfo=timezone.utc)
                elif isinstance(ft_raw, (int, float)):
                    ft = datetime.fromtimestamp(ft_raw, tz=timezone.utc)
                else:
                    ft = None

                # Enforce no lookahead on confirmation
                if as_of and ft and ft > as_of:
                    continue
                future_maths.append(self.calculate_candle_math(fo, fh, fl, fc_close))

        confirm_cand = future_maths[0] if future_maths else None
        failed_breakout = self.observe_failed_breakout(
            math_metrics,
            range_high=ctx.get("prior_range_high"),
            range_low=ctx.get("prior_range_low"),
            confirmation_candle=confirm_cand,
        )

        trend_pullback = self.observe_trend_pullback(math_metrics, rejection_obs, trend_ctx, prior_close)

        # 9. Pattern Taxonomies (IG & Groww)
        pattern_cand_window = lookback_maths[-4:] + [math_metrics] if lookback_maths else [math_metrics]
        pattern_labels = self.detect_pattern_labels(pattern_cand_window, prior_trend=trend_ctx)

        # 10. Confirmation Follow-Through
        confirmation_status = self.evaluate_confirmation(
            rejection_obs, math_metrics.close, future_maths, as_of=as_of
        )

        # 11. Multi-Candle Sequence Analysis
        seq_window = lookback_maths[-4:] + [math_metrics] if lookback_maths else [math_metrics]
        seq_obs = self.observe_candle_sequence(seq_window)

        # 12. Source Provenance Assembly
        source_prov = [SourceProvenance.PDF_BODY_WICK_FRAMEWORK, SourceProvenance.FXOPEN_WICK_ANALYSIS]
        if any(p in pattern_labels for p in (
            PatternLabel.HAMMER, PatternLabel.HANGING_MAN, PatternLabel.SHOOTING_STAR,
            PatternLabel.INVERTED_HAMMER, PatternLabel.DOJI, PatternLabel.BULLISH_ENGULFING,
            PatternLabel.BEARISH_ENGULFING, PatternLabel.TWEEZER_TOP, PatternLabel.TWEEZER_BOTTOM,
            PatternLabel.MORNING_STAR, PatternLabel.EVENING_STAR, PatternLabel.THREE_WHITE_SOLDIERS,
            PatternLabel.THREE_BLACK_CROWS, PatternLabel.INSIDE_BAR,
        )):
            source_prov.append(SourceProvenance.IG_PATTERN_TAXONOMY)

        if any(p in pattern_labels for p in (
            PatternLabel.PIERCING_LINE, PatternLabel.BULLISH_KICKER, PatternLabel.BEARISH_KICKER,
            PatternLabel.RISING_THREE_METHODS, PatternLabel.MAT_HOLD, PatternLabel.MEETING_LINES,
            PatternLabel.THREE_INSIDE_UP, PatternLabel.THREE_INSIDE_DOWN, PatternLabel.THREE_OUTSIDE_UP,
            PatternLabel.THREE_OUTSIDE_DOWN, PatternLabel.THREE_LINE_STRIKE, PatternLabel.BEARISH_THREE_LINE_STRIKE,
            PatternLabel.ABANDONED_BABY, PatternLabel.BULLISH_BELT_HOLD, PatternLabel.BULLISH_SEPARATING_LINES,
        )):
            source_prov.append(SourceProvenance.GROWW_PATTERN_TAXONOMY)

        return CandlestickResearchObservation(
            experiment_name=self.EXPERIMENT_NAME,
            experiment_version=self.EXPERIMENT_VERSION,
            evaluated_at=eval_time,
            as_of=as_of or eval_time,
            instrument=ctx.get(
                "instrument",
                (
                    current_candle.get("symbol", current_candle.get("instrument", "UNKNOWN"))
                    if isinstance(current_candle, dict)
                    else getattr(current_candle, "symbol", getattr(current_candle, "instrument", "UNKNOWN"))
                ),
            ),
            timeframe=ctx.get(
                "timeframe",
                (
                    current_candle.get("timeframe", "M15")
                    if isinstance(current_candle, dict)
                    else getattr(current_candle, "timeframe", "M15")
                ),
            ),
            candidate_id=ctx.get("candidate_id"),
            signal_id=ctx.get("signal_id"),
            strategy_id=ctx.get("strategy_id"),
            strategy_version=ctx.get("strategy_version"),
            source_provenance=list(set(source_prov)),
            open=math_metrics.open,
            high=math_metrics.high,
            low=math_metrics.low,
            close=math_metrics.close,
            range=math_metrics.range,
            body_size=math_metrics.body_size,
            body_ratio=math_metrics.body_ratio,
            upper_wick=math_metrics.upper_wick,
            lower_wick=math_metrics.lower_wick,
            upper_wick_ratio=math_metrics.upper_wick_ratio,
            lower_wick_ratio=math_metrics.lower_wick_ratio,
            total_wick=math_metrics.total_wick,
            wick_to_body_ratio=math_metrics.wick_to_body_ratio,
            body_position=math_metrics.body_position,
            body_state=body_state,
            body_direction=body_direction,
            body_change=body_change,
            directional_sequence=dir_sequence,
            upper_wick_state=upper_wick_state,
            lower_wick_state=lower_wick_state,
            wick_dominance=wick_dominance,
            wick_expansion=wick_expansion,
            wick_contraction=wick_contraction,
            wick_cluster_state=wick_cluster_state,
            rejection_observation=rejection_obs,
            indecision_observation=indecision_obs,
            momentum_observation=momentum_obs,
            support_resistance_interaction=support_interaction,
            swing_interaction=swing_interaction,
            liquidity_sweep_like_observation=liquidity_sweep_like,
            failed_breakout_observation=failed_breakout,
            trend_pullback_observation=trend_pullback,
            session_context=session_ctx,
            volatility_context=volatility_ctx,
            news_context=news_ctx,
            volume_context=volume_ctx,
            volume=vol_val,
            trend_context=trend_ctx,
            market_regime_context=regime_ctx,
            pattern_labels=pattern_labels,
            confirmation_status=confirmation_status,
            sequence_observation=seq_obs,
        )

    def get_candlestick_research_analytics(
        self,
        instrument: Optional[str] = None,
        timeframe: Optional[str] = None,
        pattern: Optional[str] = None,
        wick_type: Optional[str] = None,
        regime: Optional[str] = None,
        as_of: Optional[datetime] = None,
        limit: int = 100,
        observations: Optional[List[CandlestickResearchObservation]] = None,
        candles: Optional[List[Any]] = None,
    ) -> CandlestickResearchAnalyticsResponse:
        """
        Authoritative analytics query interface for candlestick and wick observations.
        Stateless, deterministic, read-only, and enforces zero lookahead.
        """
        as_of_effective = as_of if as_of is not None else datetime.now(timezone.utc)
        if as_of_effective.tzinfo is None:
            as_of_effective = as_of_effective.replace(tzinfo=timezone.utc)

        computed_obs: List[CandlestickResearchObservation] = []
        if observations:
            computed_obs = list(observations)
        elif candles:
            # Dynamically compute observations for provided candle sequence
            for i, c in enumerate(candles):
                history_window = candles[:i]
                obs = self.analyze_candle(c, historical_candles=history_window, as_of=as_of_effective)
                computed_obs.append(obs)
        elif instrument and timeframe:
            # Attempt to query historical candles safely from database if available
            try:
                from app.core.config.database import SessionLocal
                from app.repositories.market_repository import MarketRepository
                from app.models.market_candle import Timeframe

                tf_enum = None
                try:
                    tf_enum = Timeframe(timeframe.upper())
                except Exception:
                    pass

                if tf_enum:
                    db = SessionLocal()
                    try:
                        repo = MarketRepository(db)
                        fetched_candles = repo.get_history(
                            symbol=instrument.upper(),
                            timeframe=tf_enum,
                            end_time=as_of_effective,
                            limit=limit + self.DEFAULT_LOOKBACK,
                        )
                        if fetched_candles:
                            for i, c in enumerate(fetched_candles):
                                history_window = fetched_candles[:i]
                                obs = self.analyze_candle(c, historical_candles=history_window, as_of=as_of_effective)
                                computed_obs.append(obs)
                    finally:
                        db.close()
            except Exception:
                computed_obs = []

        # Filter strictly by parameters
        filtered: List[CandlestickResearchObservation] = []
        for obs in computed_obs:
            if obs.evaluated_at > as_of_effective:
                continue
            if instrument and obs.instrument.upper() != instrument.upper():
                continue
            if timeframe and obs.timeframe.upper() != timeframe.upper():
                continue
            if pattern:
                p_clean = pattern.upper()
                if not any(
                    (getattr(p, "value", str(p)).upper() == p_clean or getattr(p, "name", str(p)).upper() == p_clean)
                    for p in obs.pattern_labels
                ):
                    continue
            if wick_type:
                wt_clean = wick_type.upper()
                matches_wick = (
                    obs.upper_wick_state.value.upper() == wt_clean
                    or obs.lower_wick_state.value.upper() == wt_clean
                    or obs.wick_dominance.value.upper() == wt_clean
                    or obs.rejection_observation.value.upper() == wt_clean
                )
                if not matches_wick:
                    continue
            if regime:
                r_clean = regime.upper()
                if obs.market_regime_context.upper() != r_clean:
                    continue
            filtered.append(obs)

        # Respect limit
        sliced = filtered[:limit]

        filters_applied = {
            "instrument": instrument,
            "timeframe": timeframe,
            "pattern": pattern,
            "wick_type": wick_type,
            "regime": regime,
            "as_of": as_of_effective.isoformat(),
            "limit": limit,
        }

        return CandlestickResearchAnalyticsResponse(
            observations=sliced,
            total_observations=len(sliced),
            experiment_version=self.EXPERIMENT_VERSION,
            as_of=as_of_effective,
            filters_applied=filters_applied,
        )


# Singleton instance for stateless service calls
candlestick_research_service = CandlestickResearchService()

