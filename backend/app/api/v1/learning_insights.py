from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List

from app.core.engines.learning_insight_engine import LearningInsightEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.learning_insight import (
    LearningInsight,
    LearningInsightListResponse,
    LearningSummary,
    LearningCategory,
    InsightSeverity,
    InsightConfidence,
    InsightRecommendation,
    InsightPattern,
    InsightEvidence,
)

router = APIRouter(prefix="/learning-insights", tags=["learning_insights"])

_learning_engine = LearningInsightEngine()
_insights_store: List[LearningInsight] = []


@router.get("", response_model=LearningInsightListResponse)
def get_learning_insights():
    """
    Runs the Learning & Insight Engine against the current repository state
    and returns a LearningInsightListResponse.
    """
    # Return sample learning insights for Phase 1.3
    now = datetime.now(timezone.utc)
    insights = [
        LearningInsight(
            id="insight-001",
            category=LearningCategory.MARKET,
            title="XAUUSD Breakout Pattern Detected",
            description="Strong bullish momentum detected on XAUUSD with key support at 4670. Volume surge confirms institutional interest.",
            severity=InsightSeverity.NOTICE,
            confidence=InsightConfidence.HIGH,
            recommendation=InsightRecommendation.MONITOR,
            pattern=InsightPattern(
                title="Bullish Breakout",
                description="Repeated breakouts above resistance levels",
                occurrences=5,
                confidencePercentage=85.0
            ),
            evidence=[
                InsightEvidence(
                    title="Volume Spike",
                    description="50% increase in trading volume",
                    source="Market Data Provider",
                    artifactId="data-001",
                    timestamp=now
                )
            ],
            affectedStrategies=["London Breakout"],
            relatedMissionIds=[],
            generatedFrom="Market Analysis",
            generatedAt=now,
            generationDurationMs=150
        ),
        LearningInsight(
            id="insight-002",
            category=LearningCategory.STRATEGY,
            title="London Breakout Strategy Performance",
            description="Strategy shows 78% win rate on EURUSD during London session. Risk/reward ratio improving.",
            severity=InsightSeverity.INFO,
            confidence=InsightConfidence.MEDIUM,
            recommendation=InsightRecommendation.FOCUS,
            pattern=InsightPattern(
                title="Session Performance",
                description="Higher win rates during London session",
                occurrences=12,
                confidencePercentage=78.0
            ),
            evidence=[
                InsightEvidence(
                    title="Win Rate Analysis",
                    description="78% win rate on EURUSD during London session",
                    source="Mission Repository",
                    artifactId="mission-001",
                    timestamp=now
                )
            ],
            affectedStrategies=["London Breakout"],
            relatedMissionIds=["mission-001"],
            generatedFrom="Strategy Analysis",
            generatedAt=now,
            generationDurationMs=200
        ),
        LearningInsight(
            id="insight-003",
            category=LearningCategory.RISK,
            title="Volatility Spreading Warning",
            description="Market volatility increasing across all pairs. Recommended to reduce position sizes and widen stop losses.",
            severity=InsightSeverity.WARNING,
            confidence=InsightConfidence.MEDIUM,
            recommendation=InsightRecommendation.ADJUST,
            pattern=InsightPattern(
                title="Volatility Increase",
                description="Market volatility rising across multiple pairs",
                occurrences=8,
                confidencePercentage=68.0
            ),
            evidence=[
                InsightEvidence(
                    title="Volatility Metrics",
                    description="ATR values increased by 30% across watched symbols",
                    source="Market Data Provider",
                    artifactId="data-002",
                    timestamp=now
                )
            ],
            affectedStrategies=["London Breakout", "Risk Management"],
            relatedMissionIds=[],
            generatedFrom="Risk Analysis",
            generatedAt=now,
            generationDurationMs=180
        )
    ]
    
    return LearningInsightListResponse(
        insights=insights,
        summary=LearningSummary(
            totalInsights=3,
            marketInsights=1,
            strategyInsights=1,
            riskInsights=1,
            decisionInsights=0,
            criticalInsights=0,
            averageConfidence=0.0
        ),
        lastUpdated=now,
    )


@router.get("/latest", response_model=LearningInsightListResponse)
def get_latest_learning_insights():
    """Returns the latest LearningInsightListResponse."""
    return get_learning_insights()


@router.get("/{insight_id}", response_model=LearningInsight)
def get_learning_insight_by_id(insight_id: str):
    """Returns a single LearningInsight by ID."""
    global _insights_store
    if not _insights_store:
        _insights_store = _learning_engine.generate_learning_insights(mission_repository)

    for i in _insights_store:
        if i.id == insight_id:
            return i

    raise HTTPException(
        status_code=404,
        detail=f"Learning insight '{insight_id}' not found",
    )
