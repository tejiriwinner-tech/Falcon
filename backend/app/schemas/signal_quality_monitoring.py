"""
Falcon V10 — Signal Quality Monitoring & Reporting Schemas

Strictly read-only schemas for the post-V10 signal quality monitoring and reporting workflow.
No database models, no migrations, no broker automation fields.
Execution boundary remains: FALCON -> SIGNAL -> USER -> MT5 -> EXNESS.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PopulationType(str, Enum):
    CANDIDATE_POPULATION = "CANDIDATE_POPULATION"
    BASELINE_POPULATION = "BASELINE_POPULATION"
    EXPERIMENT_PASS_POPULATION = "EXPERIMENT_PASS_POPULATION"
    EXPERIMENT_REJECT_POPULATION = "EXPERIMENT_REJECT_POPULATION"
    ACTUAL_EXECUTION_POPULATION = "ACTUAL_EXECUTION_POPULATION"
    COUNTERFACTUAL_POPULATION = "COUNTERFACTUAL_POPULATION"


class MissedOpportunityCategory(str, Enum):
    REJECTED_NO_OUTCOME = "REJECTED_NO_OUTCOME"
    REJECTED_WOULD_HAVE_WON = "REJECTED_WOULD_HAVE_WON"
    REJECTED_WOULD_HAVE_LOST = "REJECTED_WOULD_HAVE_LOST"
    REJECTED_OUTCOME_UNKNOWN = "REJECTED_OUTCOME_UNKNOWN"


class CounterfactualProvenance(BaseModel):
    candidateId: str
    outcome: MissedOpportunityCategory
    evaluationSource: Optional[str] = None
    evaluatedAt: datetime
    closedAt: Optional[datetime] = None
    evidenceDetails: Optional[Dict[str, Any]] = None


class PopulationOutcomeMetrics(BaseModel):
    population: PopulationType
    closedCount: int = 0
    wins: int = 0
    losses: int = 0
    winRate: Optional[float] = None
    averageRealizedR: Optional[float] = None
    medianRealizedR: Optional[float] = None
    totalRealizedR: Optional[float] = None
    averageMfe: Optional[float] = None
    averageMae: Optional[float] = None
    evaluable: bool = False


class FilteringMetrics(BaseModel):
    totalCandidates: int = 0
    baselineApproved: int = 0
    experimentalPassed: int = 0
    experimentalRejected: int = 0
    unknown: int = 0
    notApplicable: int = 0
    passRate: Optional[float] = None
    rejectionRate: Optional[float] = None


class ComponentBreakdownItem(BaseModel):
    component: str  # "REGIME", "MTF", "STRUCTURE", "LIQUIDITY", "VOLATILITY"
    observations: int = 0
    passCount: int = 0
    rejectCount: int = 0
    unknownCount: int = 0
    notApplicableCount: int = 0
    outcomes: Optional[PopulationOutcomeMetrics] = None


class RejectionReasonItem(BaseModel):
    reason: str
    count: int = 0
    percentage: float = 0.0


class StrategyBreakdownItem(BaseModel):
    strategyId: str
    strategyVersion: str
    adaptiveRuleVersion: Optional[str] = None
    executionMode: str
    candidateCount: int = 0
    baselineApproved: int = 0
    experimentalPassed: int = 0
    experimentalRejected: int = 0
    outcomes: Optional[PopulationOutcomeMetrics] = None


class DirectionBreakdownItem(BaseModel):
    direction: str  # "BUY", "SELL"
    candidateCount: int = 0
    passed: int = 0
    rejected: int = 0
    outcomes: Optional[PopulationOutcomeMetrics] = None


class RegimeBreakdownItem(BaseModel):
    regime: str  # "TRENDING", "RANGING", "VOLATILE", "QUIET", "UNKNOWN"
    candidateCount: int = 0
    passed: int = 0
    rejected: int = 0
    outcomes: Optional[PopulationOutcomeMetrics] = None


class BaselineVsExperimentComparison(BaseModel):
    baselineCount: int = 0
    experimentCount: int = 0
    pairedCount: int = 0
    unpairedCount: int = 0
    baselineOutcomes: Optional[PopulationOutcomeMetrics] = None
    experimentOutcomes: Optional[PopulationOutcomeMetrics] = None
    deltaWinRate: Optional[float] = None
    deltaAverageRealizedR: Optional[float] = None
    deltaTotalRealizedR: Optional[float] = None
    evaluable: bool = False


class MissedOpportunityAnalysis(BaseModel):
    totalRejected: int = 0
    rejectedNoOutcomeCount: int = 0
    rejectedWouldHaveWonCount: int = 0
    rejectedWouldHaveLostCount: int = 0
    rejectedOutcomeUnknownCount: int = 0
    provenanceRecords: List[CounterfactualProvenance] = Field(default_factory=list)


class ReportMetadata(BaseModel):
    generatedAt: datetime
    asOf: Optional[datetime] = None
    startAt: Optional[datetime] = None
    endAt: Optional[datetime] = None
    experimentVersion: str = "1.0.0"
    executionModeFilter: Optional[str] = None
    strategyIdFilter: Optional[str] = None


class SampleMetrics(BaseModel):
    sampleSize: int = 0
    minSampleSize: int = 10
    sampleAdequacy: str = "NOT_EVALUABLE"  # "EVALUABLE" or "NOT_EVALUABLE"


class SignalQualityExperimentReport(BaseModel):
    metadata: ReportMetadata
    sample: SampleMetrics
    filtering: FilteringMetrics
    actualOutcomes: PopulationOutcomeMetrics
    missedOpportunities: MissedOpportunityAnalysis
    baselineVsExperiment: BaselineVsExperimentComparison
    rejectionReasons: List[RejectionReasonItem] = Field(default_factory=list)
    componentAnalysis: List[ComponentBreakdownItem] = Field(default_factory=list)
    strategyAnalysis: List[StrategyBreakdownItem] = Field(default_factory=list)
    directionAnalysis: List[DirectionBreakdownItem] = Field(default_factory=list)
    regimeAnalysis: List[RegimeBreakdownItem] = Field(default_factory=list)
    dataQuality: Dict[str, Any] = Field(default_factory=dict)
    limitations: List[str] = Field(default_factory=list)


class SignalQualitySummaryResponse(BaseModel):
    sampleSize: int = 0
    sampleAdequacy: str = "NOT_EVALUABLE"
    passRate: Optional[float] = None
    rejectionRate: Optional[float] = None
    closedCount: int = 0
    winRate: Optional[float] = None
    averageRealizedR: Optional[float] = None
    topRejectionReasons: List[RejectionReasonItem] = Field(default_factory=list)
    dataQualityStatus: str = "OK"
    asOf: Optional[datetime] = None
    experimentVersion: str = "1.0.0"
