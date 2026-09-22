"""
Falcon V10 Phase 5B: Canonical Performance Analytics Schemas.

Provides single authoritative schemas for:
- Lifecycle & mutually-exclusive trade populations
- Closed trade outcomes (wins, losses, breakevens)
- Canonical win rate with explicit zero-denominator handling
- Authoritative realized R metrics (sourced exclusively from persisted initial risk)
- Holding duration vs pending latency duration
- Trade-by-trade closed equity curve & chronological drawdown
- Active cycle measurement (isolated protected profit, cycle starting capital)
- Descriptive, non-ranking strategy performance metrics
- As-of timestamp filtering
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class LifecyclePopulations(BaseModel):
    """
    Trade & setup populations.
    Note: Current status populations (pending, open, closed, expired, invalidated)
    are mutually exclusive partitions of trade journal records.
    Evaluated setups and authorized reservations represent lifecycle event counts.
    """
    evaluatedSetupsCount: int = Field(
        ..., description="Total setup candidates generated across missions by strategy pipeline"
    )
    authorizedReservationsCount: int = Field(
        ..., description="Total trades authorized by Capital Guardian with committed reservations"
    )
    pendingCount: int = Field(
        ..., description="Current pending untriggered reservations"
    )
    openCount: int = Field(
        ..., description="Current active filled trades (OPEN)"
    )
    closedCount: int = Field(
        ..., description="Terminal closed trades with realized outcome"
    )
    expiredCount: int = Field(
        ..., description="Untriggered reservations that expired (NOT trading losses)"
    )
    invalidatedCount: int = Field(
        ..., description="Untriggered reservations invalidated prior to fill (NOT trading losses)"
    )


class ClosedOutcomeCounts(BaseModel):
    """Counts for closed trades only."""
    wins: int = Field(..., description="Closed trades with positive outcome (result WIN/WON or profit > 0)")
    losses: int = Field(..., description="Closed trades with loss outcome (result LOSS/LOST or profit < 0)")
    breakevens: int = Field(..., description="Closed trades with breakeven outcome (result BREAKEVEN/BE or profit == 0)")
    totalClosed: int = Field(..., description="Total terminal closed trades (wins + losses + breakevens)")


class CanonicalWinRate(BaseModel):
    """Canonical win rate definition: wins / (wins + losses + breakevens)."""
    winRate: Optional[float] = Field(
        None, description="Win rate ratio (0.0 to 1.0), or None if denominator is 0"
    )
    winRatePercent: Optional[float] = Field(
        None, description="Win rate percentage (0.0% to 100.0%), or None if denominator is 0"
    )
    hasSufficientData: bool = Field(
        ..., description="True if denominator > 0 (at least one closed trade)"
    )
    formula: str = Field(
        default="wins / (wins + losses + breakevens)",
        description="Authoritative win rate formula string",
    )


class RealizedRMetrics(BaseModel):
    """Authoritative realized R metrics derived exclusively from persisted initial monetary risk."""
    totalRealizedR: Optional[float] = Field(
        None, description="Sum of realized R multiples across trades with valid initial risk"
    )
    averageRealizedR: Optional[float] = Field(
        None, description="Average realized R multiple for trades with valid initial risk, or None"
    )
    tradesWithRealizedR: int = Field(
        ..., description="Count of closed trades with valid non-null realized_r_multiple"
    )
    missingRealizedRCount: int = Field(
        ..., description="Count of closed trades where realized_r_multiple is NULL (not established)"
    )
    positiveRCount: int = Field(..., description="Count of trades with realized R > 0")
    negativeRCount: int = Field(..., description="Count of trades with realized R < 0")
    zeroRCount: int = Field(..., description="Count of trades with realized R == 0.0")


class HoldingDurationMetrics(BaseModel):
    """Holding time (fill_time -> close_date) vs pending wait duration (trade_date -> fill_time or close_date)."""
    averageHoldingDurationSeconds: Optional[float] = Field(
        None, description="Average market exposure duration in seconds (close_date - fill_time)"
    )
    averageHoldingDurationMinutes: Optional[float] = Field(
        None, description="Average market exposure duration in minutes"
    )
    tradesWithValidHoldingDuration: int = Field(
        ..., description="Count of closed trades with non-null fill_time and close_date"
    )
    averagePendingDurationSeconds: Optional[float] = Field(
        None, description="Average trigger wait duration in seconds (fill_time - trade_date)"
    )
    averagePendingDurationMinutes: Optional[float] = Field(
        None, description="Average trigger wait duration in minutes"
    )
    tradesWithValidPendingDuration: int = Field(
        ..., description="Count of filled trades with valid trade_date and fill_time"
    )
    averageUntriggeredDurationMinutes: Optional[float] = Field(
        None, description="Average duration before untriggered cancellation for expired/invalidated trades"
    )


class EquityCurvePoint(BaseModel):
    """Single point along chronological closed trade equity curve."""
    tradeId: int
    closeDate: datetime
    symbol: str
    direction: str
    result: str
    profitLoss: float
    realizedRMultiple: Optional[float]
    cumulativePnL: float
    equity: float
    peakEquity: float
    drawdown: float
    drawdownPercent: Optional[float]


class ActiveCycleMetrics(BaseModel):
    """Measurement for the active capital cycle without mutating cycle state."""
    hasActiveCycle: bool
    cycleId: Optional[str] = None
    cycleNumber: Optional[int] = None
    startingCapital: Optional[float] = None
    activeTradingCapital: Optional[float] = None
    protectedProfit: Optional[float] = None
    cycleClosedTradesCount: int = 0
    cycleWins: int = 0
    cycleLosses: int = 0
    cycleBreakevens: int = 0
    cycleWinRate: Optional[float] = None
    cycleRealizedPnL: float = 0.0
    cycleMaxDrawdown: float = 0.0
    cycleMaxDrawdownPercent: Optional[float] = None
    qualification: str = Field(
        default="Measured on trades closed since cycle started_at. Protected profit strictly excluded from equity.",
        description="Explicit scope qualification",
    )


class StrategyPerformanceMetrics(BaseModel):
    """Descriptive, non-ranking performance metrics for an individual strategy."""
    strategyId: str
    strategyVersion: Optional[str] = Field(
        None, description="Authoritative strategy version associated with trades"
    )
    closedTradesCount: int
    wins: int
    losses: int
    breakevens: int
    winRate: Optional[float]
    netProfitLoss: float
    totalRealizedR: Optional[float]
    averageRealizedR: Optional[float]
    tradesWithRealizedR: int
    maxDrawdown: float
    maxDrawdownPercent: Optional[float]
    averageHoldingMinutes: Optional[float]
    hasSufficientData: bool = Field(
        ..., description="True if closedTradesCount >= 5 (descriptive statistical threshold only)"
    )


class CanonicalAnalyticsResponse(BaseModel):
    """Complete canonical performance analytics response."""
    populations: LifecyclePopulations
    closedOutcomes: ClosedOutcomeCounts
    winRate: CanonicalWinRate
    realizedR: RealizedRMetrics
    durations: HoldingDurationMetrics
    activeCycle: ActiveCycleMetrics
    equityCurve: List[EquityCurvePoint]
    maxDrawdown: float
    maxDrawdownPercent: Optional[float]
    strategies: List[StrategyPerformanceMetrics]
    executionMode: Optional[str] = None
    asOfTimestamp: Optional[datetime] = None
    generatedAt: datetime

