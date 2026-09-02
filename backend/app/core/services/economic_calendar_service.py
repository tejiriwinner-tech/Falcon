"""Economic calendar sourced from Financial Modeling Prep and stored for reuse.

Events are fetched at most once every ``CALENDAR_CACHE_SECONDS`` and persisted to
the ``economic_events`` table, so the pipeline and the learning engines read the
same history even when the provider is unreachable or the API key is absent.
"""

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.core.config.provider_settings import REQUEST_TIMEOUT_SECONDS
from app.core.database import EconomicEventRecord, database_enabled, get_session
from app.schemas.market_state import EconomicEvent

PROVIDER_NAME = "FinancialModelingPrep"

_IMPACT_BY_FMP_IMPACT = {
    "high": "High",
    "medium": "Medium",
    "low": "Low",
    "holiday": "Low",
    "none": "Low",
}


class _StoredEvent:
    """Normalised calendar event independent of the storage backend."""

    __slots__ = ("event_time", "currency", "title", "impact", "forecast", "previous", "actual")

    def __init__(
        self,
        event_time: datetime,
        currency: str,
        title: str,
        impact: str,
        forecast: Optional[str],
        previous: Optional[str],
        actual: Optional[str],
    ):
        self.event_time = event_time
        self.currency = currency
        self.title = title
        self.impact = impact
        self.forecast = forecast
        self.previous = previous
        self.actual = actual

    @property
    def key(self) -> tuple:
        return (self.event_time, self.currency, self.title)


def _as_text(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)[:64]


def _parse_event_time(raw: str) -> Optional[datetime]:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _normalize(payload: List[Dict[str, Any]]) -> List[_StoredEvent]:
    events: List[_StoredEvent] = []
    for row in payload:
        event_time = _parse_event_time(str(row.get("date", "")))
        currency = str(row.get("country") or row.get("currency") or "").strip().upper()
        title = str(row.get("event") or "").strip()
        if event_time is None or not title or not currency:
            continue
        impact = _IMPACT_BY_FMP_IMPACT.get(str(row.get("impact", "")).lower(), "Low")
        events.append(
            _StoredEvent(
                event_time=event_time,
                currency=currency[:8],
                title=title[:255],
                impact=impact,
                forecast=_as_text(row.get("estimate")),
                previous=_as_text(row.get("previous")),
                actual=_as_text(row.get("actual")),
            )
        )
    return events


class EconomicCalendarService:
    """Fetches, stores and serves the economic calendar."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._memory: Dict[tuple, _StoredEvent] = {}
        self._last_fetch_monotonic: Optional[float] = None
        self.last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Provider access
    # ------------------------------------------------------------------

    @property
    def configured(self) -> bool:
        return bool(settings.FMP_API_KEY)

    def _fetch_remote(self) -> List[_StoredEvent]:
        if not self.configured:
            self.last_error = "FMP_API_KEY is not configured"
            return []
        now = datetime.now(timezone.utc)
        params = {
            "from": now.date().isoformat(),
            "to": (now + timedelta(days=settings.CALENDAR_LOOKAHEAD_DAYS)).date().isoformat(),
            "apikey": settings.FMP_API_KEY,
        }
        try:
            base = settings.FMP_BASE_URL.rstrip('/')
            endpoint = f"{base}/economic-calendar" if "stable" in base else f"{base}/v3/economic_calendar"
            response = requests.get(
                endpoint,
                params=params,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            return []
        if not isinstance(payload, list):
            self.last_error = f"Unexpected calendar payload: {type(payload).__name__}"
            return []
        self.last_error = None
        return _normalize(payload)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    def _store(self, events: List[_StoredEvent]) -> int:
        if not events:
            return 0
        stored_at = datetime.now(timezone.utc)
        if not database_enabled():
            with self._lock:
                for event in events:
                    self._memory[event.key] = event
            return len(events)
        rows = [
            {
                "event_time": event.event_time,
                "currency": event.currency,
                "title": event.title,
                "impact": event.impact,
                "forecast": event.forecast,
                "previous": event.previous,
                "actual": event.actual,
                "provider": PROVIDER_NAME,
                "stored_at": stored_at,
            }
            for event in events
        ]
        statement = pg_insert(EconomicEventRecord).values(rows)
        statement = statement.on_conflict_do_update(
            constraint="uq_economic_events_time_currency_title",
            set_={
                "impact": statement.excluded.impact,
                "forecast": statement.excluded.forecast,
                "previous": statement.excluded.previous,
                "actual": statement.excluded.actual,
                "stored_at": statement.excluded.stored_at,
            },
        )
        with get_session() as session, session.begin():
            session.execute(statement)
        return len(rows)

    def _load(self, since: datetime, until: datetime) -> List[_StoredEvent]:
        if not database_enabled():
            with self._lock:
                return sorted(
                    (e for e in self._memory.values() if since <= e.event_time <= until),
                    key=lambda e: e.event_time,
                )
        with get_session() as session:
            records = session.scalars(
                select(EconomicEventRecord)
                .where(EconomicEventRecord.event_time >= since)
                .where(EconomicEventRecord.event_time <= until)
                .order_by(EconomicEventRecord.event_time)
            ).all()
        return [
            _StoredEvent(
                event_time=record.event_time,
                currency=record.currency,
                title=record.title,
                impact=record.impact,
                forecast=record.forecast,
                previous=record.previous,
                actual=record.actual,
            )
            for record in records
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self, force: bool = False) -> int:
        """Pulls the calendar from FMP, honouring the cache window."""
        with self._lock:
            fresh = (
                self._last_fetch_monotonic is not None
                and time.monotonic() - self._last_fetch_monotonic
                < settings.CALENDAR_CACHE_SECONDS
            )
        if fresh and not force:
            return 0
        events = self._fetch_remote()
        stored = self._store(events)
        with self._lock:
            self._last_fetch_monotonic = time.monotonic()
        return stored

    def get_events(self, lookback_hours: int = 0, lookahead_hours: int = 168) -> List[EconomicEvent]:
        """Returns stored events as pipeline artifacts, refreshing when stale."""
        self.refresh()
        now = datetime.now(timezone.utc)
        stored = self._load(
            now - timedelta(hours=lookback_hours), now + timedelta(hours=lookahead_hours)
        )
        events: List[EconomicEvent] = []
        for record in stored:
            event_time = record.event_time
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
            countdown = int((event_time - now).total_seconds() // 60)
            events.append(
                EconomicEvent(
                    title=record.title,
                    currency=record.currency,
                    impact=record.impact,
                    eventTime=event_time,
                    countdownMinutes=countdown,
                    forecast=record.forecast or "",
                    previous=record.previous or "",
                    actual=record.actual,
                    provider=PROVIDER_NAME,
                )
            )
        return events


economic_calendar_service = EconomicCalendarService()
