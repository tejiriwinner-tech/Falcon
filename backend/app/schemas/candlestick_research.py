"""
Falcon V10 — Candlestick & Wick Behaviour Research Schemas.

Defines the observational schemas for Phase 1 research experiment.
Strictly separates:
RAW CANDLE BEHAVIOUR -> BODY / WICK / POSITION / CONTEXT -> SEQUENCE -> OPTIONAL PATTERN LABEL.

All models are read-only research classifications.
Zero production signal, risk, or execution coupling.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Research Provenance Enums
# -----------------------------------------------------------------------------

class SourceProvenance(str, Enum):
    PDF_BODY_WICK_FRAMEWORK = "PDF_BODY_WICK_FRAMEWORK"
    FXOPEN_WICK_ANALYSIS = "FXOPEN_WICK_ANALYSIS"
    IG_PATTERN_TAXONOMY = "IG_PATTERN_TAXONOMY"
    GROWW_PATTERN_TAXONOMY = "GROWW_PATTERN_TAXONOMY"


# -----------------------------------------------------------------------------
# Body & Wick Behaviour Enums
# -----------------------------------------------------------------------------

class BodyDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class BodyState(str, Enum):
    VERY_SMALL = "VERY_SMALL"
    SMALL = "SMALL"
    NORMAL = "NORMAL"
    LARGE = "LARGE"
    VERY_LARGE = "VERY_LARGE"
    UNKNOWN = "UNKNOWN"


class BodyEvolution(str, Enum):
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"
    STABLE = "STABLE"
    UNKNOWN = "UNKNOWN"


class DirectionalSequence(str, Enum):
    BULLISH_BODY_EXPANSION = "BULLISH_BODY_EXPANSION"
    BEARISH_BODY_EXPANSION = "BEARISH_BODY_EXPANSION"
    BULLISH_BODY_CONTRACTION = "BULLISH_BODY_CONTRACTION"
    BEARISH_BODY_CONTRACTION = "BEARISH_BODY_CONTRACTION"
    DIRECTIONAL_BODY_STABILITY = "DIRECTIONAL_BODY_STABILITY"
    UNKNOWN = "UNKNOWN"


class WickState(str, Enum):
    NO_SIGNIFICANT_WICK = "NO_SIGNIFICANT_WICK"
    SMALL_WICK = "SMALL_WICK"
    NORMAL_WICK = "NORMAL_WICK"
    LARGE_WICK = "LARGE_WICK"
    EXTREME_WICK = "EXTREME_WICK"
    UNKNOWN = "UNKNOWN"


class WickDominance(str, Enum):
    UPPER_WICK_DOMINANT = "UPPER_WICK_DOMINANT"
    LOWER_WICK_DOMINANT = "LOWER_WICK_DOMINANT"
    BOTH_WICKS_LARGE = "BOTH_WICKS_LARGE"
    WICKS_BALANCED = "WICKS_BALANCED"
    UNKNOWN = "UNKNOWN"


class RejectionObservation(str, Enum):
    UPPER_PRICE_REJECTION = "UPPER_PRICE_REJECTION"
    LOWER_PRICE_REJECTION = "LOWER_PRICE_REJECTION"
    NO_CLEAR_REJECTION = "NO_CLEAR_REJECTION"
    UNKNOWN = "UNKNOWN"


class WickClusterState(str, Enum):
    WICK_CLUSTER = "WICK_CLUSTER"
    WICK_REJECTION_REPEATED = "WICK_REJECTION_REPEATED"
    WICK_REJECTION_STRENGTHENING = "WICK_REJECTION_STRENGTHENING"
    WICK_REJECTION_WEAKENING = "WICK_REJECTION_WEAKENING"
    NO_CLUSTER = "NO_CLUSTER"
    UNKNOWN = "UNKNOWN"


class TrendPullbackObservation(str, Enum):
    POSSIBLE_TREND_CONTINUATION_OBSERVATION = "POSSIBLE_TREND_CONTINUATION_OBSERVATION"
    NO_TREND_PULLBACK = "NO_TREND_PULLBACK"
    UNKNOWN = "UNKNOWN"


# -----------------------------------------------------------------------------
# Structural & Price-Action Enums
# -----------------------------------------------------------------------------

class StructuralInteraction(str, Enum):
    WICK_REJECTED_SUPPORT = "WICK_REJECTED_SUPPORT"
    WICK_REJECTED_RESISTANCE = "WICK_REJECTED_RESISTANCE"
    WICK_TESTED_SWING_HIGH = "WICK_TESTED_SWING_HIGH"
    WICK_TESTED_SWING_LOW = "WICK_TESTED_SWING_LOW"
    WICK_TESTED_LIQUIDITY_ZONE = "WICK_TESTED_LIQUIDITY_ZONE"
    NO_STRUCTURAL_INTERACTION = "NO_STRUCTURAL_INTERACTION"
    UNKNOWN = "UNKNOWN"


class FailedBreakoutObservation(str, Enum):
    FAILED_UPSIDE_BREAKOUT = "FAILED_UPSIDE_BREAKOUT"
    FAILED_DOWNSIDE_BREAKOUT = "FAILED_DOWNSIDE_BREAKOUT"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    NO_FAILED_BREAKOUT = "NO_FAILED_BREAKOUT"
    UNKNOWN = "UNKNOWN"


class LiquiditySweepLikeObservation(str, Enum):
    UPSIDE_LIQUIDITY_SWEEP_LIKE = "UPSIDE_LIQUIDITY_SWEEP_LIKE"
    DOWNSIDE_LIQUIDITY_SWEEP_LIKE = "DOWNSIDE_LIQUIDITY_SWEEP_LIKE"
    NO_LIQUIDITY_SWEEP_LIKE_EVENT = "NO_LIQUIDITY_SWEEP_LIKE_EVENT"
    UNKNOWN = "UNKNOWN"


# -----------------------------------------------------------------------------
# Context Enums
# -----------------------------------------------------------------------------

class SessionContext(str, Enum):
    ASIAN_SESSION_HIGH = "ASIAN_SESSION_HIGH"
    ASIAN_SESSION_LOW = "ASIAN_SESSION_LOW"
    LONDON_SESSION_HIGH = "LONDON_SESSION_HIGH"
    LONDON_SESSION_LOW = "LONDON_SESSION_LOW"
    NEW_YORK_SESSION_HIGH = "NEW_YORK_SESSION_HIGH"
    NEW_YORK_SESSION_LOW = "NEW_YORK_SESSION_LOW"
    WITHIN_SESSION_RANGE = "WITHIN_SESSION_RANGE"
    UNKNOWN = "UNKNOWN"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class VolatilityContext(str, Enum):
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    VOLATILITY_EXPANSION = "VOLATILITY_EXPANSION"
    VOLATILITY_SPIKE = "VOLATILITY_SPIKE"
    NEWS_VOLATILITY_CONTEXT = "NEWS_VOLATILITY_CONTEXT"
    UNKNOWN = "UNKNOWN"


class NewsContext(str, Enum):
    NEWS_CONTEXT = "NEWS_CONTEXT"
    NO_NEWS_CONTEXT = "NO_NEWS_CONTEXT"
    UNKNOWN = "UNKNOWN"


class VolumeContext(str, Enum):
    GENUINE_VOLUME = "GENUINE_VOLUME"
    TICK_VOLUME = "TICK_VOLUME"
    UNKNOWN = "UNKNOWN"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class ConfirmationStatus(str, Enum):
    CONFIRMED_FOLLOW_THROUGH = "CONFIRMED_FOLLOW_THROUGH"
    FAILED_FOLLOW_THROUGH = "FAILED_FOLLOW_THROUGH"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


# -----------------------------------------------------------------------------
# Candlestick Pattern Taxonomies (Descriptive Labels Only)
# -----------------------------------------------------------------------------

class PatternLabel(str, Enum):
    # Single-candle patterns
    HAMMER = "HAMMER"
    HANGING_MAN = "HANGING_MAN"
    SHOOTING_STAR = "SHOOTING_STAR"
    INVERTED_HAMMER = "INVERTED_HAMMER"
    DOJI = "DOJI"
    DRAGONFLY_DOJI = "DRAGONFLY_DOJI"
    GRAVESTONE_DOJI = "GRAVESTONE_DOJI"
    LONG_LEGGED_DOJI = "LONG_LEGGED_DOJI"
    SPINNING_TOP = "SPINNING_TOP"

    # Two-candle patterns
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    BEARISH_ENGULFING = "BEARISH_ENGULFING"
    TWEEZER_TOP = "TWEEZER_TOP"
    TWEEZER_BOTTOM = "TWEEZER_BOTTOM"
    BULLISH_HARAMI = "BULLISH_HARAMI"
    BEARISH_HARAMI = "BEARISH_HARAMI"
    PIERCING_LINE = "PIERCING_LINE"
    BULLISH_KICKER = "BULLISH_KICKER"
    BEARISH_KICKER = "BEARISH_KICKER"
    MEETING_LINES = "MEETING_LINES"

    # Three-candle patterns
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"
    THREE_WHITE_SOLDIERS = "THREE_WHITE_SOLDIERS"
    THREE_BLACK_CROWS = "THREE_BLACK_CROWS"
    INSIDE_BAR = "INSIDE_BAR"
    THREE_INSIDE_UP = "THREE_INSIDE_UP"
    THREE_INSIDE_DOWN = "THREE_INSIDE_DOWN"
    THREE_OUTSIDE_UP = "THREE_OUTSIDE_UP"
    THREE_OUTSIDE_DOWN = "THREE_OUTSIDE_DOWN"
    THREE_LINE_STRIKE = "THREE_LINE_STRIKE"
    BEARISH_THREE_LINE_STRIKE = "BEARISH_THREE_LINE_STRIKE"
    LADDER_BOTTOM = "LADDER_BOTTOM"
    ABANDONED_BABY = "ABANDONED_BABY"

    # Multi-candle patterns
    RISING_THREE_METHODS = "RISING_THREE_METHODS"
    MAT_HOLD = "MAT_HOLD"
    BULLISH_BELT_HOLD = "BULLISH_BELT_HOLD"
    BULLISH_SEPARATING_LINES = "BULLISH_SEPARATING_LINES"

    # Default / negative
    NO_PATTERN = "NO_PATTERN"
    UNKNOWN = "UNKNOWN"


# -----------------------------------------------------------------------------
# Candle Mathematics Model
# -----------------------------------------------------------------------------

class CandleMathMetrics(BaseModel):
    open: float
    high: float
    low: float
    close: float
    range: float
    body_size: float
    body_ratio: Optional[float] = None
    upper_wick: float
    lower_wick: float
    upper_wick_ratio: Optional[float] = None
    lower_wick_ratio: Optional[float] = None
    total_wick: float
    wick_to_body_ratio: Optional[float] = None
    body_position: Optional[float] = None  # Normalized 0.0 (low) to 1.0 (high)


# -----------------------------------------------------------------------------
# Sequence Observation Model
# -----------------------------------------------------------------------------

class CandleSequenceObservation(BaseModel):
    window_size: int = 5
    body_evolution: BodyEvolution = BodyEvolution.UNKNOWN
    wick_evolution: str = "UNKNOWN"
    range_evolution: str = "UNKNOWN"
    rejection_evolution: str = "UNKNOWN"
    momentum_evolution: str = "UNKNOWN"
    sequence_stability: str = "UNKNOWN"
    candles_analyzed: int = 0


# -----------------------------------------------------------------------------
# Full Research Observation Model
# -----------------------------------------------------------------------------

class CandlestickResearchObservation(BaseModel):
    """
    Comprehensive, immutable research observation of candlestick & wick behaviour.
    Contains zero trading decisions, zero weights, zero execution signals.
    """
    # Experiment Metadata & Provenance
    experiment_name: str = "CANDLE_BEHAVIOUR_EXPERIMENT"
    experiment_version: str = "1.0.0"
    evaluated_at: datetime
    as_of: datetime
    instrument: str
    timeframe: str
    candidate_id: Optional[str] = None
    signal_id: Optional[int] = None
    strategy_id: Optional[str] = None
    strategy_version: Optional[str] = None
    source_provenance: List[SourceProvenance] = Field(default_factory=list)

    # OHLC & Mathematics
    open: float
    high: float
    low: float
    close: float
    range: float
    body_size: float
    body_ratio: Optional[float] = None
    upper_wick: float
    lower_wick: float
    upper_wick_ratio: Optional[float] = None
    lower_wick_ratio: Optional[float] = None
    total_wick: float
    wick_to_body_ratio: Optional[float] = None
    body_position: Optional[float] = None

    # Body Analysis
    body_state: BodyState = BodyState.UNKNOWN
    body_direction: BodyDirection = BodyDirection.UNKNOWN
    body_change: BodyEvolution = BodyEvolution.UNKNOWN
    directional_sequence: DirectionalSequence = DirectionalSequence.UNKNOWN

    # Wick Analysis
    upper_wick_state: WickState = WickState.UNKNOWN
    lower_wick_state: WickState = WickState.UNKNOWN
    wick_dominance: WickDominance = WickDominance.UNKNOWN
    wick_expansion: bool = False
    wick_contraction: bool = False
    wick_cluster_state: WickClusterState = WickClusterState.UNKNOWN

    # Rejection & Momentum
    rejection_observation: RejectionObservation = RejectionObservation.UNKNOWN
    indecision_observation: bool = False
    momentum_observation: str = "UNKNOWN"

    # Structural & Price-Action Observations
    support_resistance_interaction: StructuralInteraction = StructuralInteraction.UNKNOWN
    swing_interaction: StructuralInteraction = StructuralInteraction.UNKNOWN
    liquidity_sweep_like_observation: LiquiditySweepLikeObservation = LiquiditySweepLikeObservation.UNKNOWN
    failed_breakout_observation: FailedBreakoutObservation = FailedBreakoutObservation.UNKNOWN
    trend_pullback_observation: TrendPullbackObservation = TrendPullbackObservation.UNKNOWN

    # Context Observations
    session_context: SessionContext = SessionContext.UNKNOWN
    volatility_context: VolatilityContext = VolatilityContext.UNKNOWN
    news_context: NewsContext = NewsContext.UNKNOWN
    volume_context: VolumeContext = VolumeContext.UNKNOWN
    volume: Optional[float] = None
    trend_context: str = "UNKNOWN"
    market_regime_context: str = "UNKNOWN"
    fib_context: str = "NOT_AVAILABLE"
    ma_context: str = "NOT_AVAILABLE"

    # Pattern Taxonomies & Confirmation
    pattern_labels: List[PatternLabel] = Field(default_factory=list)
    confirmation_status: ConfirmationStatus = ConfirmationStatus.UNKNOWN
    sequence_observation: Optional[CandleSequenceObservation] = None


# -----------------------------------------------------------------------------
# Analytics Response Model
# -----------------------------------------------------------------------------

class CandlestickResearchAnalyticsResponse(BaseModel):
    """
    Response schema for GET /api/v1/analytics/candlestick-behaviour.
    Strictly read-only, provenance-aware, and deterministic.
    """
    observations: List[CandlestickResearchObservation] = Field(default_factory=list)
    total_observations: int = 0
    experiment_version: str = "1.0.0"
    as_of: datetime
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
