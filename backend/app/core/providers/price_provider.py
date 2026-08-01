from abc import ABC, abstractmethod
from typing import List, Dict
from datetime import datetime, timezone
from app.schemas.market_state import MarketPrice
from app.core.events.event_bus import event_bus, PriceUpdated

class PriceProvider(ABC):
    @abstractmethod
    def get_current_prices(self, symbols: List[str]) -> Dict[str, MarketPrice]:
        pass

    @abstractmethod
    def get_latest_candle(self, symbol: str, timeframe: str):
        pass

    @abstractmethod
    def get_market_snapshot(self, symbol: str):
        pass

class MockPriceProvider(PriceProvider):
    def __init__(self):
        self.provider_name = "MockPriceProvider"
        self._last_refresh = datetime.now(timezone.utc)
        self.is_online = True
        self.latency_ms = 15

    def get_current_prices(self, symbols: List[str]) -> Dict[str, MarketPrice]:
        now = datetime.now(timezone.utc)
        self._last_refresh = now
        prices = {}
        for symbol in symbols:
            # Mock data based on symbol
            if symbol == "XAU/USD":
                current, spread = 2350.50, 0.3
            elif symbol == "GBP/USD":
                current, spread = 1.2500, 0.8
            elif symbol == "EUR/USD":
                current, spread = 1.0800, 0.5
            else:
                current, spread = 100.0, 1.0

            prices[symbol] = MarketPrice(
                symbol=symbol,
                currentPrice=current,
                bid=current - (spread/2 * 0.01),
                ask=current + (spread/2 * 0.01),
                spread=spread,
                timestamp=now,
                provider=self.provider_name
            )
            # Fire event
            event_bus.publish(PriceUpdated(provider=self.provider_name, symbol=symbol))
            
        return prices

    def get_latest_candle(self, symbol: str, timeframe: str):
        return {"open": 100, "high": 102, "low": 98, "close": 101, "volume": 500}

    def get_market_snapshot(self, symbol: str):
        return {"symbol": symbol, "status": "Active", "session": "London"}
