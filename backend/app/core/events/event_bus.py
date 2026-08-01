from typing import Callable, Dict, List
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PriceUpdated:
    provider: str
    symbol: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class IndicatorsUpdated:
    provider: str
    symbol: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CalendarUpdated:
    provider: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class NewsUpdated:
    provider: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SentimentUpdated:
    provider: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MarketStateUpdated:
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# Union type alias for all events
Event = (
    PriceUpdated
    | IndicatorsUpdated
    | CalendarUpdated
    | NewsUpdated
    | SentimentUpdated
    | MarketStateUpdated
)


class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_type: type, callback: Callable) -> None:
        self._subscribers[event_type.__name__].append(callback)

    def publish(self, event: object) -> None:
        event_name = type(event).__name__
        for callback in self._subscribers.get(event_name, []):
            try:
                callback(event)
            except Exception:
                # In production this would be logged via the logging framework
                pass


# Global singleton event bus
event_bus = EventBus()
