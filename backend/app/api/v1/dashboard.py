"""
Falcon API — Dashboard Endpoint
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from app.core.services.dashboard_service import dashboard_service
from app.schemas.dashboard import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard():
    """Return an aggregated immutable DashboardResponse."""
    return dashboard_service.get_dashboard()


@router.get("/ui", response_class=HTMLResponse)
def get_dashboard_ui():
    """Return the visual audit dashboard web UI."""
    from pathlib import Path
    html_path = Path(__file__).resolve().parent.parent.parent / "templates" / "dashboard.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Dashboard template not found</h1>", status_code=404)
