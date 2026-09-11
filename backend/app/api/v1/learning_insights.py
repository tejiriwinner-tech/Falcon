import time
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List, Optional

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

from app.core.engines.market_state_engine import MarketStateEngine

_learning_engine = LearningInsightEngine()
_market_state_engine = MarketStateEngine()
_insights_store: List[LearningInsight] = []


def _build_live_market_insights(market_state, now: datetime) -> List[LearningInsight]:
    insights: List[LearningInsight] = []
    trend = getattr(market_state, "trend", None) or getattr(market_state, "overallTrend", "Neutral")
    session = getattr(market_state, "session", None) or getattr(market_state, "activeTradingSession", "Standby")
    volatility = getattr(market_state, "volatility", "Moderate")
    spread = getattr(market_state, "spread", 0.3)
    sentiment = getattr(market_state, "sentiment", "Neutral")
    fgi = getattr(market_state, "fearGreedIndex", 50)
    
    dir_desc = (
        f"Live quotes across watched symbols indicate {trend.lower()} pressure during the {session} session."
        if trend != "Neutral"
        else f"Prices are consolidating within normal bounds during the {session} session with no abnormal breakout."
    )
    insights.append(
        LearningInsight(
            id="insight-live-001",
            category=LearningCategory.MARKET,
            title=f"{trend} Market Structure in {session}",
            description=dir_desc,
            severity=InsightSeverity.NOTICE if trend != "Neutral" else InsightSeverity.INFO,
            confidence=InsightConfidence.HIGH if trend != "Neutral" else InsightConfidence.MEDIUM,
            recommendation=InsightRecommendation.FOCUS if trend != "Neutral" else InsightRecommendation.MONITOR,
            pattern=InsightPattern(
                title=f"{trend} Regime Flow",
                description=f"Active pricing aligns with {trend.lower()} trajectory in {session}.",
                occurrences=1,
                confidencePercentage=80.0 if trend != "Neutral" else 65.0,
            ),
            evidence=[
                InsightEvidence(
                    title="Live Market State",
                    description=f"Trend: {trend}, Volatility: {volatility}, Sentiment: {sentiment} (FGI: {fgi})",
                    source="MarketStateEngine",
                    artifactId="market-state-live",
                    timestamp=now,
                )
            ],
            affectedStrategies=["London Breakout", "Trend Continuation"] if trend != "Neutral" else ["Range Reversion"],
            relatedMissionIds=[],
            generatedFrom="LiveMarketAnalysis",
            generatedAt=now,
            generationDurationMs=5,
        )
    )
    
    vol_sev = InsightSeverity.WARNING if volatility == "High" else InsightSeverity.INFO
    vol_rec = InsightRecommendation.ADJUST if volatility == "High" else InsightRecommendation.OBSERVE
    insights.append(
        LearningInsight(
            id="insight-live-002",
            category=LearningCategory.RISK,
            title=f"{volatility} Volatility Environment ({spread:.1f} pips spread)",
            description=f"Observed spread of {spread:.1f} pips with {volatility.lower()} volatility. Session budget and risk limits are active.",
            severity=vol_sev,
            confidence=InsightConfidence.HIGH,
            recommendation=vol_rec,
            pattern=InsightPattern(
                title="Volatility Spread Ratio",
                description=f"{volatility} volatility with {spread:.1f} pips average spread.",
                occurrences=1,
                confidencePercentage=75.0,
            ),
            evidence=[
                InsightEvidence(
                    title="Risk Parameters",
                    description=f"Volatility: {volatility}, Average Spread: {spread:.2f} pips",
                    source="ProviderManager",
                    artifactId="market-risk-live",
                    timestamp=now,
                )
            ],
            affectedStrategies=["Risk Management"],
            relatedMissionIds=[],
            generatedFrom="LiveRiskAnalysis",
            generatedAt=now,
            generationDurationMs=4,
        )
    )
    return insights


_cached_insights_resp: Optional[LearningInsightListResponse] = None
_cached_insights_at: float = 0.0


@router.get("", response_model=LearningInsightListResponse)
def get_learning_insights():
    """
    Runs the Learning & Insight Engine against the current repository state
    and returns a LearningInsightListResponse. If no missions exist yet or on error,
    derives dynamic insights from the live market state.
    """
    global _insights_store, _cached_insights_resp, _cached_insights_at
    now_mono = time.monotonic()
    if _cached_insights_resp is not None and (now_mono - _cached_insights_at) < 60.0:
        return _cached_insights_resp

    now = datetime.now(timezone.utc)
    insights = []
    try:
        insights = _learning_engine.generate_learning_insights(mission_repository)
    except Exception as ex:
        import logging
        logging.getLogger("falcon.learning_insights").error(f"Failed to generate repository insights: {ex}")

    if not insights:
        try:
            ms = _market_state_engine.get_market_state()
            insights = _build_live_market_insights(ms, now)
        except Exception as ex:
            import logging
            logging.getLogger("falcon.learning_insights").error(f"Failed to generate live market insights: {ex}")
            insights = []

    _insights_store = insights
    summary = _learning_engine.build_summary(insights)

    resp = LearningInsightListResponse(
        insights=insights,
        summary=summary,
        lastUpdated=now,
    )
    _cached_insights_resp = resp
    _cached_insights_at = now_mono
    return resp


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
