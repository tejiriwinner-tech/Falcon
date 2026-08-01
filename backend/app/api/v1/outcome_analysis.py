from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List

from app.core.engines.outcome_analysis_engine import OutcomeAnalysisEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.outcome_analysis import (
    OutcomeAnalysisReport,
    OutcomeAnalysisListResponse,
)

router = APIRouter(prefix="/outcome-analysis", tags=["outcome_analysis"])

_outcome_engine = OutcomeAnalysisEngine()
_outcome_store: List[OutcomeAnalysisReport] = []


@router.get("", response_model=OutcomeAnalysisListResponse)
def get_outcome_analysis():
    """
    Runs the Outcome Analysis Engine against the historical repository
    and returns an OutcomeAnalysisListResponse.
    """
    global _outcome_store
    _outcome_store = _outcome_engine.generate_reports(mission_repository)
    summary = _outcome_engine.build_summary(_outcome_store)

    return OutcomeAnalysisListResponse(
        reports=_outcome_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )


@router.get("/latest", response_model=OutcomeAnalysisListResponse)
def get_latest_outcome_analysis():
    """Returns the latest OutcomeAnalysisListResponse."""
    return get_outcome_analysis()


@router.get("/{report_id}", response_model=OutcomeAnalysisReport)
def get_outcome_report_by_id(report_id: str):
    """Returns a single OutcomeAnalysisReport by ID."""
    global _outcome_store
    if not _outcome_store:
        _outcome_store = _outcome_engine.generate_reports(mission_repository)

    for r in _outcome_store:
        if r.id == report_id:
            return r

    raise HTTPException(
        status_code=404,
        detail=f"Outcome analysis report '{report_id}' not found",
    )
