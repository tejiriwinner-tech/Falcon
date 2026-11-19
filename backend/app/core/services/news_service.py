"""
Falcon News Service
Maps the stored economic calendar into the news contract shared by the
/news endpoint and the dashboard aggregate.
"""
import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Set

from app.core.services.economic_calendar_service import economic_calendar_service
from app.schemas.news import NewsItem, NewsListResponse


def _stable_news_id(key: str) -> int:
    """Deterministic positive 48-bit id (JS-safe), stable across processes."""
    return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)


def _currencies_for_symbols(symbols: Optional[List[str]]) -> Set[str]:
    currencies: Set[str] = set()
    for sym in symbols or []:
        s = str(sym or "").upper().replace("/", "").replace("_", "").strip()
        if not s:
            continue
        if s in ("GOLD", "XAUUSD"):
            currencies.update({"XAU", "USD"})
        elif len(s) == 6 and s.isalpha():
            currencies.update({s[:3], s[3:]})
        else:
            # Indices / crypto / unknown symbols are predominantly USD-driven.
            currencies.add("USD")
    return currencies


def build_news_response(
    lookback_hours: int = 24,
    lookahead_hours: int = 168,
    symbols: Optional[List[str]] = None,
) -> NewsListResponse:
    """Build news response using real economic calendar data.

    ``symbols`` is optional; when given, events are filtered to the currencies
    of those symbols (global / "ALL" events are always kept). Default
    behaviour (no symbols) is unchanged.
    """
    now = datetime.now(timezone.utc)
    
    # Get real economic calendar events
    try:
        economic_events = economic_calendar_service.get_events(
            lookback_hours=lookback_hours,
            lookahead_hours=lookahead_hours
        )
        
        # Convert EconomicEvent to NewsItem format
        wanted = _currencies_for_symbols(symbols) if symbols else None
        news_items = []
        for event in economic_events:
            if wanted:
                cur = str(getattr(event, "currency", "") or "").upper()
                if cur and cur not in wanted and cur not in ("ALL", "GLOBAL"):
                    continue
            news_items.append(
                NewsItem(
                    id=_stable_news_id(f"{event.eventTime}_{event.title}_{event.currency}"),
                    currency=event.currency,
                    title=event.title,
                    impact=event.impact,
                    time=event.eventTime,
                    forecast=event.forecast,
                    previous=event.previous,
                    actual=event.actual,
                    status="Upcoming" if event.actual is None else "Released"
                )
            )
        
        return NewsListResponse(
            events=news_items,
            lastUpdated=now,
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to fetch economic calendar: {e}")
        # Return empty response on error
        return NewsListResponse(
            events=[],
            lastUpdated=now,
        )
