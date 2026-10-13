"""
Falcon Pillar 1 — Session Breakout, Volume Expansion & Volatility Exhaustion Schemas.

Defines canonical Pydantic models for:
1. SessionRange (Asian Range, London Open Corridor, New York Overlap)
2. VolumeExpansionMarker (Relative Volume spikes >= 1.8x with directional spread expansion)
3. VolatilityExhaustionZone (2.5σ Keltner / Bollinger envelopes + mean reversion anchor)
4. SessionBreakoutStructureResponse & Conviction models
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class SessionName(str, Enum):
    ASIAN = "ASIAN"
    LONDON = "LONDON"
    NY_OVERLAP = "NY_OVERLAP"
    NEW_YORK = "NEW_YORK"


class SessionStatus(str, Enum):
    FORMING = "FORMING"
    INTACT = "INTACT"
    BROKEN_UP = "BROKEN_UP"
    BROKEN_DOWN = "BROKEN_DOWN"


class SessionRange(BaseModel):
    """Corridor boundaries for active and historical institutional trading sessions."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    session_name: SessionName = Field(..., description="ASIAN, LONDON, NY_OVERLAP, NEW_YORK")
    high: float = Field(..., description="High boundary of the session corridor")
    low: float = Field(..., description="Low boundary of the session corridor")
    open_price: float = Field(default=0.0, description="Session opening price")
    close_price: float = Field(default=0.0, description="Session closing price")
    status: SessionStatus = Field(default=SessionStatus.INTACT, description="Breakout status")
    range_pips: float = Field(default=0.0, description="Vertical span of session range in pips")
    start_time: Optional[Union[datetime, str]] = Field(default=None, description="Start time of the session")
    end_time: Optional[Union[datetime, str]] = Field(default=None, description="End time of the session")

    @property
    def mid_price(self) -> float:
        return round((self.high + self.low) / 2.0, 5)


class VolumeExpansionMarker(BaseModel):
    """Detected institutional volume expansion spike confirming momentum breakout."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    timestamp: Union[datetime, str] = Field(..., description="Candle timestamp of the volume surge")
    direction: str = Field(..., description="BULLISH or BEARISH")
    rvol: float = Field(..., ge=1.0, description="Relative Volume vs 20-period SMA (e.g. 2.1x)")
    breakout_price: float = Field(..., description="Closing price executing the expansion")
    target_price: float = Field(..., description="Projected expansion objective (1.5x - 2.0x session range)")
    invalidation_price: float = Field(..., description="Opposite boundary invalidation level")
    spread_ratio: float = Field(default=1.0, description="Candle body to total range ratio (>0.60 confirms conviction)")


class VolatilityExhaustionZone(BaseModel):
    """Statistical volatility envelope (2.5σ Keltner / Bollinger) identifying mean reversion."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    upper_band: float = Field(..., description="2.5-3.0σ upper exhaustion ceiling")
    lower_band: float = Field(..., description="2.5-3.0σ lower exhaustion floor")
    mean_level: float = Field(..., description="20 EMA / volume-weighted mean reversion target")
    current_sigma: float = Field(default=0.0, description="Current price deviation in standard deviations")
    is_exhausted: bool = Field(default=False, description="Whether price has pierced the outer threshold")
    exhaustion_state: str = Field(default="NORMAL", description="OVERBOUGHT_EXHAUSTION, OVERSOLD_EXHAUSTION, NORMAL")
    rsi_value: Optional[float] = Field(default=None, description="Relative Strength Index value (extremes >75 or <25)")


class ConvictionBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class CompositeConvictionScore(BaseModel):
    """Composite Conviction Score (0-100%) synthesizing session breakout and volatility metrics."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    total_score: float = Field(..., ge=0.0, le=100.0, description="Overall conviction score 0-100%")
    session_momentum_score: float = Field(..., description="Session breakout and corridor alignment contribution")
    volume_expansion_score: float = Field(..., description="Relative volume spike (RVol >= 1.8x) contribution")
    volatility_exhaustion_score: float = Field(..., description="Statistical volatility and mean reversion alignment")
    correlation_score: float = Field(..., description="Macro/DXY correlation contribution")
    spread_penalty: float = Field(..., description="Spread deduction penalty")
    macro_news_penalty: float = Field(default=0.0, description="Macro high-impact news blackout penalty")
    htf_alignment_score: float = Field(default=0.0, description="Higher-timeframe trend alignment contribution (bonus or penalty)")
    htf_trend_bias: Optional[str] = Field(default="NEUTRAL", description="BULLISH, BEARISH, or NEUTRAL macro bias")
    symbol: Optional[str] = Field(default=None, description="Instrument identifier")
    bias: ConvictionBias = Field(..., description="BULLISH, BEARISH, or NEUTRAL")
    key_reasons: List[str] = Field(default_factory=list, description="Key institutional rationale bullet points")


class SessionBreakoutStructureResponse(BaseModel):
    """Consolidated market structure response for session corridors, volume spikes, and volatility bands."""
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    symbol: str = Field(..., description="Instrument identifier")
    timeframe: str = Field(..., description="Timeframe")
    session_ranges: List[SessionRange] = Field(default_factory=list, description="Active and historical session corridors")
    volume_expansions: List[VolumeExpansionMarker] = Field(default_factory=list, description="Volume expansion triggers")
    volatility_zone: Optional[VolatilityExhaustionZone] = Field(default=None, description="Statistical volatility envelope")
    active_session: str = Field(default="LONDON", description="Currently active market session")
    is_breakout_confirmed: bool = Field(default=False, description="True if volume-confirmed session breakout occurred")
    # Quantitative Breakthrough Enhancements
    htf_trend_bias: Optional[str] = Field(default="NEUTRAL", description="H4/D1 50/200 EMA Macro Trend Bias (BULLISH, BEARISH, NEUTRAL)")
    htf_ema_50: Optional[float] = Field(default=None, description="Higher-timeframe 50-period Exponential Moving Average")
    htf_ema_200: Optional[float] = Field(default=None, description="Higher-timeframe 200-period Exponential Moving Average")
    atr_14: Optional[float] = Field(default=None, description="14-period Average True Range for dynamic volatility stop buffer")
    suggested_tp1: Optional[float] = Field(default=None, description="Scale-out Target 1 (Bank 50% @ 1.5R)")
    suggested_tp2: Optional[float] = Field(default=None, description="Runner Target 2 (Trail 50% @ 3.0R+)")
    trailing_stop_buffer: Optional[float] = Field(default=None, description="Dynamic trailing buffer (1.0x ATR)")
