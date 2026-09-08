from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import time
from typing import List, Optional

from app.core.engines.outcome_analysis_engine import OutcomeAnalysisEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.outcome_analysis import (
    OutcomeAnalysisReport,
    OutcomeAnalysisListResponse,
)

router = APIRouter(prefix="/outcome-analysis", tags=["outcome_analysis"])

_outcome_engine = OutcomeAnalysisEngine()
_outcome_cache: Optional[OutcomeAnalysisListResponse] = None
_outcome_cache_time: float = 0.0
_CACHE_TTL_SECONDS = 60.0


@router.get("", response_model=OutcomeAnalysisListResponse)
def get_outcome_analysis(
    limit: int = 30
):
    """
    Runs the Outcome Analysis Engine against the recent historical repository
    and returns an OutcomeAnalysisListResponse with in-memory caching.
    """
    global _outcome_cache, _outcome_cache_time
    now_mono = time.monotonic()

    if _outcome_cache is not None and (now_mono - _outcome_cache_time) < _CACHE_TTL_SECONDS:
        return _outcome_cache

    reports = _outcome_engine.generate_reports(mission_repository, limit=limit)
    summary = _outcome_engine.build_summary(reports)

    response = OutcomeAnalysisListResponse(
        reports=reports,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )
    _outcome_cache = response
    _outcome_cache_time = now_mono
    return response


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
