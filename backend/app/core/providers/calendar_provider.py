from abc import ABC, abstractmethod
from typing import List
from datetime import datetime, timezone
from app.schemas.market_state import EconomicEvent
from app.core.events.event_bus import event_bus, CalendarUpdated
from app.core.services.economic_calendar_service import economic_calendar_service

class CalendarProvider(ABC):
    @abstractmethod
    def get_upcoming_events(self) -> List[EconomicEvent]:
        pass

class FMPCalendarProvider(CalendarProvider):
    """Economic calendar backed by Financial Modeling Prep and stored history."""

    def __init__(self):
        self.provider_name = "FinancialModelingPrep"
        self._last_refresh = datetime.now(timezone.utc)
        self.latency_ms = 0

    @property
    def is_online(self) -> bool:
        return economic_calendar_service.configured

    def get_upcoming_events(self) -> List[EconomicEvent]:
        started = datetime.now(timezone.utc)
        events = economic_calendar_service.get_events()
        self._last_refresh = datetime.now(timezone.utc)
        self.latency_ms = int((self._last_refresh - started).total_seconds() * 1000)
        event_bus.publish(CalendarUpdated(provider=self.provider_name))
        return events


calendar_provider: CalendarProvider = FMPCalendarProvider()
