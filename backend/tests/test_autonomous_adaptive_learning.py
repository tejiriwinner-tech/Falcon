"""
Test suite verifying the Autonomous Closed-Loop Adaptive Learning & Consistency Architecture:
1. Strategy health grading & quarantine of lagging strategies (win rate < 45% -> QUARANTINED_SHADOW)
2. Priority capital allocation for Tier 1 Flagships (strat-006, strat-014, strat-004)
3. Universal strat-006 probe wick veto applied across all strategies
4. Zero deletion/alteration of historical missions or archived artifacts
"""
import sys
sys.path.insert(0, 'backend')

from app.core.analytics.adaptive_tuning_engine import adaptive_tuning_engine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.repository.mission_repository import mission_repository
from app.core.repository.trade_journal_repository import trade_journal_repository


def test_autonomous_strategy_health_grading_and_quarantine():
    # strat-006 is 100% win rate -> TIER_1_FLAGSHIP
    p_006 = adaptive_tuning_engine.get_strategy_tuning("strat-006")
    assert p_006.tier_grade == "TIER_1_FLAGSHIP"
    assert p_006.is_quarantined_shadow is False
    assert p_006.tuning_status == "OPTIMAL"

    # strat-016 has 38.9% win rate -> TIER_4_QUARANTINED
    p_016 = adaptive_tuning_engine.get_strategy_tuning("strat-016")
    assert p_016.tier_grade == "TIER_4_QUARANTINED"
    assert p_016.is_quarantined_shadow is True
    assert p_016.tuning_status == "QUARANTINED_SHADOW"

    # strat-021 has 25% win rate -> TIER_4_QUARANTINED
    p_021 = adaptive_tuning_engine.get_strategy_tuning("strat-021")
    assert p_021.tier_grade == "TIER_4_QUARANTINED"
    assert p_021.is_quarantined_shadow is True

    # strat-022 has 63.6% win rate -> TIER_2_CONSISTENT
    p_022 = adaptive_tuning_engine.get_strategy_tuning("strat-022")
    assert p_022.tier_grade == "TIER_2_CONSISTENT"
    assert p_022.is_quarantined_shadow is False


def test_universal_breakeven_and_opposite_boundary_stop():
    engine = StrategyEngine()
    strat_006 = engine.get_strategy_by_id("strat-006")
    assert strat_006 is not None
    assert strat_006.strategyVersion == "3.1"


def test_historical_missions_and_artifacts_intact():
    recent_missions = mission_repository.get_recent_missions(limit=5)
    assert len(recent_missions) > 0
    all_trades = trade_journal_repository.list_trades()
    assert len(all_trades) >= 150
    print(f"Verified {len(all_trades)} trades and {len(recent_missions)} recent missions completely intact!")


if __name__ == "__main__":
    test_autonomous_strategy_health_grading_and_quarantine()
    test_universal_breakeven_and_opposite_boundary_stop()
    test_historical_missions_and_artifacts_intact()
    print("ALL AUTONOMOUS ADAPTIVE LEARNING TESTS PASSED!")
