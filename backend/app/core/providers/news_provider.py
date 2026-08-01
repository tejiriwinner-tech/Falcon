from abc import ABC, abstractmethod
from typing import List
from datetime import datetime, timezone, timedelta
from app.schemas.market_state import MarketNews
from app.core.events.event_bus import event_bus, NewsUpdated

class NewsProvider(ABC):
    @abstractmethod
    def get_market_news(self) -> List[MarketNews]:
        pass

class MockNewsProvider(NewsProvider):
    def __init__(self):
        self.provider_name = "MockNewsProvider"
        self._last_refresh = datetime.now(timezone.utc)
        self.is_online = True
        self.latency_ms = 35

    def get_market_news(self) -> List[MarketNews]:
        now = datetime.now(timezone.utc)
        self._last_refresh = now
        
        news = [
            MarketNews(
                title="Fed Chair Signals Potential Rate Cut",
                currency="USD",
                impact="High",
                sentiment="Bullish",
                publishedAt=now - timedelta(minutes=30),
                expiresAt=now + timedelta(hours=4),
                provider=self.provider_name
            ),
            MarketNews(
                title="ECB Maintains Current Stance",
                currency="EUR",
                impact="Medium",
                sentiment="Neutral",
                publishedAt=now - timedelta(hours=2),
                expiresAt=now + timedelta(hours=12),
                provider=self.provider_name
            )
        ]
        
        event_bus.publish(NewsUpdated(provider=self.provider_name))
        return news
