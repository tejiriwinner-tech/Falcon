import sys
import os
from datetime import datetime, timezone
import json

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.engines.market_state_engine import MarketStateEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.validation_engine import ValidationEngine
from app.core.engines.risk_engine import RiskEngine
from app.core.engines.execution_readiness_engine import ExecutionReadinessEngine
from app.core.engines.decision_engine import DecisionEngine

from app.schemas.decision_artifact import (
    DecisionRecommendation,
    DecisionStatus
)
from app.schemas.execution_readiness import ExecutionReadinessStatus
from app.schemas.risk_assessment import RiskLevel
from app.schemas.validation_result import ValidationStatus

def verify_decision_pipeline():
    print("=== Falcon Decision Engine Verification ===")

    market_state_engine = MarketStateEngine()
    strategy_engine = StrategyEngine()
    signal_gen_engine = SignalGenerationEngine()
    val_engine = ValidationEngine()
    risk_engine = RiskEngine()
    execution_engine = ExecutionReadinessEngine()
    decision_engine = DecisionEngine()

    # Flow 1: Optimal Standard Pipeline Execution
    print("\n--- Test Case 1: Standard Optimal 5-Stage Execution ---")
    market_state = market_state_engine.get_market_state()
    strategies = strategy_engine.get_strategies()
    candidates = signal_gen_engine.generate_candidates(market_state, strategies)
    validations = val_engine.validate_candidates(candidates, strategies, market_state)
    assessments = risk_engine.assess_all(validations, candidates, strategies, market_state)
    readiness_items = execution_engine.evaluate_execution_readiness(
        assessments, validations, candidates, strategies, market_state
    )

    # Clone initial state of upstream items for immutability check
    initial_readiness_json = json.dumps([r.model_dump(mode='json') for r in readiness_items])

    decisions = decision_engine.generate_decisions(
        readiness_items, assessments, validations, candidates, strategies, market_state
    )

    # Immutability Check
    post_readiness_json = json.dumps([r.model_dump(mode='json') for r in readiness_items])
    assert initial_readiness_json == post_readiness_json, "Upstream ExecutionReadiness artifacts were modified!"
    print("Upstream Immutability Check: PASSED")

    assert len(decisions) > 0, "No decision artifacts generated!"
    d1 = decisions[0]

    print(f"Decision ID: {d1.id} (Expected: decision-001)")
    assert d1.id == "decision-001"

    print(f"Recommendation: {d1.recommendation.value} (Expected: WAIT, BUY, or SELL)")
    assert d1.recommendation in [DecisionRecommendation.WAIT, DecisionRecommendation.BUY, DecisionRecommendation.SELL]

    print(f"Status: {d1.status.value} (Expected: PENDING or APPROVED)")
    assert d1.status in [DecisionStatus.PENDING, DecisionStatus.APPROVED]

    print(f"Decision Confidence: {d1.decisionConfidence}% (Bounds: 0 to 100)")
    assert 0.0 <= d1.decisionConfidence <= 100.0

    print(f"Timeline Order: {d1.timelineOrder} (Expected: 6)")
    assert d1.timelineOrder == 6

    print(f"Market State ID: {d1.marketStateId} (Frozen link verified)")
    assert d1.marketStateId.startswith("market-")

    # Verify Trace Length
    print(f"Decision Trace Stages: {[t.stage for t in d1.decisionTrace]}")
    assert len(d1.decisionTrace) == 5
    assert d1.decisionTrace[0].stage == "SIGNAL"
    assert d1.decisionTrace[4].stage == "DECISION"

    # Verify Mission Verdict
    print(f"Mission Verdict: {d1.missionVerdict.model_dump_json()}")
    assert d1.missionVerdict.decisionVerdict == d1.recommendation

    # Verify Captain's Recommendation Details
    print(f"Captain's Title: {d1.recommendationDetails.title}")
    print(f"Captain's Priority: {d1.recommendationDetails.priority.value}")
    print(f"Expected Holding: {d1.recommendationDetails.expectedHolding}")

    # Flow 1b: Explicit READY -> BUY / SELL check
    print("\n--- Test Case 1b: Execution READY -> Decision BUY / SELL ---")
    readiness_ready = readiness_items[0].model_copy(deep=True)
    readiness_ready.status = ExecutionReadinessStatus.READY
    decisions_ready = decision_engine.generate_decisions(
        [readiness_ready], assessments, validations, candidates, strategies, market_state
    )
    d_ready = decisions_ready[0]
    print(f"Recommendation for Execution READY: {d_ready.recommendation.value} (Expected: BUY or SELL)")
    print(f"Status for Execution READY: {d_ready.status.value} (Expected: APPROVED)")
    assert d_ready.recommendation in [DecisionRecommendation.BUY, DecisionRecommendation.SELL]
    assert d_ready.status == DecisionStatus.APPROVED

    # Flow 2: Test Case for WAIT recommendation
    print("\n--- Test Case 2: Execution Readiness WAIT -> Decision WAIT ---")
    readiness_wait = readiness_items[0].model_copy(deep=True)
    readiness_wait.status = ExecutionReadinessStatus.WAIT
    readiness_wait.recommendation.nextReviewIn = "At London Open"

    decisions_wait = decision_engine.generate_decisions(
        [readiness_wait], assessments, validations, candidates, strategies, market_state
    )
    d_wait = decisions_wait[0]
    print(f"Status for Execution WAIT: {d_wait.status.value} (Expected: PENDING)")
    print(f"Recommendation: {d_wait.recommendation.value} (Expected: WAIT)")
    print(f"Next Review: {d_wait.recommendationDetails.nextReviewIn} (Expected: At London Open)")
    assert d_wait.recommendation == DecisionRecommendation.WAIT
    assert d_wait.status == DecisionStatus.PENDING
    assert d_wait.recommendationDetails.nextReviewIn == "At London Open"

    # Flow 3: Test Case for NO_TRADE recommendation (Execution BLOCKED)
    print("\n--- Test Case 3: Execution BLOCKED -> Decision NO_TRADE ---")
    readiness_blocked = readiness_items[0].model_copy(deep=True)
    readiness_blocked.status = ExecutionReadinessStatus.BLOCKED
    readiness_blocked.recommendation.nextReviewIn = "When market opens"

    decisions_blocked = decision_engine.generate_decisions(
        [readiness_blocked], assessments, validations, candidates, strategies, market_state
    )
    d_blocked = decisions_blocked[0]
    print(f"Status for Execution BLOCKED: {d_blocked.status.value} (Expected: REJECTED)")
    print(f"Recommendation: {d_blocked.recommendation.value} (Expected: NO_TRADE)")
    assert d_blocked.recommendation == DecisionRecommendation.NO_TRADE
    assert d_blocked.status == DecisionStatus.REJECTED

    # Flow 4: Test Case for Risk Confidence Calculation
    print("\n--- Test Case 4: Risk Confidence Calculation Verification ---")
    # 40% Signal (100) + 25% Validation (100) + 20% RiskConf (100-20=80) + 15% Readiness (100)
    # = 40 + 25 + 16 + 15 = 96.0
    cand_perfect = candidates[0].model_copy(deep=True)
    cand_perfect.confidence = 100.0

    val_perfect = validations[0].model_copy(deep=True)
    val_perfect.validationScore = 100.0

    risk_safe = assessments[0].model_copy(deep=True)
    risk_safe.overallRiskScore = 20.0  # Risk confidence = 80.0

    exec_perfect = readiness_items[0].model_copy(deep=True)
    exec_perfect.overallReadinessScore = 100

    decisions_conf = decision_engine.generate_decisions(
        [exec_perfect], [risk_safe], [val_perfect], [cand_perfect], strategies, market_state
    )
    expected_conf = round(0.40 * 100.0 + 0.25 * 100.0 + 0.20 * 80.0 + 0.15 * 100.0, 1) # 96.0
    print(f"Calculated Confidence: {decisions_conf[0].decisionConfidence}% (Expected: {expected_conf}%)")
    assert decisions_conf[0].decisionConfidence == expected_conf

    print("\nDecision Engine Verification Passed Successfully!")

if __name__ == "__main__":
    verify_decision_pipeline()
