from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List

from app.core.analytics.performance_analytics_engine import PerformanceAnalyticsEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.analytics_report import AnalyticsReport, AnalyticsSummaryResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])

_analytics_engine = PerformanceAnalyticsEngine()
_reports_store: List[AnalyticsReport] = []


@router.get("", response_model=AnalyticsSummaryResponse)
def get_analytics():
    """
    Generates an AnalyticsReport from MissionRepository, stores it in long-term reports history,
    and returns AnalyticsSummaryResponse.
    """
    report = _analytics_engine.generate_report(mission_repository)
    _reports_store.append(report)

    return AnalyticsSummaryResponse(
        reports=list(_reports_store),
        lastGenerated=datetime.now(timezone.utc),
        repositoryVersion="1.0.0",
    )


@router.get("/latest", response_model=AnalyticsReport)
def get_latest_analytics_report():
    """
    Generates and returns the latest AnalyticsReport based on current repository state.
    """
    report = _analytics_engine.generate_report(mission_repository)
    _reports_store.append(report)
    return report


@router.get("/{analytics_id}", response_model=AnalyticsReport)
def get_analytics_report_by_id(analytics_id: str):
    """
    Returns a previously generated AnalyticsReport by ID.
    If not in cache, generates a new report and checks ID.
    """
    for r in _reports_store:
        if r.id == analytics_id:
            return r

    # Generate fresh if store is empty
    report = get_latest_analytics_report()
    if report.id == analytics_id:
        return report

    raise HTTPException(status_code=404, detail=f"Analytics report '{analytics_id}' not found")
