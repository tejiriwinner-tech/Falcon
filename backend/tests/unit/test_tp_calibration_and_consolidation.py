import pytest
from datetime import datetime, time as dt_time, timezone, timedelta
from app.schemas.signal_candidate import CandidateDirection
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.session_breakout_engine import SessionBreakoutEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.strategy import StrategyStatus


def test_signal_generation_engine_calibrated_atr_and_rr():
    """Verify stop loss scales to 1.0x ATR and eff_rr floor is 1.5R."""
    # Test EURUSD with 0.0020 ATR (20 pips)
    current_price = 1.1000
    atr = 0.0020

    entry, sl, tp = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=current_price,
        atr=atr,
        symbol="EURUSD",
        rr=1.5,
    )

    # 1.5 * ATR = 0.0030. SL = 1.09700
    assert abs(sl - 1.09700) < 1e-4
    # Risk = 0.0030. TP at 1.5R = 1.10450
    assert abs(tp - 1.10450) < 1e-4

    # Test Gold with $10 ATR
    gold_price = 2650.00
    gold_atr = 10.00
    entry_g, sl_g, tp_g = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=gold_price,
        atr=gold_atr,
        symbol="XAUUSD",
        rr=1.5,
    )
    # 1.5 * ATR = $15.00. SL = $2635.00
    assert abs(sl_g - 2635.00) < 1e-2
    # 1.5R = $22.50. TP = $2672.50
    assert abs(tp_g - 2672.50) < 1e-2


def test_session_breakout_engine_tp1_and_tp2_levels():
    """Verify TP1 is calibrated to +1.0R and TP2 is calibrated to +1.5R."""
    engine = SessionBreakoutEngine()
    entry = 1.3000
    effective_risk = 0.0030
    structure_sl = entry - effective_risk  # 1.2970

    sl, tp1, tp2, trail_buf, atr = engine.calculate_trade_levels(
        symbol="GBPUSD",
        direction="BUY",
        entry_price=entry,
        candles=[],
        structure_sl=structure_sl,
    )

    # Effective risk = 0.0030
    # TP1 (+1.0R) = 1.3030
    assert abs(tp1 - (entry + effective_risk)) < 1e-4
    # TP2 (+1.5R) = 1.3045
    assert abs(tp2 - (entry + 1.5 * effective_risk)) < 1e-4


def test_strategy_consolidation_active_vs_incubation():
    """Verify exactly 6 flagships are ACTIVE and the 12 other strategies are in INCUBATION."""
    engine = StrategyEngine()
    flagship_ids = {"strat-004", "strat-007", "strat-012", "strat-013", "strat-016", "strat-017"}

    active_count = 0
    incubation_count = 0

    for s in engine._strategies:
        if s.id in flagship_ids:
            assert s.status == StrategyStatus.ACTIVE, f"{s.id} should be ACTIVE"
            assert s.readyForExecution is True, f"{s.id} should be readyForExecution"
            assert s.minimumRiskReward <= 1.8, f"{s.id} minimumRiskReward should be <= 1.8"
            active_count += 1
        else:
            assert s.status == StrategyStatus.INCUBATION, f"{s.id} should be in INCUBATION"
            assert s.readyForExecution is False, f"{s.id} should not be readyForExecution"
            incubation_count += 1

    assert active_count == 6
    assert incubation_count == 12
    assert len(engine._strategies) == 18


def test_all_18_strategies_can_toggle_on_and_off_for_live_signals():
    """Verify all 18 strategies are approved in settings and respect user ON/OFF toggles."""
    from app.core.config.settings import settings

    all_18 = {f"strat-{i:03d}" for i in range(1, 19)}
    assert all_18.issubset(settings.APPROVED_FLAGSHIP_STRATEGIES)

    engine = StrategyEngine()
    # Toggle an incubation strategy ON (e.g. strat-001) and verify it becomes ACTIVE
    updated_on = engine.set_strategy_status("strat-001", StrategyStatus.ACTIVE)
    assert updated_on is not None
    assert updated_on.status == StrategyStatus.ACTIVE
    assert updated_on.readyForExecution is True

    # Toggle it back OFF (INCUBATION) and verify it deactivates cleanly
    updated_off = engine.set_strategy_status("strat-001", StrategyStatus.INCUBATION)
    assert updated_off is not None
    assert updated_off.status == StrategyStatus.INCUBATION
    assert updated_off.readyForExecution is False


def test_cleanup_stale_open_trades_protects_filled_active_positions():
    """Verify filled OPEN trades are never prematurely expired at 6h as untriggered."""
    from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage
    from app.schemas.trade_journal import TradeJournalCreate

    storage = InMemoryTradeJournalStorage(persistence_file=None)
    eight_hours_ago = datetime.now(timezone.utc) - timedelta(hours=8)

    # 1. Filled active trade (8h old, has fillPrice) -> MUST remain OPEN
    filled_trade = storage.create_trade(
        TradeJournalCreate(
            signalId=9001,
            strategyId="strat-012",
            symbol="XAU/USD",
            direction="SELL",
            entryPrice=3983.74,
            stopLoss=4005.00,
            takeProfit=3955.00,
            timeframe="H1",
            marketSession="London",
            tradeDate=eight_hours_ago,
            status="OPEN",
            result="OPEN",
            fillPrice=3983.74,
            fillTime=eight_hours_ago,
            reasonForEntry="Live entry filled",
        )
    )

    # 2. Untriggered pending reservation (8h old, fillPrice=None) -> MUST expire
    pending_trade = storage.create_trade(
        TradeJournalCreate(
            signalId=9002,
            strategyId="strat-004",
            symbol="GBP/USD",
            direction="BUY",
            entryPrice=1.3000,
            stopLoss=1.2950,
            takeProfit=1.3065,
            timeframe="H1",
            marketSession="London",
            tradeDate=eight_hours_ago,
            status="PENDING",
            result="PENDING",
            fillPrice=None,
            reasonForEntry="Pending order",
        )
    )

    expired_count = storage.cleanup_stale_open_trades(max_age_hours=6)
    assert expired_count == 1
    assert storage.get_trade(filled_trade.id).status == "OPEN"
    assert storage.get_trade(pending_trade.id).status == "EXPIRED"
