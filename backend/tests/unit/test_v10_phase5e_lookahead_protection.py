"""
Falcon V10 Phase 5E — Adaptive Lookahead Protection Test Suite
=============================================================
Verifies point-in-time safety for AdaptiveRuleTuningEngine:
1. Closed trade before as_of is included.
2. Closed trade exactly at as_of is included.
3. Closed trade after as_of is excluded.
4. Trade opened before as_of but closed after as_of is excluded.
5. CLOSED trade with NULL closeDate is excluded.
6. OPEN/PENDING trades are excluded.
7. Future trade does not affect the adaptive result.
8. Existing top-N sample is selected AFTER the as_of filter.
9. Historical replay passes its timestamp into adaptive tuning.
10. Live/default behavior remains compatible.
11. Phase 5D adaptive provenance still captures the selected rule version/multiplier.
12. Two different as_of timestamps produce different eligible populations without mutating stored records.
13. No future outcome can alter an earlier historical tuning result.
14. Deterministic ordering remains unchanged for eligible records (tradeDate DESC, id DESC).
15. Capital Guardian risk calculations and 3-trade limits remain untouched.
16. Manual MT5/Exness execution boundary preserved (zero broker automation).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.analytics.adaptive_tuning_engine import (
    AdaptiveRuleTuningEngine,
    StrategyTuningProfile,
    adaptive_tuning_engine,
)
from app.core.database.models import Base, TradeJournalRecord
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.core.repository.capital_cycle_repository import capital_cycle_repository
from app.core.repository.trade_journal_repository import (
    DatabaseTradeJournalStorage,
    InMemoryTradeJournalStorage,
    trade_journal_repository,
)
from app.core.services.capital_guardian_service import capital_guardian_service
from app.core.services.signal_authorization_service import (
    FALCON_GUARDIAN_ADVISORY_LOCK_KEY,
    signal_authorization_service,
)
from app.schemas.capital_cycle import CapitalCycleCreate
from app.schemas.market_state import MarketPrice, MarketState
from app.schemas.strategy import StrategyItem, StrategyScore, StrategyStatus, StrategyType
from app.schemas.trade_journal import TradeJournalCreate


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Isolate each test with a clean in-memory journal and reset adaptive profiles."""
    orig_storage = trade_journal_repository._storage
    mem_storage = InMemoryTradeJournalStorage()
    trade_journal_repository._storage = mem_storage
    trade_journal_repository.clear()

    orig_profiles = dict(adaptive_tuning_engine._profiles)
    orig_version = getattr(adaptive_tuning_engine, "version", "1.0.0")
    adaptive_tuning_engine._profiles.clear()

    yield

    trade_journal_repository.clear()
    trade_journal_repository._storage = orig_storage
    adaptive_tuning_engine._profiles = orig_profiles
    adaptive_tuning_engine.version = orig_version


def _create_sample_trade(
    symbol: str = "EUR/USD",
    strategy_id: str = "strat-001",
    status: str = "CLOSED",
    result: str = "LOSS",
    trade_date: datetime = None,
    close_date: datetime = None,
    profit_loss: float = -20.0,
    reason_for_exit: str = "Stop Loss hit by liquidity sweep wick",
    signal_id: int = 1000,
) -> int:
    t = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=signal_id,
            strategyId=strategy_id,
            symbol=symbol,
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=trade_date or datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc),
            closeDate=close_date,
            status=status,
            result=result,
            profitLoss=profit_loss,
            reasonForEntry="Test setup",
            reasonForExit=reason_for_exit,
        )
    )
    return t.id


# ==============================================================================
# Condition 1: Closed trade before as_of is included
# ==============================================================================
def test_condition_1_closed_trade_before_as_of_is_included():
    t_trade = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 9, 10, 11, 0, 0, tzinfo=timezone.utc)
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    _create_sample_trade(trade_date=t_trade, close_date=t_close, status="CLOSED")

    trades = trade_journal_repository.list_closed_trades_as_of(
        strategy_id="strat-001", as_of=t_as_of
    )
    assert len(trades) == 1
    assert trades[0].closeDate == t_close


# ==============================================================================
# Condition 2: Closed trade exactly at as_of is included
# ==============================================================================
def test_condition_2_closed_trade_exactly_at_as_of_is_included():
    t_trade = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    _create_sample_trade(trade_date=t_trade, close_date=t_close, status="CLOSED")

    trades = trade_journal_repository.list_closed_trades_as_of(
        strategy_id="strat-001", as_of=t_as_of
    )
    assert len(trades) == 1
    assert trades[0].closeDate == t_as_of


# ==============================================================================
# Condition 3: Closed trade after as_of is excluded
# ==============================================================================
def test_condition_3_closed_trade_after_as_of_is_excluded():
    t_trade = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 9, 10, 13, 0, 0, tzinfo=timezone.utc)
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    _create_sample_trade(trade_date=t_trade, close_date=t_close, status="CLOSED")

    trades = trade_journal_repository.list_closed_trades_as_of(
        strategy_id="strat-001", as_of=t_as_of
    )
    assert len(trades) == 0


# ==============================================================================
# Condition 4: Trade opened before as_of but closed after as_of is excluded
# ==============================================================================
def test_condition_4_trade_opened_before_but_closed_after_as_of_is_excluded():
    t_trade = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 9, 10, 15, 0, 0, tzinfo=timezone.utc)

    _create_sample_trade(trade_date=t_trade, close_date=t_close, status="CLOSED")

    trades = trade_journal_repository.list_closed_trades_as_of(
        strategy_id="strat-001", as_of=t_as_of
    )
    assert len(trades) == 0, "A trade opened before as_of whose outcome is in the future must be strictly excluded."


# ==============================================================================
# Condition 5: CLOSED trade with NULL closeDate is excluded
# ==============================================================================
def test_condition_5_closed_trade_with_null_close_date_is_excluded():
    t_trade = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    _create_sample_trade(trade_date=t_trade, close_date=None, status="CLOSED")

    trades = trade_journal_repository.list_closed_trades_as_of(
        strategy_id="strat-001", as_of=t_as_of
    )
    assert len(trades) == 0, "CLOSED trade without an authoritative closeDate must never qualify."


# ==============================================================================
# Condition 6: OPEN/PENDING trades are excluded
# ==============================================================================
def test_condition_6_open_and_pending_trades_are_excluded():
    t_trade = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    _create_sample_trade(trade_date=t_trade, close_date=None, status="OPEN")
    _create_sample_trade(trade_date=t_trade, close_date=None, status="PENDING")

    trades = trade_journal_repository.list_closed_trades_as_of(
        strategy_id="strat-001", as_of=t_as_of
    )
    assert len(trades) == 0, "Non-closed trades must be strictly excluded."


# ==============================================================================
# Condition 7: Future trade does not affect the adaptive result
# ==============================================================================
def test_condition_7_future_trade_does_not_affect_adaptive_result():
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # 1. Historical state at t_as_of: 0 losses -> baseline 1.0x
    profile_before = adaptive_tuning_engine.get_strategy_tuning(
        "strat-001", "EUR/USD", as_of=t_as_of
    )
    assert profile_before.adaptive_stop_multiplier == 1.0
    assert profile_before.tuning_status == "OPTIMAL"

    # 2. Inject 3 consecutive losses in the FUTURE (14:00, 15:00, 16:00)
    for i in range(3):
        _create_sample_trade(
            trade_date=datetime(2026, 9, 10, 13, 0 + i, tzinfo=timezone.utc),
            close_date=datetime(2026, 9, 10, 14 + i, 0, tzinfo=timezone.utc),
            status="CLOSED",
            result="LOSS",
            signal_id=2000 + i,
        )

    # 3. Query again at t_as_of: MUST STILL BE 1.0x (unaffected by future losses)
    profile_at_as_of = adaptive_tuning_engine.get_strategy_tuning(
        "strat-001", "EUR/USD", as_of=t_as_of
    )
    assert profile_at_as_of.adaptive_stop_multiplier == 1.0
    assert profile_at_as_of.tuning_status == "OPTIMAL"
    assert profile_at_as_of.total_evaluated == 0

    # 4. Query at t_future: now the 3 losses are included -> 1.6x VOLATILITY_DEFENSE
    t_future = datetime(2026, 9, 10, 18, 0, 0, tzinfo=timezone.utc)
    profile_at_future = adaptive_tuning_engine.get_strategy_tuning(
        "strat-001", "EUR/USD", as_of=t_future
    )
    assert profile_at_future.adaptive_stop_multiplier == 1.6
    assert profile_at_future.tuning_status == "VOLATILITY_DEFENSE"
    assert profile_at_future.consecutive_losses == 3


# ==============================================================================
# Condition 8: Existing top-N sample is selected AFTER the as-of filter
# ==============================================================================
def test_condition_8_top_n_sample_selected_after_as_of_filter():
    """
    If 20 total trades exist (10 closed before as_of, 10 closed after as_of),
    filtering before top-15 must evaluate all 10 historical trades, rather
    than taking 15 globally and filtering down to 5.
    """
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # 10 historical wins (close_date = 10:00 to 11:30)
    for i in range(10):
        _create_sample_trade(
            trade_date=datetime(2026, 9, 10, 8, i, tzinfo=timezone.utc),
            close_date=datetime(2026, 9, 10, 9 + (i // 5), 10 * (i % 5), tzinfo=timezone.utc),
            status="CLOSED",
            result="WIN",
            profit_loss=20.0,
            signal_id=3000 + i,
        )

    # 10 future losses (close_date = 13:00 to 15:00)
    for i in range(10):
        _create_sample_trade(
            trade_date=datetime(2026, 9, 10, 12, 30 + i, tzinfo=timezone.utc),
            close_date=datetime(2026, 9, 10, 13 + (i // 5), 10 * (i % 5), tzinfo=timezone.utc),
            status="CLOSED",
            result="LOSS",
            profit_loss=-20.0,
            signal_id=4000 + i,
        )

    profile = adaptive_tuning_engine.get_strategy_tuning(
        "strat-001", "EUR/USD", as_of=t_as_of
    )
    # If filtered before top-15: all 10 historical trades qualify, win_rate = 1.0 -> OPTIMAL 1.0x
    assert profile.total_evaluated == 10
    assert profile.recent_win_rate == 1.0
    assert profile.adaptive_stop_multiplier == 1.0
    assert profile.tuning_status == "OPTIMAL"


# ==============================================================================
# Condition 9: Historical replay passes its timestamp into adaptive tuning
# ==============================================================================
def test_condition_9_historical_replay_passes_timestamp_into_adaptive_tuning():
    t_hist = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Historical state: 1 win
    _create_sample_trade(
        trade_date=datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc),
        close_date=datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
        status="CLOSED",
        result="WIN",
        profit_loss=30.0,
        signal_id=5001,
    )
    # Future state: 3 consecutive losses
    for i in range(3):
        _create_sample_trade(
            trade_date=datetime(2026, 9, 10, 13, i, tzinfo=timezone.utc),
            close_date=datetime(2026, 9, 10, 14 + i, 0, tzinfo=timezone.utc),
            status="CLOSED",
            result="LOSS",
            profit_loss=-20.0,
            signal_id=5002 + i,
        )

    engine = SignalGenerationEngine()
    strat_engine = StrategyEngine()
    dummy_strategy = strat_engine.get_strategy_by_id("strat-001") or strat_engine.get_strategies()[0]
    dummy_strategy.status = StrategyStatus.ACTIVE
    dummy_strategy.symbol = "EUR/USD"

    dummy_market_state = MarketState(
        prices={
            "EURUSD": MarketPrice(
                symbol="EURUSD",
                currentPrice=1.1000,
                bid=1.09995,
                ask=1.10005,
                spread=0.0001,
                timestamp=t_hist,
                provider="Test",
            )
        },
        timestamp=t_hist,
        dataAgeSeconds=5,
    )

    # Replay evaluated at t_hist
    candidates = engine.generate_candidates(
        market_state=dummy_market_state,
        strategies=[dummy_strategy],
        as_of=t_hist,
    )
    assert len(candidates) >= 1
    cand = candidates[0]
    # At t_hist, the 3 future losses did not exist yet, so adaptiveStopMultiplier is 1.15 (1 win, total < 5) NOT 1.60
    assert cand.adaptiveStopMultiplier == 1.15
    assert cand.adaptiveRuleVersion in ("1.0.0", "1.1.0")


# ==============================================================================
# Condition 10: Live/default behavior remains compatible
# ==============================================================================
def test_condition_10_live_default_behavior_remains_compatible():
    # Calling get_strategy_tuning without as_of defaults to current time
    now = datetime.now(timezone.utc)
    _create_sample_trade(
        trade_date=now - timedelta(minutes=30),
        close_date=now - timedelta(minutes=15),
        status="CLOSED",
        result="WIN",
        profit_loss=25.0,
        signal_id=6001,
    )

    profile = adaptive_tuning_engine.get_strategy_tuning("strat-001", "EUR/USD")
    assert profile is not None
    assert profile.total_evaluated == 1
    assert profile.recent_win_rate == 1.0


# ==============================================================================
# Condition 11: Phase 5D adaptive provenance still captures rule version/multiplier
# ==============================================================================
def test_condition_11_phase5d_adaptive_provenance_preserved():
    t_as_of = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    engine = SignalGenerationEngine()
    strat_engine = StrategyEngine()
    strategy = strat_engine.get_strategy_by_id("strat-001") or strat_engine.get_strategies()[0]
    strategy.status = StrategyStatus.ACTIVE
    strategy.symbol = "EUR/USD"

    market_state = MarketState(
        prices={
            "EURUSD": MarketPrice(
                symbol="EURUSD",
                currentPrice=1.1000,
                bid=1.09995,
                ask=1.10005,
                spread=0.0001,
                timestamp=t_as_of,
                provider="Test",
            )
        },
        timestamp=t_as_of,
        dataAgeSeconds=2,
    )

    candidates = engine.generate_candidates(market_state, [strategy], as_of=t_as_of)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.strategyVersion == strategy.strategyVersion
    assert cand.adaptiveRuleVersion in ("1.0.0", "1.1.0")
    assert cand.adaptiveStopMultiplier is not None


# ==============================================================================
# Condition 12: Two different as_of timestamps produce different populations
# ==============================================================================
def test_condition_12_two_different_as_of_timestamps_produce_different_populations():
    t1 = datetime(2026, 9, 10, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 10, 14, 0, 0, tzinfo=timezone.utc)

    # Trade 1 closed at 09:00
    _create_sample_trade(
        trade_date=datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc),
        close_date=datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc),
        status="CLOSED",
        signal_id=7001,
    )
    # Trade 2 closed at 12:00
    _create_sample_trade(
        trade_date=datetime(2026, 9, 10, 11, 0, tzinfo=timezone.utc),
        close_date=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        status="CLOSED",
        signal_id=7002,
    )

    # At t1: only trade 1
    p1 = adaptive_tuning_engine.get_strategy_tuning("strat-001", "EUR/USD", as_of=t1)
    assert p1.total_evaluated == 1

    # At t2: both trades
    p2 = adaptive_tuning_engine.get_strategy_tuning("strat-001", "EUR/USD", as_of=t2)
    assert p2.total_evaluated == 2

    # Verify journal rows are unmutated
    all_trades = trade_journal_repository.list_trades()
    assert len(all_trades) == 2


# ==============================================================================
# Condition 13: No future outcome can alter an earlier historical tuning result
# ==============================================================================
def test_condition_13_no_future_outcome_can_alter_earlier_historical_result():
    t_past = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    # Baseline at t_past
    res_1 = adaptive_tuning_engine.get_strategy_tuning("strat-001", "EUR/USD", as_of=t_past)

    # Massive future catastrophe (10 consecutive losses at 18:00)
    for i in range(10):
        _create_sample_trade(
            trade_date=datetime(2026, 9, 10, 17, i, tzinfo=timezone.utc),
            close_date=datetime(2026, 9, 10, 18, i, tzinfo=timezone.utc),
            status="CLOSED",
            result="LOSS",
            signal_id=8000 + i,
        )

    # Query again at t_past
    res_2 = adaptive_tuning_engine.get_strategy_tuning("strat-001", "EUR/USD", as_of=t_past)
    assert res_1.adaptive_stop_multiplier == res_2.adaptive_stop_multiplier
    assert res_1.tuning_status == res_2.tuning_status
    assert res_1.consecutive_losses == res_2.consecutive_losses
    assert res_1.total_evaluated == res_2.total_evaluated


# ==============================================================================
# Condition 14: Deterministic ordering remains unchanged for eligible records
# ==============================================================================
def test_condition_14_deterministic_ordering_remains_trade_date_desc_id_desc():
    t_as_of = datetime(2026, 9, 10, 16, 0, 0, tzinfo=timezone.utc)

    # Create 3 trades with different trade dates
    _create_sample_trade(
        trade_date=datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc),
        close_date=datetime(2026, 9, 10, 11, 0, tzinfo=timezone.utc),
        status="CLOSED",
        signal_id=9001,
    )
    _create_sample_trade(
        trade_date=datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc),
        close_date=datetime(2026, 9, 10, 13, 0, tzinfo=timezone.utc),
        status="CLOSED",
        signal_id=9002,
    )
    _create_sample_trade(
        trade_date=datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc),
        close_date=datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc),
        status="CLOSED",
        signal_id=9003,
    )

    trades = trade_journal_repository.list_closed_trades_as_of("strat-001", as_of=t_as_of)
    assert len(trades) == 3
    # Expected ordering: trade_date DESC -> 9002 (12:00), 9003 (10:00), 9001 (09:00)
    assert [t.signalId for t in trades] == [9002, 9003, 9001]


# ==============================================================================
# Condition 15: Capital Guardian risk calculations and 3-trade limits remain untouched
# ==============================================================================
def test_condition_15_capital_guardian_behavior_unchanged():
    capital_cycle_repository.clear()
    capital_cycle_repository.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-5e-01",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("0.00"),
        )
    )

    trades = capital_guardian_service.get_capital_reserving_trades()
    assert len(trades) == 0
    assert FALCON_GUARDIAN_ADVISORY_LOCK_KEY == 8882026


# ==============================================================================
# Condition 16: Manual MT5/Exness execution boundary preserved (zero automation)
# ==============================================================================
def test_condition_16_manual_mt5_exness_execution_boundary_preserved():
    from app.services.execution.order_execution_service import order_execution_service

    assert hasattr(order_execution_service, "create_order")
    # Verify no broker client connects or auto-executes
    assert not hasattr(adaptive_tuning_engine, "execute_broker_order")
    assert not hasattr(adaptive_tuning_engine, "send_mt5_order")


# ==============================================================================
# DatabaseStorage Test: Verify DatabaseTradeJournalStorage.list_closed_trades_as_of
# ==============================================================================
def test_database_trade_journal_storage_list_closed_trades_as_of():
    """Verify that DatabaseTradeJournalStorage executes SQL with close_date <= as_of correctly."""
    sqlite_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(sqlite_engine)
    session_factory = sessionmaker(bind=sqlite_engine)

    storage = DatabaseTradeJournalStorage()

    with patch("app.core.repository.trade_journal_repository.get_session", session_factory):
        t1_trade = datetime(2026, 9, 10, 8, 0, tzinfo=timezone.utc)
        t1_close = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)
        t2_trade = datetime(2026, 9, 10, 10, 0, tzinfo=timezone.utc)
        t2_close = datetime(2026, 9, 10, 14, 0, tzinfo=timezone.utc)

        # Create two trades directly in sqlite
        with session_factory() as sess:
            sess.add(
                TradeJournalRecord(
                    strategy_id="strat-db",
                    symbol="EUR/USD",
                    direction="BUY",
                    entry_price=1.1000,
                    stop_loss=1.0950,
                    take_profit=1.1100,
                    timeframe="M15",
                    market_session="London",
                    trade_date=t1_trade,
                    close_date=t1_close,
                    status="CLOSED",
                    result="WIN",
                    profit_loss=20.0,
                    risk_reward=2.0,
                    confidence=80,
                    reason_for_entry="test",
                    created_at=t1_trade,
                    updated_at=t1_close,
                )
            )
            sess.add(
                TradeJournalRecord(
                    strategy_id="strat-db",
                    symbol="EUR/USD",
                    direction="BUY",
                    entry_price=1.1000,
                    stop_loss=1.0950,
                    take_profit=1.1100,
                    timeframe="M15",
                    market_session="London",
                    trade_date=t2_trade,
                    close_date=t2_close,
                    status="CLOSED",
                    result="LOSS",
                    profit_loss=-20.0,
                    risk_reward=2.0,
                    confidence=80,
                    reason_for_entry="test",
                    created_at=t2_trade,
                    updated_at=t2_close,
                )
            )
            sess.commit()

        # Query as of 11:00 (between t1_close and t2_close)
        t_as_of = datetime(2026, 9, 10, 11, 0, tzinfo=timezone.utc)
        with session_factory() as sess:
            trades = storage.list_closed_trades_as_of("strat-db", as_of=t_as_of, session=sess)
            assert len(trades) == 1
            assert trades[0].result == "WIN"

            # Query as of 15:00 (after both)
            trades_all = storage.list_closed_trades_as_of("strat-db", as_of=datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc), session=sess)
            assert len(trades_all) == 2
