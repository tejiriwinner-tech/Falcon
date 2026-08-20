from datetime import datetime, timezone

from fastapi import APIRouter, Query

from app.core.services.economic_calendar_service import economic_calendar_service
from app.schemas.news import NewsListResponse, NewsItem

router = APIRouter()


@router.get("", response_model=NewsListResponse)
def get_news(
    lookbackHours: int = Query(24, ge=0, le=720),
    lookaheadHours: int = Query(168, ge=0, le=720),
):
    """
    Returns the stored economic calendar from Financial Modeling Prep.

    Without ``FMP_API_KEY`` the calendar is empty rather than illustrative.
    """
    now = datetime.now(timezone.utc)
    events = economic_calendar_service.get_events(
        lookback_hours=lookbackHours, lookahead_hours=lookaheadHours
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
        lastUpdated=now,
    )
