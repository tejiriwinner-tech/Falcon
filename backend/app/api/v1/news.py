from fastapi import APIRouter, Query

from app.core.services.news_service import build_news_response
from app.schemas.news import NewsListResponse

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
    return build_news_response(
        lookback_hours=lookbackHours, lookahead_hours=lookaheadHours
    )
