from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List

from app.core.analytics.strategy_intelligence_engine import StrategyIntelligenceEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.strategy_intelligence import (
    StrategyIntelligenceReport,
    StrategyIntelligenceListResponse,
)

router = APIRouter(prefix="/strategy-intelligence", tags=["strategy_intelligence"])

_intelligence_engine = StrategyIntelligenceEngine()
_reports_store: List[StrategyIntelligenceReport] = []


@router.get("", response_model=StrategyIntelligenceListResponse)
def get_strategy_intelligence():
    """
    Evaluates strategies using archived repository data and returns StrategyIntelligenceListResponse.
    """
    global _reports_store
    _reports_store = _intelligence_engine.generate_reports(mission_repository)
    summary = _intelligence_engine.build_summary(_reports_store)

    return StrategyIntelligenceListResponse(
        reports=_reports_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )


@router.get("/latest", response_model=StrategyIntelligenceListResponse)
def get_latest_strategy_intelligence():
    """
    Returns latest StrategyIntelligenceListResponse based on current repository state.
    """
    return get_strategy_intelligence()


@router.get("/{report_id}", response_model=StrategyIntelligenceReport)
def get_strategy_intelligence_report_by_id(report_id: str):
    """
    Returns a single StrategyIntelligenceReport by its ID (e.g. strategy-report-001).
    """
    global _reports_store
    if not _reports_store:
        _reports_store = _intelligence_engine.generate_reports(mission_repository)

    for r in _reports_store:
        if r.id == report_id or r.strategyId == report_id:
            return r

    raise HTTPException(status_code=404, detail=f"Strategy intelligence report '{report_id}' not found")
