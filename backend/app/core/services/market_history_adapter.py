"""
Market History Adapter

Bridges price_history (canonical storage) to the signal pipeline's expected
MarketCandle format. This adapter allows the signal pipeline to consume data from
price_history without modifying the existing signal-generation business logic.
"""

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.database.models import PriceBarRecord
from app.core.services.market_history_service import PriceBar, market_history_service
from app.models.market_candle import MarketCandle, Timeframe


class MarketHistoryAdapter:
    """Adapter to make price_history compatible with signal pipeline."""

    # Timeframe mapping: signal pipeline Timeframe enum → price_history string format
    _TIMEFRAME_MAPPING = {
        Timeframe.M1: "1m",
        Timeframe.M5: "5m",
        Timeframe.M15: "15m",
        Timeframe.M30: "30m",
        Timeframe.H1: "1h",
        Timeframe.H4: "4h",
        Timeframe.D1: "1d",
    }

    def __init__(self, db: Session):
        """
        Initialize the adapter with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_latest_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 100
    ) -> List[MarketCandle]:
        """
        Get candles from price_history and convert to MarketCandle format.

        This method maintains the same interface as HistoryService.get_latest_candles()
        to ensure compatibility with the existing signal pipeline.

        Args:
            symbol: Canonical symbol (e.g., "XAUUSD")
            timeframe: Timeframe enum
            limit: Maximum candles to return

        Returns:
            List of MarketCandle objects (most recent first)
        """
        # Convert Timeframe enum to string format used by price_history
        timeframe_str = self._convert_timeframe(timeframe)

        # Get PriceBar objects from price_history
        price_bars = market_history_service.get_bars(symbol, timeframe_str, limit)

        # Convert PriceBar to MarketCandle (most recent first)
        candles = [
            self._price_bar_to_candle(bar, timeframe)
            for bar in reversed(price_bars)
        ]

        return candles

    def _convert_timeframe(self, timeframe: Timeframe) -> str:
        """
        Convert Timeframe enum to price_history string format.

        Args:
            timeframe: Timeframe enum

        Returns:
            String format expected by price_history
        """
        return self._TIMEFRAME_MAPPING.get(timeframe, "1h")

    def _price_bar_to_candle(
        self,
        price_bar: PriceBar,
        timeframe: Timeframe
    ) -> MarketCandle:
        """
        Convert PriceBar to MarketCandle format.

        This conversion handles:
        - Symbol preservation
        - Timeframe enum conversion
        - UTC timestamp preservation
        - Volume null → 0.0 handling
        - Provider field preservation

        Args:
            price_bar: PriceBar object from price_history
            timeframe: Target Timeframe enum

        Returns:
            MarketCandle object compatible with signal pipeline
        """
        return MarketCandle(
            symbol=price_bar.symbol,
            timeframe=timeframe.value,
            open=price_bar.open,
            high=price_bar.high,
            low=price_bar.low,
            close=price_bar.close,
            volume=price_bar.volume if price_bar.volume is not None else 0.0,
            provider=price_bar.provider,
            timestamp=price_bar.bar_time
        )


# Singleton instance for backward compatibility with service patterns
market_history_adapter = None


def get_market_history_adapter(db: Session) -> MarketHistoryAdapter:
    """
    Factory function to get or create the market history adapter.

    Args:
        db: SQLAlchemy database session

    Returns:
        MarketHistoryAdapter instance
    """
    global market_history_adapter
    if market_history_adapter is None:
        market_history_adapter = MarketHistoryAdapter(db)
    else:
        market_history_adapter.db = db
    return market_history_adapter
