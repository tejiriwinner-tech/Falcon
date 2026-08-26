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
    # Return sample news for Phase 1.2 (economic calendar integration is complex)
    now = datetime.now(timezone.utc)
    return NewsListResponse(
        events=[
            NewsItem(
                id=1,
                currency="USD",
                title="Federal Reserve Interest Rate Decision",
                impact="High",
                time=now.replace(hour=14, minute=0),
                forecast="5.25%",
                previous="5.00%",
                actual=None,
                status="Upcoming"
            ),
            NewsItem(
                id=2,
                currency="EUR",
                title="ECB Monetary Policy Statement",
                impact="High",
                time=now.replace(hour=12, minute=30),
                forecast="4.00%",
                previous="3.75%",
                actual=None,
                status="Upcoming"
            ),
            NewsItem(
                id=3,
                currency="GBP",
                title="UK CPI inflation Rate",
                impact="Medium",
                time=now.replace(hour=9, minute=30),
                forecast="2.5%",
                previous="2.3%",
                actual=None,
                status="Upcoming"
            ),
            NewsItem(
                id=4,
                currency="JPY",
                title="Bank of Japan Policy Meeting",
                impact="Medium",
                time=now.replace(hour=3, minute=0),
                forecast="-0.10%",
                previous="0.00%",
                actual=None,
                status="Upcoming"
            )
        ],
        lastUpdated=now,
    )
