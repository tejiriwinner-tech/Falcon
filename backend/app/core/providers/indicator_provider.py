from abc import ABC, abstractmethod
from typing import List, Dict
from app.schemas.market_state import Indicator
from app.core.events.event_bus import event_bus, IndicatorsUpdated
from datetime import datetime, timezone

class IndicatorProvider(ABC):
    @abstractmethod
    def get_indicators(self, symbol: str) -> List[Indicator]:
        pass

    @abstractmethod
    def calculate_market_strength(self, symbol: str) -> float:
        pass

class MockIndicatorProvider(IndicatorProvider):
    def __init__(self):
        self.provider_name = "MockIndicatorProvider"
        self._last_refresh = datetime.now(timezone.utc)
        self.is_online = True
        self.latency_ms = 22

    def get_indicators(self, symbol: str) -> List[Indicator]:
        self._last_refresh = datetime.now(timezone.utc)
        indicators = [
            Indicator(name="EMA20", value=1.0850, signal="Bullish", provider=self.provider_name),
            Indicator(name="EMA50", value=1.0820, signal="Bullish", provider=self.provider_name),
            Indicator(name="EMA200", value=1.0750, signal="Bullish", provider=self.provider_name),
            Indicator(name="RSI", value=65.5, signal="Neutral", provider=self.provider_name),
            Indicator(name="ATR", value=0.0015, signal="Volatile", provider=self.provider_name),
            Indicator(name="ADX", value=35.0, signal="Strong Trend", provider=self.provider_name),
            Indicator(name="MACD", value=0.002, signal="Bullish", provider=self.provider_name),
            Indicator(name="Bollinger Bands", value=1.0900, signal="Upper Band", provider=self.provider_name),
            Indicator(name="Trend Direction", value=1.0, signal="Up", provider=self.provider_name),
        ]
        
        event_bus.publish(IndicatorsUpdated(provider=self.provider_name, symbol=symbol))
        return indicators

    def calculate_market_strength(self, symbol: str) -> float:
        return 75.0
