from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import time
from typing import List, Optional

from app.core.engines.market_regime_engine import MarketRegimeEngine
from app.core.engines.market_state_engine import MarketStateEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.market_regime import (
    MarketRegimeReport,
    MarketRegimeListResponse,
)

router = APIRouter(prefix="/market-regimes", tags=["market_regimes"])

_regime_engine = MarketRegimeEngine()
_market_state_engine = MarketStateEngine()
_regime_store: List[MarketRegimeReport] = []
_regime_cache: Optional[MarketRegimeListResponse] = None
_regime_cache_time: float = 0.0
_CACHE_TTL_SECONDS = 30.0


@router.get("", response_model=MarketRegimeListResponse)
def get_market_regimes():
    """
    Runs the Market Regime Engine against the current state
    and returns a MarketRegimeListResponse with in-memory caching.
    """
    global _regime_store, _regime_cache, _regime_cache_time
    now_mono = time.monotonic()
    if _regime_cache is not None and (now_mono - _regime_cache_time) < _CACHE_TTL_SECONDS:
        return _regime_cache

    market_state = _market_state_engine.get_market_state()
    _regime_store = _regime_engine.generate_reports(mission_repository, market_state=market_state)
    summary = _regime_engine.build_summary(_regime_store)

    response = MarketRegimeListResponse(
        reports=_regime_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )
    _regime_cache = response
    _regime_cache_time = now_mono
    return response


@router.get("/latest", response_model=MarketRegimeListResponse)
def get_latest_market_regimes():
    """Returns the latest MarketRegimeListResponse."""
    return get_market_regimes()


@router.get("/{report_id}", response_model=MarketRegimeReport)
def get_market_regime_by_id(report_id: str):
    """Returns a single MarketRegimeReport by ID."""
    global _regime_store
    if not _regime_store:
        market_state = _market_state_engine.get_market_state()
        _regime_store = _regime_engine.generate_reports(mission_repository, market_state=market_state)

    for r in _regime_store:
        if r.id == report_id:
            return r

    raise HTTPException(
        status_code=404,
        detail=f"Market regime report '{report_id}' not found",
    )
