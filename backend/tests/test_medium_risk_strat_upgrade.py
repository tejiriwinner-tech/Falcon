"""
Verification test suite for Medium-Risk Normalization & strat-006 Zero-Loss Discipline Upgrade:
1. strat-004, strat-017, strat-019, strat-020, strat-021, strat-022, strat-023 are RiskLevel.MEDIUM with maxConsecutiveLosses == 2
2. strat-017 (AUD/USD) has minimumConfidence == 85 and OrderFlowEngine v3.0 dependency
3. strat-006 (EUR/USD v3.1) and strat-024 (XAU/USD Velocity Scalp v3.2) remain 100% untouched
"""
import sys
sys.path.insert(0, "backend")

from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.strategy import RiskLevel, StrategyCategory


def test_medium_risk_normalization_and_isolation():
    engine = StrategyEngine()
    target_ids = ["strat-004", "strat-017", "strat-019", "strat-020", "strat-021", "strat-022", "strat-023"]
    for sid in target_ids:
        st = engine.get_strategy_by_id(sid)
        assert st is not None, f"{sid} missing"
        assert st.riskLevel == RiskLevel.MEDIUM, f"{sid} expected MEDIUM, got {st.riskLevel}"
        assert st.maxConsecutiveLosses == 2, f"{sid} expected maxConsecutiveLosses=2, got {st.maxConsecutiveLosses}"

    # Verify strat-017 enhanced configuration
    s17 = engine.get_strategy_by_id("strat-017")
    assert s17.symbol == "AUD/USD"
    assert s17.minimumConfidence == 85
    assert "OrderFlowEngine v3.0" in s17.dependencies
    assert "RVol >= 1.8x & Body >= 45%" in s17.successConditions

    # Verify strat-006 (EUR/USD) and strat-024 (XAU/USD) 100% untouched
    s06 = engine.get_strategy_by_id("strat-006")
    assert s06 is not None
    assert s06.symbol == "EUR/USD"
    assert s06.strategyVersion == "3.1"
    assert s06.riskLevel == RiskLevel.MEDIUM

    s24 = engine.get_strategy_by_id("strat-024")
    assert s24 is not None
    assert s24.symbol == "XAU/USD"
    assert s24.category == StrategyCategory.SCALPING
    assert s24.minimumRiskReward == 1.2
    assert s24.riskLevel == RiskLevel.MEDIUM

    print("ALL MEDIUM-RISK & ISOLATION TESTS PASSED!")


if __name__ == "__main__":
    test_medium_risk_normalization_and_isolation()
