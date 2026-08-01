from fastapi import APIRouter
from datetime import datetime, timezone
from app.schemas.news import NewsListResponse, NewsItem

router = APIRouter()

@router.get("", response_model=NewsListResponse)
def get_news():
    return NewsListResponse(
        events=[
            NewsItem(
                id=1,
                currency="USD",
                title="CPI",
                impact="High",
                time=datetime.now(timezone.utc),
                forecast="0.3%",
                previous="0.2%",
                actual=None,
                status="Upcoming"
            ),
            NewsItem(
                id=2,
                currency="GBP",
                title="Retail Sales",
                impact="Medium",
                time=datetime.now(timezone.utc),
                forecast="1.0%",
                previous="0.8%",
                actual=None,
                status="Upcoming"
            ),
            NewsItem(
                id=3,
                currency="EUR",
                title="ECB Press Conference",
                impact="Low",
                time=datetime.now(timezone.utc),
                forecast=None,
                previous=None,
                actual=None,
                status="Upcoming"
            )
        ],
        lastUpdated=datetime.now(timezone.utc)
    )
