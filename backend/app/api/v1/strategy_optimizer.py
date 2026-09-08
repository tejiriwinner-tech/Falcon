from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import time
from typing import List, Optional

from app.core.analytics.adaptive_strategy_optimizer import AdaptiveStrategyOptimizer
from app.core.repository.mission_repository import mission_repository
from app.schemas.strategy_optimization import (
    StrategyOptimizationReport,
    StrategyOptimizationListResponse,
)

router = APIRouter(prefix="/strategy-optimizer", tags=["strategy_optimizer"])

_optimizer = AdaptiveStrategyOptimizer()
_reports_store: List[StrategyOptimizationReport] = []
_optimizer_cache: Optional[StrategyOptimizationListResponse] = None
_optimizer_cache_time: float = 0.0
_CACHE_TTL_SECONDS = 60.0


@router.get("", response_model=StrategyOptimizationListResponse)
def get_strategy_optimization():
    """
    Runs the Adaptive Strategy Optimizer against the current repository state
    and returns a StrategyOptimizationListResponse with in-memory caching.
    """
    global _reports_store, _optimizer_cache, _optimizer_cache_time
    now_mono = time.monotonic()
    if _optimizer_cache is not None and (now_mono - _optimizer_cache_time) < _CACHE_TTL_SECONDS:
        return _optimizer_cache

    _reports_store = _optimizer.generate_optimization_reports(
        repository=mission_repository,
        analytics_report=None,
        strategy_reports=None,
        market_state=None,
    )
    summary = _optimizer.build_summary(_reports_store)

    response = StrategyOptimizationListResponse(
        reports=_reports_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )
    _optimizer_cache = response
    _optimizer_cache_time = now_mono
    return response


@router.get("/latest", response_model=StrategyOptimizationListResponse)
def get_latest_strategy_optimization():
    """Returns the latest StrategyOptimizationListResponse."""
    return get_strategy_optimization()


@router.get("/{report_id}", response_model=StrategyOptimizationReport)
def get_strategy_optimization_report_by_id(report_id: str):
    """Returns a single StrategyOptimizationReport by ID (e.g. optimizer-001)."""
    global _reports_store
    if not _reports_store:
        _reports_store = _optimizer.generate_optimization_reports(
            repository=mission_repository,
        )

    for r in _reports_store:
        if r.id == report_id or r.strategyId == report_id:
            return r

    raise HTTPException(
        status_code=404,
        detail=f"Strategy optimization report '{report_id}' not found",
    )
