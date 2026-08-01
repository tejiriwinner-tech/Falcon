from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Dict, Any

from app.core.repository.mission_repository import mission_repository
from app.schemas.repository_statistics import RepositoryStatistics
from app.schemas.mission_report import (
    MissionReport,
    MissionReportListResponse,
    MissionSummary,
    MissionStatus,
)

router = APIRouter(prefix="/repository", tags=["repository"])


@router.get("/statistics", response_model=RepositoryStatistics)
def get_repository_statistics():
    """
    Returns current RepositoryStatistics for Falcon's long-term memory layer.
    """
    return mission_repository.get_statistics()


@router.get("/missions", response_model=MissionReportListResponse)
def get_archived_missions():
    """
    Returns all archived MissionReports from long-term storage along with an aggregate summary.
    """
    missions = mission_repository.get_all_missions()
    total = len(missions)
    successful = sum(1 for m in missions if m.status == MissionStatus.SUCCESS)
    partial = sum(1 for m in missions if m.status == MissionStatus.PARTIAL_SUCCESS)
    failed = sum(1 for m in missions if m.status == MissionStatus.FAILED)

    durations = [m.performance.totalDurationMs for m in missions]
    avg_duration = round(sum(durations) / total, 2) if total > 0 else 0.0

    healths = [m.health.pipelineHealthPercentage for m in missions]
    avg_health = round(sum(healths) / total, 2) if total > 0 else 0.0

    summary = MissionSummary(
        totalMissions=total,
        successful=successful,
        partialSuccess=partial,
        failed=failed,
        averageDurationMs=avg_duration,
        averagePipelineHealth=avg_health,
    )

    return MissionReportListResponse(
        missions=missions,
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )


@router.get("/missions/{mission_id}", response_model=MissionReport)
def get_archived_mission_by_id(mission_id: str):
    """
    Returns a single archived MissionReport by its ID.
    """
    mission = mission_repository.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Archived mission '{mission_id}' not found")
    return mission


@router.get("/artifacts/{mission_id}", response_model=Dict[str, Any])
def get_mission_artifacts(mission_id: str):
    """
    Returns all immutable pipeline artifacts associated with a specific mission ID.
    """
    mission = mission_repository.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Archived mission '{mission_id}' not found")
    return mission_repository.get_mission_artifacts(mission_id)
