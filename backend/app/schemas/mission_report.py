from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class MissionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"


class MissionStageStatus(str, Enum):
    COMPLETED = "COMPLETED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"


class MissionTimelineEvent(BaseModel):
    stage: str
    artifactId: str
    status: MissionStageStatus
    startedAt: datetime
    completedAt: datetime
    durationMs: int


class MissionArtifactReferences(BaseModel):
    marketStateId: str
    candidateIds: List[str]
    validationIds: List[str]
    riskAssessmentIds: List[str]
    executionReadinessIds: List[str]
    decisionIds: List[str]


class MissionPipelineSummary(BaseModel):
    marketStateCount: int
    candidateCount: int
    validationCount: int
    riskAssessmentCount: int
    executionReadinessCount: int
    decisionCount: int


class MissionPerformance(BaseModel):
    totalDurationMs: int
    marketDurationMs: int
    signalDurationMs: int
    validationDurationMs: int
    riskDurationMs: int
    executionDurationMs: int
    decisionDurationMs: int
    averageStageDurationMs: float


class MissionHealth(BaseModel):
    pipelineHealthPercentage: float
    providerHealthPercentage: float
    enginesHealthy: int
    providersHealthy: int
    warnings: List[str]


class MissionReport(BaseModel):
    id: str
    missionNumber: int
    status: MissionStatus
    artifactReferences: MissionArtifactReferences
    pipelineSummary: MissionPipelineSummary
    performance: MissionPerformance
    health: MissionHealth
    timeline: List[MissionTimelineEvent]
    startedAt: datetime
    completedAt: datetime

    # Metadata
    artifactType: str = "MissionReport"
    pipelineStage: str = "MISSION"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    generatedBy: str = "Pipeline Orchestrator"
    timelineOrder: int = 7


class MissionSummary(BaseModel):
    totalMissions: int
    successful: int
    partialSuccess: int
    failed: int
    averageDurationMs: float
    averagePipelineHealth: float


class MissionReportListResponse(BaseModel):
    missions: List[MissionReport]
    summary: MissionSummary
    lastUpdated: datetime
