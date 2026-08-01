from enum import Enum
from pydantic import BaseModel
from datetime import datetime
from typing import List


class CalibrationStatus(str, Enum):
    CALIBRATED = "CALIBRATED"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class CalibrationLevel(str, Enum):
    EXCELLENT = "EXCELLENT"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"


class CalibrationTrend(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DECLINING = "DECLINING"


class CalibrationRecommendation(str, Enum):
    TRUST_SIGNALS = "TRUST_SIGNALS"
    TRUST_WITH_MONITORING = "TRUST_WITH_MONITORING"
    REVIEW_STRATEGIES = "REVIEW_STRATEGIES"
    COLLECT_MORE_DATA = "COLLECT_MORE_DATA"
    DO_NOT_AUTOMATE = "DO_NOT_AUTOMATE"


class CalibrationEvidence(BaseModel):
    source: str
    description: str
    relatedMissionIds: List[str]


class CalibrationMetric(BaseModel):
    name: str
    weight: float
    score: float
    description: str


class CalibrationHistory(BaseModel):
    averageDecisionConfidence: float
    averageOutcomeScore: float
    averageValidationScore: float
    averageExecutionReadiness: float
    averageRiskConfidence: float
    missionCount: int


class CalibrationReport(BaseModel):
    id: str
    calibrationScore: float
    calibrationLevel: CalibrationLevel
    calibrationStatus: CalibrationStatus
    calibrationTrend: CalibrationTrend
    recommendation: CalibrationRecommendation
    metrics: List[CalibrationMetric]
    evidence: List[CalibrationEvidence]
    history: CalibrationHistory

    # Metadata
    artifactType: str = "CalibrationReport"
    pipelineStage: str = "CALIBRATION"
    pipelineVersion: str = "1.0"
    engineVersion: str = "1.0.0"
    timelineOrder: int = 13
    generatedBy: str = "AI Confidence Calibration Engine"
    generatedAt: datetime
    durationMs: int


class CalibrationSummary(BaseModel):
    totalReports: int
    averageCalibrationScore: float
    highestCalibration: float
    lowestCalibration: float
    currentCalibrationLevel: str


class CalibrationReportListResponse(BaseModel):
    reports: List[CalibrationReport]
    summary: CalibrationSummary
    lastUpdated: datetime
