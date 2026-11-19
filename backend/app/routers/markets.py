from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Query

from app.core.providers import provider_manager
from app.core.services.market_history_service import market_history_service
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
def get_markets(
    symbols: Optional[str] = Query(
        default=None, description="Comma-separated symbols; defaults to the watchlist"
    )
):
    """
    Live watchlist quotes from the provider framework.
    Falls back gracefully to the latest stored market bar on weekends or provider downtime,
    ensuring the Market Overview never disappears.
    """
    requested = (
        [s.strip() for s in symbols.split(",") if s.strip()]
        if symbols
        else DEFAULT_SYMBOLS
    )

    markets: List[MarketItem] = []
    for raw in requested:
        response = provider_manager.get_market_quote(raw)
        if response is not None and response.quote is not None:
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
        else:
            # Weekend / offline fallback: Pull latest stored Friday/historical close
            bars = market_history_service.get_bars(raw, "1h", limit=1)
            if bars:
                last_bar = bars[-1]
                markets.append(
                    MarketItem(
                        symbol=last_bar.symbol,
                        name=_DISPLAY_NAMES.get(last_bar.symbol, last_bar.symbol),
                        price=last_bar.close,
                        change=0.0,
                        changePercent=0.0,
                        isPositive=True,
                        marketStatus="CLOSED",
                    )
                )

    return MarketListResponse(
        markets=markets,
        lastUpdated=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
