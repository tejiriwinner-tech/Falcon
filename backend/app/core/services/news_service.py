"""
Falcon News Service
Maps the stored economic calendar into the news contract shared by the
/news endpoint and the dashboard aggregate.
"""
from datetime import datetime, timezone

from app.core.services.economic_calendar_service import economic_calendar_service
from app.schemas.news import NewsItem, NewsListResponse


def build_news_response(
    lookback_hours: int = 24, lookahead_hours: int = 168
) -> NewsListResponse:
    """Build news response using real economic calendar data."""
    now = datetime.now(timezone.utc)
    
    # Get real economic calendar events
    try:
        economic_events = economic_calendar_service.get_events(
            lookback_hours=lookback_hours,
            lookahead_hours=lookahead_hours
        )
        
        # Convert EconomicEvent to NewsItem format
        news_items = []
        for event in economic_events:
            news_items.append(
                NewsItem(
                    id=hash(f"{event.eventTime}_{event.title}_{event.currency}"),
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
