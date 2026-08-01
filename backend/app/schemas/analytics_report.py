from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class AnalyticsStatus(str, Enum):
    READY = "READY"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class TrendDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"


class PerformanceGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class PerformanceMetric(BaseModel):
    title: str
    description: str
    value: float
    unit: str
    trend: TrendDirection
    grade: PerformanceGrade


class StrategyAnalytics(BaseModel):
    strategyId: str
    strategyName: str
    missionsExecuted: int
    buySignals: int
    sellSignals: int
    waitSignals: int
    approvedDecisions: int
    averageSignalConfidence: float
    averageValidationScore: float
    averageRiskScore: float
    averageExecutionScore: float
    averageDecisionConfidence: float
    performanceGrade: PerformanceGrade


class PipelineAnalytics(BaseModel):
    missionsAnalyzed: int
    averageMissionDurationMs: float
    averageStageDurationMs: float
    pipelineHealth: float
    repositoryHealth: float
    averagePipelineConfidence: float


class MissionAnalytics(BaseModel):
    totalMissions: int
    successfulMissions: int
    partialMissions: int
    failedMissions: int
    buySignals: int
    sellSignals: int
    waitSignals: int
    averageDecisionConfidence: float
    averageValidationScore: float
    averageRiskScore: float
    averageExecutionReadiness: float


class AnalyticsSummary(BaseModel):
    highestDecisionConfidence: float
    lowestDecisionConfidence: float
    highestRiskObserved: float
    lowestRiskObserved: float
    mostActiveStrategy: str
    bestPerformingStrategy: str
    averageRepositoryGrowth: float
    generatedAt: datetime


class AnalyticsReport(BaseModel):
    id: str
    status: AnalyticsStatus
    missionAnalytics: MissionAnalytics
    pipelineAnalytics: PipelineAnalytics
    strategyAnalytics: List[StrategyAnalytics]
    performanceMetrics: List[PerformanceMetric]
    summary: AnalyticsSummary

    # Metadata
    artifactType: str = "AnalyticsReport"
    pipelineStage: str = "ANALYTICS"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    generatedBy: str = "Performance Analytics Engine"
    timelineOrder: int = 8
    generatedAt: datetime
    generationDurationMs: int


class AnalyticsSummaryResponse(BaseModel):
    reports: List[AnalyticsReport]
    lastGenerated: datetime
    repositoryVersion: str = "1.0.0"
