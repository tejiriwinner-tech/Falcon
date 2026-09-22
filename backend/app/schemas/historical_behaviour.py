"""
Falcon V10 — Historical Behaviour Analysis Schemas (Phase 2).

Defines research-only data contracts for measuring subsequent price behaviour
following Phase 1 candlestick and wick observations.

Strict separation:
OBSERVATION DATA (at or before T0) -> FORWARD OUTCOME WINDOW (strictly T1...TH <= as_of).
Descriptive research evidence only; zero production trading decisions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.candlestick_research import CandlestickResearchObservation


# -----------------------------------------------------------------------------
# Research Categorical Enums
# -----------------------------------------------------------------------------

class DirectionalBias(str, Enum):
    """
    Descriptive directional bias derived from the observation geometry.
    Purely observational; never a trade signal.
    """
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class SubsequentDirection(str, Enum):
    """
    Descriptive classification of subsequent price movement relative to directional bias.
    Evaluated using the versioned noise band (0.20 * reference_range).
    """
    FOLLOW_THROUGH = "FOLLOW_THROUGH"
    PARTIAL_FOLLOW_THROUGH = "PARTIAL_FOLLOW_THROUGH"
    REVERSAL = "REVERSAL"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class ContinuationState(str, Enum):
    """
    Descriptive classification of whether the prevailing trend continued or reversed.
    """
    CONTINUATION = "CONTINUATION"
    REVERSAL = "REVERSAL"
    MIXED = "MIXED"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class SampleAdequacy(str, Enum):
    """
    Explicit research sample adequacy state.
    ADEQUATE (>= 30), LIMITED (10..29), INSUFFICIENT (< 10), UNKNOWN (0).
    """
    ADEQUATE = "ADEQUATE"
    LIMITED = "LIMITED"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class DataQuality(str, Enum):
    """
    Data quality and integrity status for historical candle sequences.
    """
    VALID = "VALID"
    INCOMPLETE = "INCOMPLETE"
    INVALID = "INVALID"
    FORWARD_DATA_GAP = "FORWARD_DATA_GAP"
    UNKNOWN = "UNKNOWN"


# -----------------------------------------------------------------------------
# Forward Window Outcome Metrics
# -----------------------------------------------------------------------------

class ForwardWindowMetrics(BaseModel):
    """
    Subsequent price behaviour measured strictly within forward window [T1 ... TH].
    Never includes T0.
    """
    horizon_candles: int
    reference_price: float  # T0 close price
    forward_close: Optional[float] = None  # Price at TH close
    raw_return: Optional[float] = None  # forward_close - reference_price
    raw_return_percent: Optional[float] = None
    directional_bias: DirectionalBias = DirectionalBias.UNKNOWN
    directional_return: Optional[float] = None  # Aligned with observation bias
    directional_return_percent: Optional[float] = None
    mfe: Optional[float] = None  # Maximum Favourable Excursion
    mae: Optional[float] = None  # Maximum Adverse Excursion
    mfe_percent: Optional[float] = None
    mae_percent: Optional[float] = None
    mfe_offset: Optional[int] = None  # 1-indexed offset inside [1..H]
    mae_offset: Optional[int] = None  # 1-indexed offset inside [1..H]
    subsequent_direction: SubsequentDirection = SubsequentDirection.UNKNOWN
    continuation_state: ContinuationState = ContinuationState.UNKNOWN
    candles_to_favourable_move: Optional[int] = None
    candles_to_adverse_move: Optional[int] = None
    volatility_normalized_return: Optional[float] = None  # return / ref_range
    volatility_normalized_mfe: Optional[float] = None  # mfe / ref_range
    volatility_normalized_mae: Optional[float] = None  # mae / ref_range
    noise_band: Optional[float] = None  # 0.20 * ref_range
    data_quality: DataQuality = DataQuality.VALID


# -----------------------------------------------------------------------------
# Combined Historical Observation Model
# -----------------------------------------------------------------------------

class HistoricalBehaviourObservation(BaseModel):
    """
    Comprehensive historical observation binding a T0 Phase 1 observation
    with measured subsequent forward outcomes across configured horizons.
    """
    observation_id: str
    instrument: str
    timeframe: str
    observation_time: datetime  # T0 close timestamp
    evaluated_at: datetime
    as_of: datetime
    phase_1_version: str = "1.0.0"
    phase_2_version: str = "1.0.0"
    candle_observation: CandlestickResearchObservation
    forward_windows: Dict[int, ForwardWindowMetrics] = Field(default_factory=dict)
    primary_forward_metric: Optional[ForwardWindowMetrics] = None
    data_quality: DataQuality = DataQuality.VALID


# -----------------------------------------------------------------------------
# Descriptive Statistics & Distributions
# -----------------------------------------------------------------------------

class DescriptiveStatistics(BaseModel):
    """
    Descriptive, non-ranking summary statistics for an observation population.
    """
    sample_size: int = 0
    sample_adequacy: SampleAdequacy = SampleAdequacy.UNKNOWN
    mean_raw_return: Optional[float] = None
    median_raw_return: Optional[float] = None
    mean_directional_return: Optional[float] = None
    median_directional_return: Optional[float] = None
    min_return: Optional[float] = None
    max_return: Optional[float] = None
    std_dev_return: Optional[float] = None
    mean_mfe: Optional[float] = None
    median_mfe: Optional[float] = None
    mean_mae: Optional[float] = None
    median_mae: Optional[float] = None
    mean_candles_to_mfe: Optional[float] = None
    mean_candles_to_mae: Optional[float] = None
    follow_through_count: int = 0
    follow_through_rate: float = 0.0
    reversal_count: int = 0
    reversal_rate: float = 0.0
    neutral_count: int = 0
    neutral_rate: float = 0.0
    unknown_count: int = 0


class DistributionMetrics(BaseModel):
    """
    Distribution-first percentile metrics preventing distortion from outliers.
    """
    percentiles_return: Dict[str, Optional[float]] = Field(default_factory=dict)
    percentiles_mfe: Dict[str, Optional[float]] = Field(default_factory=dict)
    percentiles_mae: Dict[str, Optional[float]] = Field(default_factory=dict)
    positive_outcome_ratio: float = 0.0
    negative_outcome_ratio: float = 0.0


# -----------------------------------------------------------------------------
# API Response Schemas
# -----------------------------------------------------------------------------

class HistoricalBehaviourAnalyticsResponse(BaseModel):
    """
    Full response schema for GET /api/v1/analytics/candlestick-behaviour/history.
    Strictly read-only, non-persistent, and deterministic.
    """
    experiment_name: str = "HISTORICAL_BEHAVIOUR_ANALYSIS"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    research_methodology_version: str = "1.0.0"
    noise_band_multiplier: float = 0.20
    as_of: datetime
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
    forward_window: int = 5
    sample_size: int = 0
    sample_status: SampleAdequacy = SampleAdequacy.UNKNOWN
    statistics: DescriptiveStatistics = Field(default_factory=DescriptiveStatistics)
    distribution: DistributionMetrics = Field(default_factory=DistributionMetrics)
    breakdowns: Dict[str, Any] = Field(default_factory=dict)
    observations: List[HistoricalBehaviourObservation] = Field(default_factory=list)


class HistoricalBehaviourSummaryResponse(BaseModel):
    """
    Compact summary response schema for GET /api/v1/analytics/candlestick-behaviour/history/summary.
    Omits the large raw observations list for fast operational dashboard queries.
    """
    experiment_name: str = "HISTORICAL_BEHAVIOUR_ANALYSIS"
    experiment_version: str = "1.0.0"
    phase_1_version: str = "1.0.0"
    research_methodology_version: str = "1.0.0"
    noise_band_multiplier: float = 0.20
    as_of: datetime
    filters_applied: Dict[str, Any] = Field(default_factory=dict)
    forward_window: int = 5
    sample_size: int = 0
    sample_status: SampleAdequacy = SampleAdequacy.UNKNOWN
    statistics: DescriptiveStatistics = Field(default_factory=DescriptiveStatistics)
    distribution: DistributionMetrics = Field(default_factory=DistributionMetrics)
    breakdowns: Dict[str, Any] = Field(default_factory=dict)
