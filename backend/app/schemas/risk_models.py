"""
Risk Management Models
Models for risk assessment and risk statistics.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


class RiskDecision(str, Enum):
    """Risk decision outcome."""
    APPROVED = "APPROVED"
    APPROVED_WITH_WARNING = "APPROVED_WITH_WARNING"
    REJECTED = "REJECTED"


class RiskAssessment(BaseModel):
    """
    Complete risk assessment for a trade setup.
    
    Contains all risk evaluation results including decision, risk score,
    risk percentage, daily exposure, portfolio exposure, correlation level,
    reasons, and warnings.
    
    Attributes:
        signalId: Signal ID being assessed
        symbol: Instrument symbol
        timeframe: Timeframe analyzed
        decision: Risk decision (APPROVED, APPROVED_WITH_WARNING, REJECTED)
        overallRiskScore: Overall risk score (0-100)
        riskPercent: Risk percentage of account
        rr: Risk/reward ratio
        dailyExposure: Daily risk exposure percentage
        portfolioExposure: Portfolio exposure percentage
        correlationLevel: Correlation level (LOW, MEDIUM, HIGH)
        approved: Whether the trade is approved
        reasons: List of reasons for the decision
        warnings: List of warnings
        assessedAt: Timestamp when assessment was performed
    """
    signalId: str = Field(..., description="Signal ID being assessed")
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Timeframe analyzed")
    decision: RiskDecision = Field(..., description="Risk decision")
    overallRiskScore: float = Field(..., ge=0.0, le=100.0, description="Overall risk score (0-100)")
    riskPercent: float = Field(..., ge=0.0, le=100.0, description="Risk percentage of account")
    rr: float = Field(..., ge=0.0, description="Risk/reward ratio")
    dailyExposure: float = Field(..., ge=0.0, le=100.0, description="Daily risk exposure percentage")
    portfolioExposure: float = Field(..., ge=0.0, le=100.0, description="Portfolio exposure percentage")
    correlationLevel: str = Field(..., description="Correlation level (LOW, MEDIUM, HIGH)")
    approved: bool = Field(..., description="Whether the trade is approved")
    reasons: List[str] = Field(default_factory=list, description="Reasons for the decision")
    warnings: List[str] = Field(default_factory=list, description="Risk warnings")
    assessedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Assessment timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "signalId": "SIG-20260802-000001",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "decision": "APPROVED",
                "overallRiskScore": 25.0,
                "riskPercent": 1.5,
                "rr": 3.05,
                "dailyExposure": 1.5,
                "portfolioExposure": 3.0,
                "correlationLevel": "LOW",
                "approved": True,
                "reasoning": [
                    "RR above minimum threshold",
                    "Confidence above threshold",
                    "Signal quality acceptable"
                ],
                "warnings": [],
                "assessedAt": "2024-01-01T12:00:00Z"
            }
        }


class RiskStatistics(BaseModel):
    """
    Risk management engine runtime statistics.
    
    Provides performance metrics for the risk management engine.
    
    Attributes:
        totalAssessments: Total number of risk assessments performed
        approvedCount: Number of approved trades
        approvedWithWarningCount: Number of approved with warning trades
        rejectedCount: Number of rejected trades
        averageRiskScore: Average risk score across all assessments
        averageRiskPercent: Average risk percentage
        averageRR: Average risk/reward ratio
        averageAssessmentTime: Average assessment time in milliseconds
        rejectionReasons: Breakdown of rejection reasons
    """
    totalAssessments: int = Field(0, description="Total risk assessments")
    approvedCount: int = Field(0, description="Number of approved trades")
    approvedWithWarningCount: int = Field(0, description="Number of approved with warning trades")
    rejectedCount: int = Field(0, description="Number of rejected trades")
    averageRiskScore: float = Field(0.0, description="Average risk score")
    averageRiskPercent: float = Field(0.0, description="Average risk percentage")
    averageRR: float = Field(0.0, description="Average risk/reward ratio")
    averageAssessmentTime: float = Field(0.0, description="Average assessment time (ms)")
    rejectionReasons: dict = Field(default_factory=dict, description="Rejection reasons breakdown")

    class Config:
        json_schema_extra = {
            "example": {
                "totalAssessments": 100,
                "approvedCount": 65,
                "approvedWithWarningCount": 15,
                "rejectedCount": 20,
                "averageRiskScore": 35.5,
                "averageRiskPercent": 1.8,
                "averageRR": 2.8,
                "averageAssessmentTime": 1.5,
                "rejectionReasons": {
                    "RR below minimum": 8,
                    "Confidence below threshold": 5,
                    "Daily risk exceeded": 4,
                    "Portfolio exposure exceeded": 3
                }
            }
        }
