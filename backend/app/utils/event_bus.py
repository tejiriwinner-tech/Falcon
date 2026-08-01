from datetime import datetime, timezone
from pydantic import BaseModel
from typing import List

class EventLog(BaseModel):
    timestamp: datetime
    eventName: str
    description: str

class EventBus:
    _history: List[EventLog] = []

    @classmethod
    def publish(cls, event_name: str, description: str):
        log = EventLog(
            timestamp=datetime.now(timezone.utc),
            eventName=event_name,
            description=description
        )
        cls._history.append(log)
        # Prune history to keep last 50 events
        if len(cls._history) > 50:
            cls._history.pop(0)

    @classmethod
    def get_history(cls) -> List[EventLog]:
        return cls._history
