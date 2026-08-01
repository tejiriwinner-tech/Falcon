from abc import ABC, abstractmethod
from datetime import datetime, timezone
from app.schemas.market_state import MarketSentiment
from app.core.events.event_bus import event_bus, SentimentUpdated

class SentimentProvider(ABC):
    @abstractmethod
    def get_sentiment(self) -> MarketSentiment:
        pass

class MockSentimentProvider(SentimentProvider):
    def __init__(self):
        self.provider_name = "MockSentimentProvider"
        self._last_refresh = datetime.now(timezone.utc)
        self.is_online = True
        self.latency_ms = 18

    def get_sentiment(self) -> MarketSentiment:
        now = datetime.now(timezone.utc)
        self._last_refresh = now
        
        sentiment = MarketSentiment(
            sentiment="Greedy",
            fearGreedIndex=72,
            institutionalBias="Long",
            retailPositioning="Short heavily",
            volumeProfileSummary="Value area migrating higher",
            provider=self.provider_name
        )
        
        event_bus.publish(SentimentUpdated(provider=self.provider_name))
        return sentiment
