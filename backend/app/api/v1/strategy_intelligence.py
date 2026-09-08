from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import time
from typing import List, Optional

from app.core.analytics.strategy_intelligence_engine import StrategyIntelligenceEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.strategy_intelligence import (
    StrategyIntelligenceReport,
    StrategyIntelligenceListResponse,
)

router = APIRouter(prefix="/strategy-intelligence", tags=["strategy_intelligence"])

_intelligence_engine = StrategyIntelligenceEngine()
_reports_store: List[StrategyIntelligenceReport] = []
_intelligence_cache: Optional[StrategyIntelligenceListResponse] = None
_intelligence_cache_time: float = 0.0
_CACHE_TTL_SECONDS = 60.0


@router.get("", response_model=StrategyIntelligenceListResponse)
def get_strategy_intelligence():
    """
    Evaluates strategies using archived repository data and returns StrategyIntelligenceListResponse with in-memory caching.
    """
    global _reports_store, _intelligence_cache, _intelligence_cache_time
    now_mono = time.monotonic()
    if _intelligence_cache is not None and (now_mono - _intelligence_cache_time) < _CACHE_TTL_SECONDS:
        return _intelligence_cache

    _reports_store = _intelligence_engine.generate_reports(mission_repository)
    summary = _intelligence_engine.build_summary(_reports_store)

    response = StrategyIntelligenceListResponse(
        reports=_reports_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )
    _intelligence_cache = response
    _intelligence_cache_time = now_mono
    return response


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
