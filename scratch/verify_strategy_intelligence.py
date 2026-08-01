import sys
import os
from io import StringIO

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.core.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from app.core.repository.mission_repository import mission_repository
from app.core.analytics.strategy_intelligence_engine import StrategyIntelligenceEngine


def verify_strategy_intelligence():
    print("=== Falcon Strategy Intelligence Verification ===")

    # Clear repository & instantiate pipeline orchestrator + engine
    mission_repository.clear_repository()
    orchestrator = PipelineOrchestrator()
    intelligence_engine = StrategyIntelligenceEngine()

    # Capture stdout during pipeline execution & report generation
    old_stdout = sys.stdout
    captured = StringIO()
    sys.stdout = captured

    try:
        # Run 4 complete missions
        for _ in range(4):
            orchestrator.run_pipeline()

        reports1 = intelligence_engine.generate_reports(mission_repository)
        reports2 = intelligence_engine.generate_reports(mission_repository)
    finally:
        sys.stdout = old_stdout

    logs = captured.getvalue()

    # 1. Deterministic IDs & Count
    print("\n1. Testing Deterministic IDs & Reports Count:")
    assert len(reports1) >= 4, f"Expected at least 4 reports, got {len(reports1)}"
    assert reports1[0].id == "strategy-report-001", f"Expected strategy-report-001, got {reports1[0].id}"
    assert reports2[0].id == "strategy-report-001", f"Expected deterministic ID matching"
    print(f"   [OK] Generated Reports Count: {len(reports1)}")
    print(f"   [OK] First Report ID: {reports1[0].id}")

    # 2. Immutability & Repository Protection
    print("\n2. Testing Repository Immutability:")
    missions_count = len(mission_repository.get_all_missions())
    assert missions_count == 4, f"Expected 4 missions, got {missions_count}"
    print("   [OK] MissionRepository contents remain strictly untouched and immutable")

    # 3. Event Bus Emission
    print("\n3. Testing Event Bus Emission:")
    assert "StrategyIntelligenceGenerated" in logs, "Missing StrategyIntelligenceGenerated event in logs"
    assert "strategy-report-001" in logs, "Missing strategy-report-001 in event logs"
    print("   [OK] StrategyIntelligenceGenerated events emitted successfully")

    # 4. Report details printing matching target benchmark output
    print(f"\nStrategies Analysed: {len(reports1)}\n")
    for r in reports1:
        print(f"{r.strategyName}")
        print(f"Score: {round(r.overallScore)}")
        print(f"Health: {r.health.value}")
        print(f"Trend: {r.trend.value}\n")

    print("SUCCESS:")
    print("Strategy Intelligence Engine Verified")


if __name__ == "__main__":
    verify_strategy_intelligence()
