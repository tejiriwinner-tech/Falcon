from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.repository.mission_repository import mission_repository
from app.schemas.mission_report import (
    MissionReport,
    MissionReportListResponse,
    MissionSummary,
    MissionStatus,
)

router = APIRouter()

# Module-level orchestrator so the mission counter persists across requests
_orchestrator = PipelineOrchestrator()


@router.get("/missions", response_model=MissionReportListResponse)
def get_missions(limit: int = 20):
    """
    Returns stored missions (newest first, limited to `limit` items) with an aggregate summary.

    Read-only: POST /missions/run executes the intelligence pipeline.
    """
    all_missions = mission_repository.get_all_missions()
    # Sort newest first
    sorted_missions = list(reversed(all_missions))
    return _build_list_response(
        missions=sorted_missions[:limit],
        all_missions=all_missions,
    )


@router.post("/missions/purge")
def purge_old_missions(keep_latest: int = 10):
    """
    Purges old historical missions and their associated artifacts, keeping only the latest N.
    """
    deleted = mission_repository.prune_missions(keep_latest=keep_latest)
    return {
        "status": "success",
        "message": f"Purged old missions. Kept latest {keep_latest}.",
        "deletedCount": deleted,
        "remainingCount": mission_repository.count_missions(),
    }


@router.post("/missions/run", response_model=MissionReport, status_code=201)
def run_mission():
    """
    Runs the Pipeline Orchestrator once and returns the stored MissionReport.
    """
    return _orchestrator.run_pipeline()


@router.get("/missions/{mission_id}", response_model=MissionReport)
def get_mission_by_id(mission_id: str):
    """
    Returns a single MissionReport by its deterministic ID (e.g. mission-001).
    The orchestrator is NOT re-run for this endpoint.
    """
    mission = mission_repository.get_mission(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")
    return mission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_list_response(
    missions: list[MissionReport],
    all_missions: list[MissionReport] | None = None,
) -> MissionReportListResponse:
    stats_pool = all_missions if all_missions is not None else missions
    total = len(stats_pool)
    successful = sum(1 for m in stats_pool if m.status == MissionStatus.SUCCESS)
    partial = sum(1 for m in stats_pool if m.status == MissionStatus.PARTIAL_SUCCESS)
    failed = sum(1 for m in stats_pool if m.status == MissionStatus.FAILED)

    durations = [m.performance.totalDurationMs for m in stats_pool]
    avg_duration = round(sum(durations) / total, 2) if total > 0 else 0.0

    healths = [m.health.pipelineHealthPercentage for m in stats_pool]
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
        missions=list(missions),
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )
