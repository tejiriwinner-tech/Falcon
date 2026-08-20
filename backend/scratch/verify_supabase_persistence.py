"""Manual check: run a mission, then read it back through a fresh repository.

Usage:
    DATABASE_URL=postgresql://... python scratch/verify_supabase_persistence.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator  # noqa: E402
from app.core.repository.mission_repository import MissionRepository, mission_repository  # noqa: E402


def main() -> int:
    if not mission_repository.persistent:
        print("DATABASE_URL is not configured — repository is in-memory")
        return 1

    before = mission_repository.count_missions()
    report = PipelineOrchestrator().run_pipeline()
    print(f"ran mission {report.id} (missions before={before})")

    # Fresh instance, fresh session: proves the data came back from Postgres.
    MissionRepository._instance = None
    reloaded = MissionRepository()

    mission = reloaded.get_mission(report.id)
    assert mission is not None, "mission not persisted"
    assert mission.status == report.status

    artifacts = reloaded.get_mission_artifacts(report.id)
    assert artifacts["marketState"] is not None, "market state not persisted"
    for key in ("candidates", "validations", "riskAssessments", "executionReadiness", "decisions"):
        print(f"  {key}: {len(artifacts[key])}")

    stats = reloaded.get_statistics()
    print(stats.model_dump_json(indent=2))
    assert stats.totalMissions == before + 1
    print("OK — mission and artifacts survived a repository restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
