"""Explicit control over Falcon's stored market data (history + calendar)."""

from typing import Dict, List, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.core.config import settings
from app.core.engines.market_state_engine import FALCON_WATCHLIST
from app.core.services.economic_calendar_service import economic_calendar_service
from app.core.services.market_history_service import market_history_service
from app.core.services.session_budget_manager import session_budget_manager

router = APIRouter(prefix="/market-data")


class PriceBarResponse(BaseModel):
    symbol: str
    timeframe: str
    barTime: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]
    provider: str


class RefreshResponse(BaseModel):
    barsStored: Dict[str, int]
    eventsStored: int
    historyProvidersConfigured: bool
    calendarConfigured: bool
    lastHistoryError: Optional[str]
    lastCalendarError: Optional[str]


@router.post("/refresh", response_model=RefreshResponse)
def refresh_market_data(
    symbols: Optional[List[str]] = Query(default=None),
    timeframe: Optional[str] = Query(default=None),
):
    """Pulls fresh history and calendar data from the configured providers."""
    stored = market_history_service.refresh_watchlist(
        symbols or FALCON_WATCHLIST, timeframe, force=True
    )
    events = economic_calendar_service.refresh(force=True)
    return RefreshResponse(
        barsStored=stored,
        eventsStored=events,
        historyProvidersConfigured=bool(
            settings.TWELVEDATA_API_KEY or settings.ALPHA_VANTAGE_API_KEY
        ),
        calendarConfigured=economic_calendar_service.configured,
        lastHistoryError=market_history_service.last_error,
        lastCalendarError=economic_calendar_service.last_error,
    )


from app.core.providers.symbol_mapper import symbol_mapper


@router.get("/history/{symbol:path}", response_model=List[PriceBarResponse])
def get_history(
    symbol: str,
    timeframe: Optional[str] = Query(default=None),
    limit: int = Query(200, ge=1, le=1000),
):
    """Returns stored bars for a symbol; empty when nothing has been backfilled."""
    canonical_symbol = symbol_mapper.normalize(symbol) or symbol.replace("/", "").replace("_", "").replace("-", "").strip().upper()
    norm_tf = (timeframe or "1h").lower()
    alias_map = {
        "m5": "5m",
        "m15": "15m",
        "m30": "30m",
        "h1": "1h",
        "h4": "4h",
        "d1": "1d",
    }
    effective_tf = alias_map.get(norm_tf, norm_tf)
    return [
        PriceBarResponse(
            symbol=bar.symbol,
            timeframe=bar.timeframe,
            barTime=bar.bar_time.isoformat(),
            open=bar.open,
            high=bar.high,
            low=bar.low,
            close=bar.close,
            volume=bar.volume,
            provider=bar.provider,
        )
        for bar in market_history_service.get_bars(canonical_symbol, effective_tf, limit)
    ]


@router.get("/session-budget")
def get_session_budget_status():
    """Returns current active trading session status, local time, and free tier budget mode."""
    return session_budget_manager.get_status()
