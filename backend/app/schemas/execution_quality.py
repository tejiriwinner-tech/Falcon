"""
Falcon V10 Phase 5C: Execution Quality & Excursion Schemas.

Defines schemas for:
- Direction-aware price excursions (MFE / MAE in price points)
- Instrument-converted R excursions (MFE_R / MAE_R using authoritative initial monetary risk)
- Detailed per-trade execution quality metrics
- Descriptive aggregate execution quality summary
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class ExcursionPriceDetail(BaseModel):
    """Direction-aware price excursion in instrument price units."""
    symbol: str
    direction: str
    fillPrice: float
    peakPrice: float
    troughPrice: float
    mfePrice: float = Field(
        ...,
        description="Maximum Favorable Excursion in price points (peak - fill for BUY, fill - trough for SELL)",
    )
    maePrice: float = Field(
        ...,
        description="Maximum Adverse Excursion in price points (fill - trough for BUY, peak - fill for SELL)",
    )


class ExcursionRDetail(BaseModel):
    """Excursion denominated in R multiples of authoritative initial monetary risk."""
    mfeR: Optional[float] = Field(
        None, description="MFE denominated in R (monetary MFE / authoritative initial monetary risk)"
    )
    maeR: Optional[float] = Field(
        None, description="MAE denominated in R (monetary MAE / authoritative initial monetary risk)"
    )
    initialMonetaryRisk: Optional[Decimal] = Field(
        None, description="Authoritative initial monetary risk established at authorization"
    )
    hasAuthoritativeRisk: bool = Field(
        ..., description="True if initial monetary risk is present and strictly positive"
    )


class TradeExecutionQuality(BaseModel):
    """Descriptive execution and excursion measurements for a single trade."""
    tradeId: int
    signalId: Optional[int] = None
    symbol: str
    direction: str
    status: str
    result: str
    tradeDate: datetime
    fillTime: Optional[datetime] = None
    closeDate: Optional[datetime] = None

    # Timing
    signalToFillSeconds: Optional[float] = Field(
        None, description="Duration in seconds from signal/reservation creation (tradeDate) to fillTime"
    )

    # Pricing & Slippage
    entryPrice: float = Field(..., description="Requested/planned entry price from signal setup")
    fillPrice: Optional[float] = Field(None, description="Actual broker execution fill price")
    entrySlippagePrice: Optional[float] = Field(
        None,
        description="Execution slippage in price units: (fillPrice - entryPrice) for BUY, (entryPrice - fillPrice) for SELL",
    )
    entrySlippagePips: Optional[float] = Field(
        None, description="Execution slippage expressed in pips (instrument-scaled)"
    )

    # Context at Entry
    spreadAtEntry: Optional[float] = Field(
        None, description="Authoritative spread at entry from genuine signal context"
    )
    atrAtEntry: Optional[float] = Field(
        None, description="Authoritative ATR at entry from genuine signal context"
    )

    # Post-Fill Excursions
    peakPrice: Optional[float] = Field(None, description="Highest observed price after actual fill")
    troughPrice: Optional[float] = Field(None, description="Lowest observed price after actual fill")
    mfePrice: Optional[float] = Field(None, description="Maximum Favorable Excursion in price points")
    maePrice: Optional[float] = Field(None, description="Maximum Adverse Excursion in price points")
    mfeR: Optional[float] = Field(None, description="MFE denominated in R multiple")
    maeR: Optional[float] = Field(None, description="MAE denominated in R multiple")
    realizedRMultiple: Optional[float] = Field(None, description="Final realized R multiple")

    hasAuthoritativeFill: bool = Field(
        ..., description="True if fillTime and fillPrice are non-null"
    )
    hasAuthoritativeRisk: bool = Field(
        ..., description="True if initialMonetaryRisk is present and positive"
    )


class ExecutionQualitySummary(BaseModel):
    """
    Descriptive, non-ranking aggregate execution quality metrics.
    Exposes raw measurable facts without arbitrary good/bad scoring or ranking.
    """
    totalTradesEvaluated: int = Field(
        ..., description="Total trades considered in this analysis"
    )
    filledTradesCount: int = Field(
        ..., description="Count of trades with authoritative fill (fillPrice and fillTime)"
    )
    averageSignalToFillSeconds: Optional[float] = Field(
        None, description="Average seconds from signal creation to fill"
    )
    tradesWithSignalToFill: int = Field(
        ..., description="Count of trades with valid signal-to-fill duration"
    )

    averageSpreadAtEntry: Optional[float] = Field(
        None, description="Average spread at entry across trades where available"
    )
    tradesWithSpreadAtEntry: int = Field(
        ..., description="Count of trades with authoritative spread at entry"
    )

    averageAtrAtEntry: Optional[float] = Field(
        None, description="Average ATR at entry across trades where available"
    )
    tradesWithAtrAtEntry: int = Field(
        ..., description="Count of trades with authoritative ATR at entry"
    )

    averageEntrySlippagePips: Optional[float] = Field(
        None, description="Average entry slippage in pips"
    )
    tradesWithEntrySlippage: int = Field(
        ..., description="Count of trades with valid entry slippage calculation"
    )

    averageMfeR: Optional[float] = Field(
        None, description="Average MFE R across trades with valid R"
    )
    averageMaeR: Optional[float] = Field(
        None, description="Average MAE R across trades with valid R"
    )
    tradesWithMfeMaeR: int = Field(
        ..., description="Count of trades with authoritative MFE/MAE R"
    )

    historicalTradesExcludedCount: int = Field(
        ..., description="Count of historical trades where MFE/MAE are NULL and preserved without fabrication"
    )
    asOfTimestamp: Optional[datetime] = None
    generatedAt: datetime
