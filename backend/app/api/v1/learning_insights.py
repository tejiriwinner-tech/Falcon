from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List

from app.core.engines.learning_insight_engine import LearningInsightEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.learning_insight import (
    LearningInsight,
    LearningInsightListResponse,
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
    global _insights_store
    _insights_store = _learning_engine.generate_learning_insights(mission_repository)
    summary = _learning_engine.build_summary(_insights_store)

    return LearningInsightListResponse(
        insights=_insights_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
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
