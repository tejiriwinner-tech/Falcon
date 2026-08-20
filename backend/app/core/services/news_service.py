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
    events = economic_calendar_service.get_events(
        lookback_hours=lookback_hours, lookahead_hours=lookahead_hours
    )
    return NewsListResponse(
        events=[
            NewsItem(
                id=index,
                currency=event.currency,
                title=event.title,
                impact=event.impact,
                time=event.eventTime,
                forecast=event.forecast or None,
                previous=event.previous or None,
                actual=event.actual,
                status="Released" if event.actual is not None else "Upcoming",
            )
            for index, event in enumerate(events, start=1)
        ],
        lastUpdated=datetime.now(timezone.utc),
    )
