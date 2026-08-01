from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.mission_report import (
    MissionReport,
    MissionReportListResponse,
    MissionSummary,
    MissionStatus,
)

router = APIRouter()

# Module-level orchestrator so the mission counter persists across requests
_orchestrator = PipelineOrchestrator()

# In-memory store of completed missions (per process lifetime)
_mission_store: list[MissionReport] = []


@router.get("/missions", response_model=MissionReportListResponse)
def get_missions():
    """
    Runs the Pipeline Orchestrator once, stores the resulting MissionReport,
    and returns the full list of missions with an aggregate summary.

    This is the single entry point for downstream consumers that need the
    complete intelligence pipeline executed end-to-end.
    """
    report = _orchestrator.run_pipeline()
    _mission_store.append(report)

    return _build_list_response(_mission_store)


@router.get("/missions/{mission_id}", response_model=MissionReport)
def get_mission_by_id(mission_id: str):
    """
    Returns a single MissionReport by its deterministic ID (e.g. mission-001).
    The orchestrator is NOT re-run for this endpoint.
    """
    for mission in _mission_store:
        if mission.id == mission_id:
            return mission
    raise HTTPException(status_code=404, detail=f"Mission '{mission_id}' not found")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_list_response(missions: list[MissionReport]) -> MissionReportListResponse:
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
        missions=list(missions),
        summary=summary,
        lastUpdated=datetime.now(timezone.utc),
    )
