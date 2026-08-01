import sys
import os
from io import StringIO

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.mission_report import MissionReport, MissionStatus


def verify_mission():
    print("=== Falcon Phase 2.7 Verification: Pipeline Orchestrator & Mission Report ===")

    orchestrator = PipelineOrchestrator()

    # Capture stdout to verify printed events
    old_stdout = sys.stdout
    captured = StringIO()
    sys.stdout = captured

    try:
        mission1: MissionReport = orchestrator.run_pipeline()
        mission2: MissionReport = orchestrator.run_pipeline()
    finally:
        sys.stdout = old_stdout

    logs = captured.getvalue()

    # 1. Deterministic IDs & Numbers
    print("\n1. Testing Deterministic IDs & Sequential Mission Numbers:")
    assert mission1.id == "mission-001", f"Expected mission-001, got {mission1.id}"
    assert mission1.missionNumber == 1, f"Expected missionNumber=1, got {mission1.missionNumber}"
    assert mission2.id == "mission-002", f"Expected mission-002, got {mission2.id}"
    assert mission2.missionNumber == 2, f"Expected missionNumber=2, got {mission2.missionNumber}"
    print(f"   [OK] Mission 1 ID: {mission1.id}, Mission # {mission1.missionNumber}")
    print(f"   [OK] Mission 2 ID: {mission2.id}, Mission # {mission2.missionNumber}")

    # 2. Correct Execution Order & Timeline
    print("\n2. Testing Execution Order & Timeline Events:")
    expected_order = ["MARKET", "SIGNAL", "VALIDATION", "RISK", "EXECUTION", "DECISION"]
    actual_order = [e.stage for e in mission1.timeline]
    assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"
    print(f"   [OK] Execution Stage Order: {' -> '.join(actual_order)}")

    # Check stage timeline order values & status
    for i, event in enumerate(mission1.timeline, 1):
        assert event.status.value == "COMPLETED", f"Stage {event.stage} status is {event.status}"
        assert event.durationMs >= 0, f"Stage {event.stage} duration invalid: {event.durationMs}"
        assert event.artifactId != "", f"Stage {event.stage} missing artifact ID"
        print(f"   [OK] Stage {i} [{event.stage}]: artifact={event.artifactId}, duration={event.durationMs}ms")

    # 3. Performance & Durations
    print("\n3. Testing Performance & Duration Calculations:")
    perf = mission1.performance
    assert perf.totalDurationMs >= 0, f"Invalid totalDurationMs: {perf.totalDurationMs}"
    assert perf.averageStageDurationMs >= 0, f"Invalid averageStageDurationMs: {perf.averageStageDurationMs}"
    print(f"   [OK] Total Pipeline Duration: {perf.totalDurationMs}ms")
    print(f"   [OK] Average Stage Duration: {perf.averageStageDurationMs}ms")
    print(f"   [OK] Market Stage Duration: {perf.marketDurationMs}ms")
    print(f"   [OK] Signal Stage Duration: {perf.signalDurationMs}ms")
    print(f"   [OK] Validation Stage Duration: {perf.validationDurationMs}ms")
    print(f"   [OK] Risk Stage Duration: {perf.riskDurationMs}ms")
    print(f"   [OK] Execution Stage Duration: {perf.executionDurationMs}ms")
    print(f"   [OK] Decision Stage Duration: {perf.decisionDurationMs}ms")

    # 4. Pipeline Health & Summary
    print("\n4. Testing Pipeline Health & Summary:")
    health = mission1.health
    assert health.pipelineHealthPercentage == 100.0, f"Expected 100%, got {health.pipelineHealthPercentage}%"
    assert health.enginesHealthy == 6, f"Expected 6 engines, got {health.enginesHealthy}"
    print(f"   [OK] Pipeline Health: {health.pipelineHealthPercentage}% ({health.enginesHealthy}/6 engines healthy)")

    summary = mission1.pipelineSummary
    print(f"   [OK] Summary Counts: Market={summary.marketStateCount}, Candidates={summary.candidateCount}, "
          f"Validations={summary.validationCount}, Risk={summary.riskAssessmentCount}, "
          f"Execution={summary.executionReadinessCount}, Decisions={summary.decisionCount}")

    # 5. Events Emitted
    print("\n5. Testing Timeline Event Bus Output:")
    assert "MissionStageCompleted" in logs, "Missing MissionStageCompleted event"
    assert "MissionCompleted" in logs, "Missing MissionCompleted event"
    assert "mission-001" in logs, "Missing mission-001 in event logs"
    print("   [OK] MissionStageCompleted events emitted successfully")
    print("   [OK] MissionCompleted event emitted successfully")

    # 6. Metadata Integrity
    print("\n6. Testing MissionReport Metadata:")
    assert mission1.artifactType == "MissionReport"
    assert mission1.pipelineStage == "MISSION"
    assert mission1.pipelineVersion == "1.0"
    assert mission1.engineVersion == "1.0.0"
    assert mission1.generatedBy == "Pipeline Orchestrator"
    assert mission1.timelineOrder == 7
    print(f"   [OK] Artifact Type: {mission1.artifactType}")
    print(f"   [OK] Pipeline Stage: {mission1.pipelineStage}")
    print(f"   [OK] Timeline Order: {mission1.timelineOrder}")

    print("\nSUCCESS: ALL VERIFICATION TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    verify_mission()
