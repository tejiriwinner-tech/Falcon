"""
Falcon API — Dashboard Endpoint
"""
from fastapi import APIRouter
from app.core.services.dashboard_service import dashboard_service
from app.schemas.dashboard import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard():
    """Return an aggregated immutable DashboardResponse."""
    return dashboard_service.get_dashboard()
