"""
Falcon Pillar 1 — SMC Institutional Perception Schemas.

Defines canonical Pydantic models for Smart Money Concepts (SMC) & Institutional Perception:
1. OrderBlock & OrderBlockType
2. FairValueGap & FairValueGapType
3. LiquiditySweep & SweepType
4. SessionLevels
5. CompositeConvictionScore & ConvictionBias
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class OrderBlockType(str, Enum):
    """Institutional Order Block classification."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class OrderBlock(BaseModel):
    """
    Institutional Order Block.
    
    Represents the last opposing candle before aggressive displacement
    breaking market structure (swing high or swing low).
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    symbol: str = Field(..., description="Instrument identifier (e.g., EURUSD, XAUUSD)")
    timeframe: str = Field(..., description="Timeframe of the structure (e.g., 5m, 15m, 1h)")
    block_type: OrderBlockType = Field(..., description="BULLISH (demand) or BEARISH (supply)")
    high: float = Field(..., description="Top boundary of the order block candle")
    low: float = Field(..., description="Bottom boundary of the order block candle")
    open_price: float = Field(..., description="Open price of the order block candle")
    close_price: float = Field(..., description="Close price of the order block candle")
    volume: float = Field(default=0.0, description="Volume of the order block candle")
    is_mitigated: bool = Field(default=False, description="Whether subsequent price action has re-entered the block")
    formed_at: Optional[Union[datetime, int, float, str]] = Field(
        default=None, description="Timestamp or index when the order block candle closed"
    )

    @property
    def is_bullish(self) -> bool:
        return self.block_type == OrderBlockType.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.block_type == OrderBlockType.BEARISH

    @property
    def range(self) -> float:
        return max(self.high - self.low, 0.0)

    @property
    def mid_price(self) -> float:
        return (self.high + self.low) / 2.0


class FairValueGapType(str, Enum):
    """Institutional Fair Value Gap classification."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class FairValueGap(BaseModel):
    """
    Institutional Fair Value Gap (FVG / Imbalance).
    
    Identified by a 3-bar sequence:
    - Bullish FVG: Bar 1 High < Bar 3 Low (imbalance between Bar 1 High and Bar 3 Low)
    - Bearish FVG: Bar 1 Low > Bar 3 High (imbalance between Bar 3 High and Bar 1 Low)
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    symbol: str = Field(..., description="Instrument identifier")
    timeframe: str = Field(..., description="Timeframe of the gap")
    gap_type: FairValueGapType = Field(..., description="BULLISH or BEARISH FVG")
    top: float = Field(..., description="Upper price boundary of the imbalance")
    bottom: float = Field(..., description="Lower price boundary of the imbalance")
    size_pips: float = Field(..., description="Imbalance width denominated in pips")
    is_mitigated: bool = Field(default=False, description="Whether subsequent candles have retraced into the gap")
    bar1_time: Optional[Union[datetime, int, float, str]] = Field(
        default=None, description="Timestamp or index of Bar 1"
    )
    bar3_time: Optional[Union[datetime, int, float, str]] = Field(
        default=None, description="Timestamp or index of Bar 3"
    )

    @property
    def is_bullish(self) -> bool:
        return self.gap_type == FairValueGapType.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.gap_type == FairValueGapType.BEARISH

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0


class SweepType(str, Enum):
    """Liquidity sweep direction."""
    HIGH_SWEEP = "HIGH_SWEEP"
    LOW_SWEEP = "LOW_SWEEP"


# Alias for compatibility
LiquiditySweepType = SweepType


class LiquiditySweep(BaseModel):
    """
    Session Liquidity Sweep (Judas Swing / Turtle Soup).
    
    Identifies manipulation wicks that pierce above/below prior session extremes
    (Asian, London, NY) and close back inside the session boundary.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    symbol: str = Field(..., description="Instrument identifier")
    session_name: str = Field(..., description="Swept session name (e.g., ASIAN, LONDON, NEW_YORK)")
    sweep_type: SweepType = Field(..., description="HIGH_SWEEP or LOW_SWEEP")
    swept_level: float = Field(..., description="The session boundary price that was breached")
    sweep_wick_extreme: float = Field(..., description="The maximum price reached by the wick beyond the level")
    candle_close_inside: Union[bool, float] = Field(
        default=True,
        description="True indicating candle closed back inside session range (or closing price inside)",
    )
    timestamp: Optional[Union[datetime, int, float, str]] = Field(
        default=None, description="Timestamp of the sweeping candle"
    )
    close_price: Optional[float] = Field(
        default=None, description="Optional exact close price of the sweeping candle"
    )

    @property
    def is_high_sweep(self) -> bool:
        return self.sweep_type == SweepType.HIGH_SWEEP

    @property
    def is_low_sweep(self) -> bool:
        return self.sweep_type == SweepType.LOW_SWEEP

    @property
    def penetration_distance(self) -> float:
        return abs(self.sweep_wick_extreme - self.swept_level)


class SessionLevels(BaseModel):
    """
    Session High/Low reference bounds.
    
    Represents key reference levels defined during Asian, London, or New York sessions.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    session_name: str = Field(..., description="Session identifier (e.g., ASIAN, LONDON, NEW_YORK)")
    high: float = Field(..., description="Session high boundary")
    low: float = Field(..., description="Session low boundary")
    open_price: float = Field(..., description="Session opening price")
    close_price: float = Field(..., description="Session closing price")
    start_time: Optional[Union[datetime, int, float, str]] = Field(
        default=None, description="Session opening timestamp"
    )
    end_time: Optional[Union[datetime, int, float, str]] = Field(
        default=None, description="Session closing timestamp"
    )

    @property
    def session_range(self) -> float:
        return max(self.high - self.low, 0.0)

    @property
    def mid_price(self) -> float:
        return (self.high + self.low) / 2.0


class ConvictionBias(str, Enum):
    """Directional bias produced by composite conviction calculation."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class CompositeConvictionScore(BaseModel):
    """
    Composite Conviction Score (0-100%).
    
    Synthesizes:
    - SMC structural alignment (Order Blocks, FVGs, Sweeps)
    - Candlestick / Sniper pattern execution triggers
    - Institutional Session Timing & Killzones
    - Macro & DXY correlation
    - Live spread frictions and penalties
    """
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    total_score: float = Field(..., ge=0.0, le=100.0, description="Overall conviction score 0-100%")
    smc_alignment_score: float = Field(..., description="SMC structural alignment contribution")
    sniper_pattern_score: float = Field(..., description="Sniper pattern execution contribution")
    session_timing_score: float = Field(..., description="Session timing and killzone contribution")
    correlation_score: float = Field(..., description="DXY/Macro correlation confluence contribution")
    spread_penalty: float = Field(..., description="Spread deduction penalty")
    bias: ConvictionBias = Field(..., description="BULLISH, BEARISH, or NEUTRAL")
    key_reasons: List[str] = Field(default_factory=list, description="Key institutional rationale bullet points")
