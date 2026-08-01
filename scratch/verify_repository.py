import sys
import os
from io import StringIO

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.repository.mission_repository import mission_repository
from app.schemas.mission_report import MissionReport


def verify_repository():
    print("=== Falcon Phase 3.1 Verification: Mission History & Artifact Repository ===")

    # Clear repository before starting verification test
    mission_repository.clear_repository()
    orchestrator = PipelineOrchestrator()

    # Capture stdout to verify printed MissionArchived events
    old_stdout = sys.stdout
    captured = StringIO()
    sys.stdout = captured

    try:
        m1: MissionReport = orchestrator.run_pipeline()
        m2: MissionReport = orchestrator.run_pipeline()
        m3: MissionReport = orchestrator.run_pipeline()
    finally:
        sys.stdout = old_stdout

    logs = captured.getvalue()

    # 1. Repository Persistence & Mission Count
    print("\n1. Testing Repository Persistence:")
    missions = mission_repository.get_all_missions()
    assert len(missions) == 3, f"Expected 3 missions, got {len(missions)}"
    assert m1.id == "mission-001" and m2.id == "mission-002" and m3.id == "mission-003"
    print(f"   [OK] Stored Missions Count: {len(missions)} ({m1.id}, {m2.id}, {m3.id})")

    # 2. Artifact Counts
    print("\n2. Testing Stored Artifact Counts:")
    stats = mission_repository.get_statistics()
    assert stats.totalMissions == 3, f"Expected totalMissions=3, got {stats.totalMissions}"
    assert stats.totalMarketStates == 3, f"Expected totalMarketStates=3, got {stats.totalMarketStates}"
    assert stats.totalCandidates == 12, f"Expected totalCandidates=12, got {stats.totalCandidates}"
    assert stats.totalValidations == 12, f"Expected totalValidations=12, got {stats.totalValidations}"
    assert stats.totalRiskAssessments == 12, f"Expected totalRiskAssessments=12, got {stats.totalRiskAssessments}"
    assert stats.totalExecutionReadiness == 12, f"Expected totalExecutionReadiness=12, got {stats.totalExecutionReadiness}"
    assert stats.totalDecisions == 12, f"Expected totalDecisions=12, got {stats.totalDecisions}"

    print(f"   [OK] Market States: {stats.totalMarketStates}")
    print(f"   [OK] Signal Candidates: {stats.totalCandidates}")
    print(f"   [OK] Validation Results: {stats.totalValidations}")
    print(f"   [OK] Risk Assessments: {stats.totalRiskAssessments}")
    print(f"   [OK] Execution Readiness: {stats.totalExecutionReadiness}")
    print(f"   [OK] Decision Artifacts: {stats.totalDecisions}")

    # 3. Immutability Verification (Deep Copy Protection)
    print("\n3. Testing Immutability & Deep Copy Protection:")
    retrieved_m1 = mission_repository.get_mission("mission-001")
    assert retrieved_m1 is not None, "Failed to retrieve mission-001"
    
    # Mutate retrieved object property
    retrieved_m1.id = "MUTATED-ID"
    retrieved_m1.performance.totalDurationMs = 999999

    # Re-fetch from repository and verify original is intact
    stored_m1 = mission_repository.get_mission("mission-001")
    assert stored_m1.id == "mission-001", "Repository object was mutated!"
    assert stored_m1.performance.totalDurationMs != 999999, "Repository sub-object was mutated!"
    print("   [OK] Repository objects remain strictly immutable after retrieval and mutation attempts")

    # 4. Repository Statistics Verification
    print("\n4. Testing Repository Health & Timestamps:")
    assert stats.repositoryHealth == 100.0, f"Expected health=100.0%, got {stats.repositoryHealth}%"
    assert stats.startedAt is not None, "startedAt is None"
    assert stats.lastMissionAt is not None, "lastMissionAt is None"
    print(f"   [OK] Repository Health: {stats.repositoryHealth}%")
    print(f"   [OK] Started At: {stats.startedAt.isoformat()}")
    print(f"   [OK] Last Mission At: {stats.lastMissionAt.isoformat()}")

    # 5. MissionArchived Events Verification
    print("\n5. Testing MissionArchived Event Bus Emission:")
    assert "MissionArchived" in logs, "Missing MissionArchived event in event bus logs"
    assert "artifactsStored" in logs, "Missing artifactsStored field in MissionArchived payload"
    archived_count = logs.count("MissionArchived")
    assert archived_count == 3, f"Expected 3 MissionArchived events, got {archived_count}"
    print("   [OK] MissionArchived event emitted 3 times with complete artifact counts")

    # 6. Artifact Retrieval API Endpoint Verification
    print("\n6. Testing Mission Artifact Bundle Retrieval:")
    m1_artifacts = mission_repository.get_mission_artifacts("mission-001")
    assert m1_artifacts["missionId"] == "mission-001"
    assert m1_artifacts["marketState"] is not None
    assert len(m1_artifacts["candidates"]) == 4
    assert len(m1_artifacts["validations"]) == 4
    assert len(m1_artifacts["riskAssessments"]) == 4
    assert len(m1_artifacts["executionReadiness"]) == 4
    assert len(m1_artifacts["decisions"]) == 4
    print("   [OK] get_mission_artifacts('mission-001') returned complete immutable artifact bundle")

    print("\nSUCCESS: ALL REPOSITORY VERIFICATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    verify_repository()
