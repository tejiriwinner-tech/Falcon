from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class OutcomeStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILURE = "FAILURE"


class OutcomeAccuracy(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"


class OutcomeSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class OutcomeRecommendation(str, Enum):
    CONTINUE = "CONTINUE"
    REVIEW = "REVIEW"
    IMPROVE = "IMPROVE"
    RETEST = "RETEST"


class OutcomeEvidence(BaseModel):
    source: str
    description: str
    relatedMissionId: str


class OutcomeMetric(BaseModel):
    name: str
    score: float
    maxScore: float
    percentage: float
    description: str


class OutcomeFinding(BaseModel):
    title: str
    description: str
    severity: OutcomeSeverity
    recommendation: OutcomeRecommendation


class OutcomePipelineStageReview(BaseModel):
    stage: str
    score: float
    verdict: str


class OutcomePipelineReview(BaseModel):
    signal: OutcomePipelineStageReview
    validation: OutcomePipelineStageReview
    risk: OutcomePipelineStageReview
    execution: OutcomePipelineStageReview
    decision: OutcomePipelineStageReview


class OutcomeAnalysisReport(BaseModel):
    id: str
    missionId: str
    decisionId: str
    strategyId: str
    strategyName: str

    outcomeScore: float
    outcomeStatus: OutcomeStatus
    accuracy: OutcomeAccuracy

    metrics: List[OutcomeMetric]
    findings: List[OutcomeFinding]
    evidence: List[OutcomeEvidence]
    pipelineReview: OutcomePipelineReview

    # Metadata
    artifactType: str = "OutcomeAnalysisReport"
    pipelineStage: str = "OUTCOME_ANALYSIS"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    analyzedBy: str = "Outcome Analysis Engine"
    timelineOrder: int = 8
    analyzedAt: datetime
    analysisDurationMs: int


class OutcomeSummary(BaseModel):
    totalReports: int
    successCount: int
    partialCount: int
    failureCount: int
    averageOutcomeScore: float
    averageAccuracy: str


class OutcomeAnalysisListResponse(BaseModel):
    reports: List[OutcomeAnalysisReport]
    summary: OutcomeSummary
    lastUpdated: datetime
