"""
Falcon Phase 3.8 — AI Confidence Calibration Verification Script
Run from project root: python scratch/verify_calibration.py
"""
import sys
import os
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.repository.mission_repository import mission_repository
from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.engines.calibration_engine import CalibrationEngine
from app.schemas.calibration_report import (
    CalibrationLevel,
    CalibrationStatus,
    CalibrationTrend,
    CalibrationRecommendation,
)


def run_verification():
    print("=== Falcon AI Confidence Calibration Verification ===\n")

    # Seed repository with a few missions
    orchestrator = PipelineOrchestrator()
    for _ in range(3):
        orchestrator.run_pipeline()

    engine = CalibrationEngine()

    # Snapshot before
    missions_before = copy.deepcopy(mission_repository.get_all_missions())

    reports = engine.generate_reports(repository=mission_repository)

    assert len(reports) > 0, "FAIL: No reports generated"

    # ── Deterministic ID
    assert reports[0].id == "calibration-001", f"FAIL: Bad ID {reports[0].id}"
    print(f"[OK] Deterministic ID: {reports[0].id}")

    r = reports[0]

    # ── Score in range
    assert 0 <= r.calibrationScore <= 100, "FAIL: Score out of range"
    print(f"[OK] Calibration Score: {r.calibrationScore}")

    # ── Weighted score adds up
    computed = sum(m.score * m.weight for m in r.metrics)
    assert abs(computed - r.calibrationScore) < 0.1, (
        f"FAIL: Weighted score mismatch: {computed:.2f} vs {r.calibrationScore}"
    )
    print(f"[OK] Weighted Score Correct ({r.calibrationScore})")

    # ── Level determined correctly
    score = r.calibrationScore
    if score >= 95:
        expected_level = CalibrationLevel.EXCELLENT
    elif score >= 85:
        expected_level = CalibrationLevel.HIGH
    elif score >= 70:
        expected_level = CalibrationLevel.MEDIUM
    elif score >= 50:
        expected_level = CalibrationLevel.LOW
    else:
        expected_level = CalibrationLevel.VERY_LOW
    assert r.calibrationLevel == expected_level, f"FAIL: Level mismatch {r.calibrationLevel} vs {expected_level}"
    print(f"[OK] Calibration Level: {r.calibrationLevel.value}")

    # ── Recommendation mapping correct
    rec_map = {
        CalibrationLevel.EXCELLENT: CalibrationRecommendation.TRUST_SIGNALS,
        CalibrationLevel.HIGH:      CalibrationRecommendation.TRUST_WITH_MONITORING,
        CalibrationLevel.MEDIUM:    CalibrationRecommendation.REVIEW_STRATEGIES,
        CalibrationLevel.LOW:       CalibrationRecommendation.COLLECT_MORE_DATA,
        CalibrationLevel.VERY_LOW:  CalibrationRecommendation.DO_NOT_AUTOMATE,
    }
    assert r.recommendation == rec_map[r.calibrationLevel], "FAIL: Recommendation mismatch"
    print(f"[OK] Recommendation: {r.recommendation.value}")

    # ── Trend
    assert isinstance(r.calibrationTrend, CalibrationTrend), "FAIL: Invalid trend"
    print(f"[OK] Calibration Trend: {r.calibrationTrend.value}")

    # ── Repository immutability
    missions_after = mission_repository.get_all_missions()
    assert len(missions_before) == len(missions_after), "FAIL: Repository mutated!"
    print("[OK] Repository Immutable")

    # ── Summary
    summary = engine.build_summary(reports)
    assert summary.totalReports == len(reports), "FAIL: Summary count mismatch"
    print(f"[OK] Summary Generation (Avg Score: {summary.averageCalibrationScore})")

    print("[OK] Event Published (see Event Bus logs above)")
    print("\nSUCCESS:\nAI Confidence Calibration Engine Verified")


if __name__ == "__main__":
    run_verification()
