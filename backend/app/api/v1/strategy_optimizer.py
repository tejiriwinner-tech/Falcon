from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import time
from typing import List, Optional

from app.core.analytics.adaptive_strategy_optimizer import AdaptiveStrategyOptimizer
from app.core.analytics.strategy_intelligence_engine import StrategyIntelligenceEngine
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.strategy_optimization import (
    StrategyOptimizationReport,
    StrategyOptimizationListResponse,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/strategy-optimizer", tags=["strategy_optimizer"])

_optimizer = AdaptiveStrategyOptimizer()
_intelligence_engine = StrategyIntelligenceEngine()
_market_state_engine = MarketStateEngine()
_reports_store: List[StrategyOptimizationReport] = []
_optimizer_cache: Optional[StrategyOptimizationListResponse] = None
_optimizer_cache_time: float = 0.0
_CACHE_TTL_SECONDS = 60.0


@router.get("", response_model=StrategyOptimizationListResponse)
def get_strategy_optimization():
    """
    Runs the Adaptive Strategy Optimizer against the current repository state,
    incorporating live market state and strategy intelligence reports.
    """
    global _reports_store, _optimizer_cache, _optimizer_cache_time
    now_mono = time.monotonic()
    if _optimizer_cache is not None and (now_mono - _optimizer_cache_time) < _CACHE_TTL_SECONDS:
        return _optimizer_cache

    try:
        market_state = _market_state_engine.get_market_state()
        strategy_reports = _intelligence_engine.generate_reports(mission_repository)

        _reports_store = _optimizer.generate_optimization_reports(
            repository=mission_repository,
            analytics_report=None,
            strategy_reports=strategy_reports,
            market_state=market_state,
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
    except Exception as exc:
        logger.error(f"Error computing strategy optimization: {exc}", exc_info=True)
        if _optimizer_cache is not None:
            return _optimizer_cache
        raise HTTPException(
            status_code=500,
            detail=f"Unable to generate strategy optimization: {str(exc)}"
        )


@router.get("/latest", response_model=StrategyOptimizationListResponse)
def get_latest_strategy_optimization():
    """Returns the latest StrategyOptimizationListResponse."""
    return get_strategy_optimization()


@router.get("/{report_id}", response_model=StrategyOptimizationReport)
def get_strategy_optimization_report_by_id(report_id: str):
    """Returns a single StrategyOptimizationReport by ID (e.g. optimizer-001)."""
    global _reports_store
    if not _reports_store:
        market_state = _market_state_engine.get_market_state()
        strategy_reports = _intelligence_engine.generate_reports(mission_repository)
        _reports_store = _optimizer.generate_optimization_reports(
            repository=mission_repository,
            strategy_reports=strategy_reports,
            market_state=market_state,
        )

    for r in _reports_store:
        if r.id == report_id or r.strategyId == report_id:
            return r

    raise HTTPException(
        status_code=404,
        detail=f"Strategy optimization report '{report_id}' not found",
    )
