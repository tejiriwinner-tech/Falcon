"""
Falcon V10 Phase 5G: Execution Divergence Schemas.

Models for comparing PAPER simulated trade expectations against actual
manually executed LIVE trades originating from the same signal candidate.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DivergenceClassification(str, Enum):
    MATCHED = "MATCHED"
    MISSED_EXECUTION = "MISSED_EXECUTION"
    MANUAL_ONLY = "MANUAL_ONLY"
    AMBIGUOUS = "AMBIGUOUS"


class TradePairDivergenceItem(BaseModel):
    """Execution divergence analysis for a single trading opportunity (signalId)."""
    model_config = ConfigDict(from_attributes=True)

    signalId: int
    symbol: str
    direction: str
    classification: str
    strategyId: Optional[str] = None
    strategyVersion: Optional[str] = None
    adaptiveRuleVersion: Optional[str] = None

    # Trade Journal references
    paperTradeId: Optional[int] = None
    liveTradeId: Optional[int] = None

    # Entry & Slippage (authoritative actual fill prices only)
    paperFillPrice: Optional[float] = None
    liveFillPrice: Optional[float] = None
    entryPriceDelta: Optional[float] = None
    slippagePoints: Optional[float] = None

    # Timing & Latency
    paperSignalTime: Optional[datetime] = None
    liveFillTime: Optional[datetime] = None
    executionLatencySeconds: Optional[float] = None

    # Spread
    paperSpread: Optional[float] = None
    liveSpread: Optional[float] = None
    spreadDelta: Optional[float] = None

    # Outcome & Realized R
    paperResult: Optional[str] = None
    liveResult: Optional[str] = None
    paperRealizedR: Optional[float] = None
    liveRealizedR: Optional[float] = None
    rDivergence: Optional[float] = None

    # Excursion
    paperMfeR: Optional[float] = None
    liveMfeR: Optional[float] = None
    paperMaeR: Optional[float] = None
    liveMaeR: Optional[float] = None

    # Deterministic premature exit indicator
    prematureExit: Optional[bool] = None


class ExecutionDivergenceResponse(BaseModel):
    """Aggregate divergence report comparing PAPER and LIVE execution populations."""
    model_config = ConfigDict(from_attributes=True)

    matchedPairsCount: int = 0
    missedExecutionCount: int = 0
    manualOnlyCount: int = 0
    ambiguousCount: int = 0
    averageSlippagePoints: Optional[float] = None
    averageLatencySeconds: Optional[float] = None
    averageRDivergence: Optional[float] = None
    prematureExitCount: int = 0
    items: List[TradePairDivergenceItem] = Field(default_factory=list)
    asOf: datetime
    evaluatedAt: datetime
