from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List

from app.core.engines.market_regime_engine import MarketRegimeEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.market_regime import (
    MarketRegimeReport,
    MarketRegimeListResponse,
)

router = APIRouter(prefix="/market-regimes", tags=["market_regimes"])

_regime_engine = MarketRegimeEngine()
_regime_store: List[MarketRegimeReport] = []


@router.get("", response_model=MarketRegimeListResponse)
def get_market_regimes():
    """
    Runs the Market Regime Engine against the current state
    and returns a MarketRegimeListResponse.
    """
    global _regime_store
    _regime_store = _regime_engine.generate_reports(mission_repository)
    summary = _regime_engine.build_summary(_regime_store)

    return MarketRegimeListResponse(
        reports=_regime_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )


@router.get("/latest", response_model=MarketRegimeListResponse)
def get_latest_market_regimes():
    """Returns the latest MarketRegimeListResponse."""
    return get_market_regimes()


@router.get("/{report_id}", response_model=MarketRegimeReport)
def get_market_regime_by_id(report_id: str):
    """Returns a single MarketRegimeReport by ID."""
    global _regime_store
    if not _regime_store:
        _regime_store = _regime_engine.generate_reports(mission_repository)

    for r in _regime_store:
        if r.id == report_id:
            return r

    raise HTTPException(
        status_code=404,
        detail=f"Market regime report '{report_id}' not found",
    )
