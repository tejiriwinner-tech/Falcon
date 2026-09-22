"""
Falcon V10 Phase 5G: Strategy Attribution & Drift Schemas.

Multi-version attribution matrix across Strategy ID, Strategy Version,
Adaptive Rule Version, and Execution Mode, plus statistical drift diagnostics.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DriftStatus(str, Enum):
    NORMAL = "NORMAL"
    WIN_RATE_DRIFT_DETECTED = "WIN_RATE_DRIFT_DETECTED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class StrategyAttributionTuple(BaseModel):
    """Canonical 4-tuple key for performance attribution."""
    model_config = ConfigDict(from_attributes=True)

    strategyId: str
    strategyVersion: Optional[str] = None
    adaptiveRuleVersion: Optional[str] = None
    executionMode: str


class StrategyAttributionMetrics(BaseModel):
    """Descriptive performance metrics for a specific attribution tuple."""
    model_config = ConfigDict(from_attributes=True)

    tradeCount: int = 0
    closedCount: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    winRate: float = 0.0
    profitFactor: Optional[float] = None
    totalRealizedR: float = 0.0
    averageRealizedR: Optional[float] = None
    averageMfeR: Optional[float] = None
    averageMaeR: Optional[float] = None
    averageLatencySeconds: Optional[float] = None
    averageSlippagePoints: Optional[float] = None


class StrategyAttributionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: StrategyAttributionTuple
    metrics: StrategyAttributionMetrics


class StrategyDriftDiagnostic(BaseModel):
    """Diagnostic comparison of LIVE performance against PAPER benchmark."""
    model_config = ConfigDict(from_attributes=True)

    strategyId: str
    strategyVersion: Optional[str] = None
    adaptiveRuleVersion: Optional[str] = None
    status: str = DriftStatus.NOT_EVALUABLE.value
    warning: bool = False
    sampleSizeLive: int = 0
    sampleSizePaper: int = 0
    liveWinRate: Optional[float] = None
    paperWinRate: Optional[float] = None
    standardError: Optional[float] = None
    zScoreWinRate: Optional[float] = None
    zScoreProfitFactor: Optional[float] = None  # Strictly None (Option A)
    profitFactorDrift: str = "NOT_EVALUABLE"    # Strictly NOT_EVALUABLE (Option A)
    diagnosticOnly: bool = True
    message: str


class StrategyAttributionResponse(BaseModel):
    """Multi-version attribution report with drift diagnostics."""
    model_config = ConfigDict(from_attributes=True)

    attributions: List[StrategyAttributionItem] = Field(default_factory=list)
    driftDiagnostics: List[StrategyDriftDiagnostic] = Field(default_factory=list)
    asOf: datetime
    evaluatedAt: datetime
