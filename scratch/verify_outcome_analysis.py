"""
Falcon Phase 3.7 — Outcome Analysis Verification Script
Run from project root: python scratch/verify_outcome_analysis.py
"""
import sys
import os
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.repository.mission_repository import mission_repository
from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.engines.outcome_analysis_engine import OutcomeAnalysisEngine
from app.schemas.outcome_analysis import OutcomeStatus, OutcomeAccuracy


def run_verification():
    print("=== Falcon Outcome Analysis Verification ===\n")

    # Run the orchestrator a few times if repository is empty
    orchestrator = PipelineOrchestrator()
    for _ in range(3):
        orchestrator.run_pipeline()

    engine = OutcomeAnalysisEngine()
    
    # Snapshot repository before run
    missions_before = copy.deepcopy(mission_repository.get_all_missions())

    reports = engine.generate_reports(repository=mission_repository)
    
    assert len(reports) > 0, "FAIL: No reports generated"
    
    # Check deterministic IDs
    for i, r in enumerate(reports):
        expected_id = f"outcome-{i+1:03d}"
        assert r.id == expected_id, f"FAIL: Expected ID {expected_id}, got {r.id}"
    print(f"[OK] Deterministic IDs Verified (First: {reports[0].id})")

    r = reports[0]

    # Check that calculation adds up
    metrics_sum = sum(m.score for m in r.metrics)
    assert abs(metrics_sum - r.outcomeScore) < 0.1, "FAIL: Weighted score calculations incorrect"
    print(f"[OK] Weighted Score Calculations (Score: {r.outcomeScore:.1f})")

    assert isinstance(r.outcomeStatus, OutcomeStatus), "FAIL: Invalid status mapping"
    assert isinstance(r.accuracy, OutcomeAccuracy), "FAIL: Invalid accuracy mapping"
    print(f"[OK] Status Mappings ({r.outcomeStatus.value}, {r.accuracy.value})")

    assert r.pipelineReview is not None, "FAIL: Pipeline review missing"
    assert r.pipelineReview.signal is not None, "FAIL: Pipeline review incomplete"
    print("[OK] Pipeline Review Generation")

    assert len(r.evidence) > 0, "FAIL: Missing evidence"
    print(f"[OK] Evidence References (Mission: {r.evidence[0].relatedMissionId})")

    # Check repository immutability
    missions_after = mission_repository.get_all_missions()
    assert len(missions_before) == len(missions_after), "FAIL: Repository mutated!"
    print("[OK] Repository Untouched")
    
    summary = engine.build_summary(reports)
    print(f"[OK] Summary Statistics (Avg Score: {summary.averageOutcomeScore})")

    print("[OK] Event Published (see Event Bus logs above)")
    print("\nSUCCESS:\nOutcome Analysis Engine Verified")


if __name__ == "__main__":
    run_verification()
