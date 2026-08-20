from fastapi import APIRouter

from app.core.services.performance_analytics_service import build_performance_analytics
from app.schemas.performance_analytics import PerformanceAnalyticsResponse

router = APIRouter()


@router.get("/performance-analytics", response_model=PerformanceAnalyticsResponse)
def get_performance_analytics():
    """
    Returns performance analytics computed from the stored trade journal.

    Equity is measured against ``STARTING_EQUITY``; an empty journal returns
    zeroed statistics.
    """
    return build_performance_analytics()
