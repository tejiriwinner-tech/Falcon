from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class StrategyHealth(str, Enum):
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    WATCH = "WATCH"
    POOR = "POOR"
    RETIRED = "RETIRED"


class StrategyTrend(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"


class RecommendationPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class StrategyScoreBreakdown(BaseModel):
    signalConfidenceScore: float
    validationScore: float
    riskScore: float
    executionScore: float
    decisionScore: float
    consistencyScore: float


class StrategyRecommendation(BaseModel):
    priority: RecommendationPriority
    title: str
    description: str
    recommendedAction: str


class StrategyTrendMetrics(BaseModel):
    confidenceTrend: StrategyTrend
    validationTrend: StrategyTrend
    riskTrend: StrategyTrend
    decisionTrend: StrategyTrend
    executionTrend: StrategyTrend
    overallTrend: StrategyTrend


class StrategyPerformanceSnapshot(BaseModel):
    missionsExecuted: int
    buySignals: int
    sellSignals: int
    waitSignals: int
    approvedTrades: int
    monitoringTrades: int
    rejectedTrades: int
    averageDecisionConfidence: float
    averageRiskScore: float
    averageExecutionReadiness: float
    averageValidationScore: float


class StrategyIntelligenceReport(BaseModel):
    id: str
    strategyId: str
    strategyName: str
    strategyVersion: str
    health: StrategyHealth
    overallScore: float
    trend: StrategyTrend
    performanceSnapshot: StrategyPerformanceSnapshot
    scoreBreakdown: StrategyScoreBreakdown
    recommendation: StrategyRecommendation

    # Metadata
    artifactType: str = "StrategyIntelligenceReport"
    pipelineStage: str = "STRATEGY_INTELLIGENCE"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    generatedBy: str = "Strategy Intelligence Engine"
    timelineOrder: int = 9
    generatedAt: datetime
    generationDurationMs: int


class StrategyIntelligenceSummary(BaseModel):
    totalStrategies: int
    excellentStrategies: int
    goodStrategies: int
    watchStrategies: int
    poorStrategies: int
    retiredStrategies: int
    highestRankedStrategy: str
    lowestRankedStrategy: str


class StrategyIntelligenceListResponse(BaseModel):
    reports: List[StrategyIntelligenceReport]
    summary: StrategyIntelligenceSummary
    lastUpdated: datetime
