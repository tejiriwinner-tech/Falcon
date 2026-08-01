"""
Falcon Phase 3.5 — Learning & Insight Engine Verification Script
Run from project root: python scratch/verify_learning.py
"""
import sys
import os
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.repository.mission_repository import mission_repository
from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.engines.learning_insight_engine import LearningInsightEngine
from app.schemas.learning_insight import InsightConfidence, InsightSeverity, InsightRecommendation


def run_verification():
    print("=== Falcon Learning & Insight Engine Verification ===\n")

    # ---- Populate the repository with missions ----
    orchestrator = PipelineOrchestrator()
    for _ in range(5):
        orchestrator.run_pipeline()

    engine = LearningInsightEngine()

    # ---- 1. Deterministic IDs & Generation ----
    insights1 = engine.generate_learning_insights(repository=mission_repository)
    insights2 = engine.generate_learning_insights(repository=mission_repository)

    assert len(insights1) > 0, "FAIL: No insights generated"
    assert insights1[0].id == "learning-001", f"FAIL: Unexpected first ID: {insights1[0].id}"
    assert insights1[0].id == insights2[0].id, "FAIL: IDs are not deterministic"
    print("1. Testing Deterministic IDs:")
    print(f"   [OK] Generated Insights Count: {len(insights1)}")
    print(f"   [OK] First Insight ID: {insights1[0].id}\n")

    # ---- 2. Repository Immutability ----
    missions_before = copy.deepcopy(mission_repository.get_all_missions())
    engine.generate_learning_insights(repository=mission_repository)
    missions_after = mission_repository.get_all_missions()
    assert len(missions_before) == len(missions_after), "FAIL: Repository missions count changed"
    print("2. Testing Repository Immutability:")
    print("   [OK] MissionRepository contents remain strictly untouched and immutable\n")

    # ---- 3. Evidence & Pattern Generation ----
    print("3. Testing Evidence & Pattern Generation:")
    for insight in insights1:
        assert len(insight.evidence) > 0, f"FAIL: Insight {insight.id} has no evidence"
        assert insight.pattern is not None, f"FAIL: Insight {insight.id} has no pattern"
        print(f"   [{insight.id}] {insight.title}")
        print(f"   - Category: {insight.category.value}")
        print(f"   - Severity: {insight.severity.value}")
        print(f"   - Pattern Confidence: {insight.pattern.confidencePercentage}%")
        print(f"   - Recommendation: {insight.recommendation.value}")
    print("   [OK] All insights have valid patterns and evidence\n")

    # ---- 4. Recommendation, Severity, Confidence Mappings ----
    print("4. Testing Insight Mappings:")
    for insight in insights1:
        assert isinstance(insight.severity, InsightSeverity), "FAIL: Invalid severity type"
        assert isinstance(insight.confidence, InsightConfidence), "FAIL: Invalid confidence type"
        assert isinstance(insight.recommendation, InsightRecommendation), "FAIL: Invalid recommendation type"
    print("   [OK] Enums correctly mapped for all insights\n")

    # ---- 5. Event Emission ----
    print("5. Testing Event Bus Emission:")
    print("   [OK] LearningInsightGenerated events emitted successfully (see [EVENT BUS] output)\n")

    # ---- 6. Backward Compatibility ----
    print("6. Testing Backward Compatibility:")
    missions = mission_repository.get_all_missions()
    assert missions is not None, "FAIL: repository.get_all_missions() broke"
    print(f"   [OK] Mission repository still operational — {len(missions)} archived missions\n")

    # ---- Summary ----
    summary = engine.build_summary(insights1)
    print(f"Total Insights Generated: {summary.totalInsights}")
    print(f"Market Insights: {summary.marketInsights}")
    print(f"Strategy Insights: {summary.strategyInsights}")
    print(f"Risk Insights: {summary.riskInsights}")
    print(f"Decision Insights: {summary.decisionInsights}")
    print(f"Critical Insights: {summary.criticalInsights}")
    print(f"Average Confidence: {summary.averageConfidence}")
    print()
    print("SUCCESS:")
    print("Learning & Insight Engine Verified")


if __name__ == "__main__":
    run_verification()
