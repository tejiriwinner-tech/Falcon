from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Query

from app.core.providers import provider_manager
from app.schemas.market import MarketItem, MarketListResponse

router = APIRouter()

DEFAULT_SYMBOLS = ["XAUUSD", "GBPUSD", "EURUSD", "GBPJPY", "USDJPY", "AUDUSD", "NAS100", "US30"]

_DISPLAY_NAMES = {
    "XAUUSD": "Gold",
    "GBPUSD": "British Pound",
    "EURUSD": "Euro",
    "GBPJPY": "GBP / JPY",
    "USDJPY": "Japanese Yen",
    "AUDUSD": "Australian Dollar",
    "NAS100": "Nasdaq 100",
    "US30": "Dow Jones 30",
    "BTCUSD": "Bitcoin",
    "ETHUSD": "Ethereum",
}


@router.get("", response_model=MarketListResponse)
async def get_markets(
    symbols: Optional[str] = Query(
        default=None, description="Comma-separated symbols; defaults to the watchlist"
    )
):
    """
    Live watchlist quotes from the provider framework. Symbols the providers
    cannot serve are omitted rather than filled with placeholder prices.
    """
    requested = (
        [s.strip() for s in symbols.split(",") if s.strip()]
        if symbols
        else DEFAULT_SYMBOLS
    )

    markets: List[MarketItem] = []
    for raw in requested:
        response = provider_manager.get_market_quote(raw)
        if response is None:
            continue
        quote = response.quote
        markets.append(
            MarketItem(
                symbol=quote.symbol,
                name=_DISPLAY_NAMES.get(quote.symbol, quote.symbol),
                price=quote.lastPrice,
                change=quote.change,
                changePercent=quote.changePercent,
                isPositive=quote.change >= 0,
                marketStatus=quote.marketStatus.value,
            )
        )

    return MarketListResponse(
        markets=markets,
        lastUpdated=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
