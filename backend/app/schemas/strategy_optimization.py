from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class OptimizationStatus(str, Enum):
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NO_CHANGES = "NO_CHANGES"


class OptimizationRecommendation(str, Enum):
    PRIORITIZE = "PRIORITIZE"
    MAINTAIN = "MAINTAIN"
    MONITOR = "MONITOR"
    PAUSE = "PAUSE"
    RETIRE = "RETIRE"


class OptimizationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class OptimizationTrend(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"


class OptimizationEvidence(BaseModel):
    title: str
    description: str
    source: str
    confidence: float


class StrategyOptimizationRecommendation(BaseModel):
    strategyId: str
    strategyName: str
    recommendation: OptimizationRecommendation
    priority: OptimizationPriority
    reason: str
    expectedBenefit: str
    confidence: float


class OptimizationScoreBreakdown(BaseModel):
    historicalPerformance: float
    strategyHealth: float
    marketCompatibility: float
    consistency: float
    riskEfficiency: float
    executionReliability: float


class StrategyOptimizationReport(BaseModel):
    id: str
    marketStateId: str
    analyticsReportId: Optional[str] = None
    strategyIntelligenceReportId: Optional[str] = None
    strategyId: str
    strategyName: str
    overallOptimizationScore: float
    status: OptimizationStatus
    trend: OptimizationTrend
    recommendation: StrategyOptimizationRecommendation
    scoreBreakdown: OptimizationScoreBreakdown
    evidence: List[OptimizationEvidence]

    # Metadata
    artifactType: str = "StrategyOptimizationReport"
    pipelineStage: str = "OPTIMIZATION"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    generatedBy: str = "Adaptive Strategy Optimizer"
    timelineOrder: int = 10
    generatedAt: datetime
    generationDurationMs: int


class StrategyOptimizationSummary(BaseModel):
    totalStrategies: int
    prioritizeCount: int
    maintainCount: int
    monitorCount: int
    pauseCount: int
    retireCount: int
    bestRecommendedStrategy: str
    highestOptimizationScore: float


class StrategyOptimizationListResponse(BaseModel):
    reports: List[StrategyOptimizationReport]
    summary: StrategyOptimizationSummary
    lastUpdated: datetime
