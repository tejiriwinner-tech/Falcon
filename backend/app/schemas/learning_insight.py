from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional


class LearningCategory(str, Enum):
    MARKET = "MARKET"
    STRATEGY = "STRATEGY"
    VALIDATION = "VALIDATION"
    RISK = "RISK"
    EXECUTION = "EXECUTION"
    DECISION = "DECISION"
    MISSION = "MISSION"
    PERFORMANCE = "PERFORMANCE"


class InsightSeverity(str, Enum):
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class InsightConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class InsightRecommendation(str, Enum):
    OBSERVE = "OBSERVE"
    MONITOR = "MONITOR"
    ADJUST = "ADJUST"
    FOCUS = "FOCUS"
    INVESTIGATE = "INVESTIGATE"


class InsightEvidence(BaseModel):
    title: str
    description: str
    source: str
    artifactId: str
    timestamp: datetime


class InsightPattern(BaseModel):
    title: str
    description: str
    occurrences: int
    confidencePercentage: float


class LearningInsight(BaseModel):
    id: str
    category: LearningCategory
    title: str
    description: str
    severity: InsightSeverity
    confidence: InsightConfidence
    recommendation: InsightRecommendation
    pattern: InsightPattern
    evidence: List[InsightEvidence]
    affectedStrategies: List[str]
    relatedMissionIds: List[str]
    generatedFrom: str

    # Metadata
    artifactType: str = "LearningInsight"
    pipelineStage: str = "LEARNING"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    generatedBy: str = "Learning Insight Engine"
    timelineOrder: int = 8
    generatedAt: datetime
    generationDurationMs: int


class LearningSummary(BaseModel):
    totalInsights: int
    marketInsights: int
    strategyInsights: int
    riskInsights: int
    decisionInsights: int
    criticalInsights: int
    averageConfidence: float


class LearningInsightListResponse(BaseModel):
    insights: List[LearningInsight]
    summary: LearningSummary
    lastUpdated: datetime
