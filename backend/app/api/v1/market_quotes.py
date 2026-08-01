"""
Falcon API Layer — Market Quotes Router
Provides endpoints for retrieving live market quotes and dynamic watchlists.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.core.providers import provider_manager
from app.schemas.market_quote import MarketQuoteResponse, MarketQuote

router = APIRouter(prefix="/market-quotes", tags=["market-quotes"])


@router.get("", response_model=List[str])
def get_supported_symbols():
    """Return list of canonical symbols supported by the provider framework."""
    return provider_manager.supported_symbols()


@router.get("/watchlist", response_model=List[MarketQuote])
def get_watchlist(
    symbols: Optional[str] = Query(
        default="XAUUSD,GBPUSD,EURUSD,USDJPY,NAS100,US30",
        description="Comma-separated symbols"
    )
):
    """Return normalized quotes for requested watchlist symbols in exact order, ignoring duplicates."""
    if not symbols:
        raw_list = ["XAUUSD", "GBPUSD", "EURUSD", "USDJPY", "NAS100", "US30"]
    else:
        raw_list = [s.strip() for s in symbols.split(",") if s.strip()]

    seen = set()
    unique_symbols = []
    for sym in raw_list:
        upper = sym.upper()
        if upper not in seen:
            seen.add(upper)
            unique_symbols.append(sym)

    quotes: List[MarketQuote] = []
    for raw in unique_symbols:
        resp = provider_manager.get_market_quote(raw)
        if resp is not None:
            quotes.append(resp.quote)

    return quotes


@router.get("/{symbol}", response_model=MarketQuoteResponse)
def get_market_quote(symbol: str):
    """Return a single MarketQuoteResponse for the given symbol or alias."""
    resp = provider_manager.get_market_quote(symbol)
    if resp is None:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found or unavailable")
    return resp
