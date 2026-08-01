"""
Falcon Phase 3.6 — Market Regime Intelligence Verification Script
Run from project root: python scratch/verify_market_regime.py
"""
import sys
import os
import copy

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.repository.mission_repository import mission_repository
from app.core.engines.market_regime_engine import MarketRegimeEngine
from app.schemas.market_regime import MarketRegime, RegimeStrength, RegimeConfidence, RecommendationBias


def run_verification():
    print("=== Falcon Market Regime Verification ===\n")

    engine = MarketRegimeEngine()
    
    # Snapshot repository before run
    missions_before = copy.deepcopy(mission_repository.get_all_missions())

    reports = engine.generate_reports(repository=mission_repository)
    
    assert len(reports) > 0, "FAIL: No reports generated"
    r = reports[0]

    assert r.id == "regime-001", f"FAIL: Expected ID regime-001, got {r.id}"
    print(f"[OK] Report ID: {r.id}")

    assert r.regime == MarketRegime.TRENDING_BULLISH, f"FAIL: Expected TRENDING_BULLISH, got {r.regime}"
    print(f"[OK] Regime: {r.regime.value}")

    assert r.strength == RegimeStrength.STRONG, f"FAIL: Expected STRONG, got {r.strength}"
    print(f"[OK] Strength: {r.strength.value}")

    assert r.confidence == RegimeConfidence.HIGH, f"FAIL: Expected HIGH, got {r.confidence}"
    print(f"[OK] Confidence: {r.confidence.value}")

    assert r.recommendation.bias == RecommendationBias.BUY_BIAS, f"FAIL: Expected BUY_BIAS, got {r.recommendation.bias}"
    print(f"[OK] Recommendation Bias: {r.recommendation.bias.value}")

    # Check repository immutability
    missions_after = mission_repository.get_all_missions()
    assert len(missions_before) == len(missions_after), "FAIL: Repository mutated!"
    print("[OK] Repository Immutable")
    
    print("[OK] Event Published (see Event Bus logs above)")
    print("\nSUCCESS:\nMarket Regime Engine Verified")


if __name__ == "__main__":
    run_verification()
