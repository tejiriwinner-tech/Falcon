from abc import ABC, abstractmethod
from typing import List
from datetime import datetime, timezone, timedelta
from app.schemas.market_state import EconomicEvent
from app.core.events.event_bus import event_bus, CalendarUpdated

class CalendarProvider(ABC):
    @abstractmethod
    def get_upcoming_events(self) -> List[EconomicEvent]:
        pass

class MockCalendarProvider(CalendarProvider):
    def __init__(self):
        self.provider_name = "MockCalendarProvider"
        self._last_refresh = datetime.now(timezone.utc)
        self.is_online = True
        self.latency_ms = 40

    def get_upcoming_events(self) -> List[EconomicEvent]:
        now = datetime.now(timezone.utc)
        self._last_refresh = now
        
        events = [
            EconomicEvent(
                title="Non-Farm Employment Change",
                currency="USD",
                impact="High",
                eventTime=now + timedelta(minutes=120),
                countdownMinutes=120,
                forecast="180K",
                previous="175K",
                provider=self.provider_name
            ),
            EconomicEvent(
                title="Core CPI m/m",
                currency="USD",
                impact="High",
                eventTime=now + timedelta(hours=24),
                countdownMinutes=1440,
                forecast="0.3%",
                previous="0.4%",
                provider=self.provider_name
            )
        ]
        
        event_bus.publish(CalendarUpdated(provider=self.provider_name))
        return events
