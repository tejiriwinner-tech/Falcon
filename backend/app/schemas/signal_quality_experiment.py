"""
Falcon V10 — Signal Quality & Regime-Confluence Experiment Schemas

Strictly read-only schemas for the paper-only post-V10 signal quality experiment.
No database models, no migrations, no broker automation fields.
Execution boundary remains: FALCON -> SIGNAL -> USER -> MT5 -> EXNESS.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExperimentalQualityDecision(str, Enum):
    PASS = "PASS"
    REJECT = "REJECT"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MtfAlignmentState(str, Enum):
    ALIGNED = "ALIGNED"
    PARTIALLY_ALIGNED = "PARTIALLY_ALIGNED"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class StructureState(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    INVALIDATED = "INVALIDATED"
    UNKNOWN = "UNKNOWN"


class LiquidityState(str, Enum):
    CONFIRMED = "CONFIRMED"
    SWEEP_DETECTED = "SWEEP_DETECTED"
    NO_SWEEP = "NO_SWEEP"
    UNKNOWN = "UNKNOWN"


class VolatilitySuitabilityState(str, Enum):
    SUITABLE = "SUITABLE"
    ELEVATED = "ELEVATED"
    COMPRESSED = "COMPRESSED"
    UNKNOWN = "UNKNOWN"


class RegimeObservation(BaseModel):
    regime: str = "UNKNOWN"
    strategyCompatibility: str = "NOT_APPLICABLE"
    avoidConditionMatched: bool = False
    details: Optional[str] = None


class MtfObservation(BaseModel):
    state: MtfAlignmentState = MtfAlignmentState.UNKNOWN
    alignedTimeframes: List[str] = Field(default_factory=list)
    conflictingTimeframes: List[str] = Field(default_factory=list)
    confluenceScore: float = 0.0
    details: Optional[str] = None


class StructureObservation(BaseModel):
    state: StructureState = StructureState.UNKNOWN
    trendDirection: Optional[str] = None
    lastEvent: Optional[str] = None
    swingStructure: Optional[str] = None
    details: Optional[str] = None


class LiquidityObservation(BaseModel):
    state: LiquidityState = LiquidityState.UNKNOWN
    sweptLevel: Optional[float] = None
    trapType: Optional[str] = None
    details: Optional[str] = None


class VolatilityObservation(BaseModel):
    state: VolatilitySuitabilityState = VolatilitySuitabilityState.UNKNOWN
    atr: Optional[float] = None
    spread: Optional[float] = None
    volatilityLabel: Optional[str] = None
    details: Optional[str] = None


class SignalQualityEvaluationItem(BaseModel):
    candidateId: str
    symbol: str
    strategyId: str
    direction: str
    evaluatedAt: datetime
    baselineDecision: str
    experimentalDecision: ExperimentalQualityDecision
    rejectionReasons: List[str] = Field(default_factory=list)
    regimeObservation: RegimeObservation
    mtfObservation: MtfObservation
    structureObservation: StructureObservation
    liquidityObservation: LiquidityObservation
    volatilityObservation: VolatilityObservation
    experimentVersion: str = "1.0.0"
    provenance: str = "PAPER_EXPERIMENT_ONLY"
    outcomePnl: Optional[float] = None
    outcomeStatus: Optional[str] = None


class ControlGroupMetrics(BaseModel):
    totalCandidates: int = 0
    acceptedCount: int = 0
    rejectedCount: int = 0
    evaluatedTradeCount: int = 0
    winRate: Optional[float] = None
    profitFactor: Optional[float] = None
    totalPnl: Optional[float] = None


class SignalQualityAnalyticsResponse(BaseModel):
    experimentEnabled: bool
    experimentVersion: str
    sampleSize: int
    minSampleSize: int
    sampleAdequacy: str  # "EVALUABLE" or "NOT_EVALUABLE"
    baselineApprovedCount: int
    experimentalPassedCount: int
    experimentalRejectedCount: int
    experimentalPassRate: Optional[float] = None
    evaluations: List[SignalQualityEvaluationItem] = Field(default_factory=list)
    controlGroupComparison: Optional[Dict[str, Any]] = None
    asOf: Optional[datetime] = None
    summaryNotes: List[str] = Field(default_factory=list)
