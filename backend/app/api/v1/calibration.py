from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import List

from app.core.engines.calibration_engine import CalibrationEngine
from app.core.repository.mission_repository import mission_repository
from app.schemas.calibration_report import (
    CalibrationReport,
    CalibrationReportListResponse,
)

router = APIRouter(prefix="/calibration", tags=["calibration"])

_calibration_engine = CalibrationEngine()
_calibration_store: List[CalibrationReport] = []


@router.get("", response_model=CalibrationReportListResponse)
def get_calibration_reports():
    """Run the Calibration Engine and return all CalibrationReports."""
    global _calibration_store
    _calibration_store = _calibration_engine.generate_reports(mission_repository)
    summary = _calibration_engine.build_summary(_calibration_store)
    return CalibrationReportListResponse(
        reports=_calibration_store,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )


@router.get("/latest", response_model=CalibrationReportListResponse)
def get_latest_calibration():
    """Returns the latest CalibrationReportListResponse."""
    return get_calibration_reports()


@router.get("/{report_id}", response_model=CalibrationReport)
def get_calibration_by_id(report_id: str):
    """Returns a single CalibrationReport by ID."""
    global _calibration_store
    if not _calibration_store:
        _calibration_store = _calibration_engine.generate_reports(mission_repository)

    for r in _calibration_store:
        if r.id == report_id:
            return r

    raise HTTPException(
        status_code=404,
        detail=f"Calibration report '{report_id}' not found",
    )
