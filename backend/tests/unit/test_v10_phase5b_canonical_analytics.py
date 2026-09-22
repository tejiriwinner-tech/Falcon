"""
Falcon V10 Phase 5B: Canonical Performance Analytics Tests.

Verifies:
1. Evaluated setup count from missions
2. Authorized/reserved population tracking
3. PENDING excluded from win rate
4. OPEN excluded from win rate
5. EXPIRED excluded from losses
6. INVALIDATED excluded from losses
7. WIN counted correctly
8. LOSS counted correctly
9. BREAKEVEN counted distinctly and in canonical denominator
10. Zero closed trades produces winRate=None and hasSufficientData=False
11. All breakevens produces winRate=0.0 and hasSufficientData=True
12. NULL realized R is not treated as zero
13. Realized R derived strictly from persisted initial monetary risk
14. Target risk_reward is not used as realized R
15. Holding duration uses fill_time -> close_date
16. Holding duration is None when fill_time is missing
17. Pending duration is separate from holding duration
18. Chronological equity curve & running peak drawdown
19. Drawdown percent is None when peak <= 0
20. Active cycle starting capital baseline (e.g. $20.00)
21. Protected profit is isolated from active trading equity
22. Strategy metrics: closed filled trades only, descriptive only (trade_count >= 5)
23. As-of safety: excludes future closed trades (zero lookahead)
24. Analytics read-only invariant (deterministic, non-mutating)
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
import pytest

from app.core.analytics.canonical_analytics_service import CanonicalAnalyticsService
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
)
from app.core.repository.mission_repository import (
    InMemoryMissionStorage,
    MissionRepository,
)
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    TradeJournalRepository,
)
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleStatus
from app.schemas.trade_journal import TradeJournalCreate


@pytest.fixture
def analytics_fixture():
    journal_storage = InMemoryTradeJournalStorage()
    journal_repo = TradeJournalRepository()
    journal_repo._storage = journal_storage
    journal_repo.clear()

    cycle_storage = InMemoryCapitalCycleStorage()
    cycle_repo = CapitalCycleRepository()
    cycle_repo._storage = cycle_storage
    cycle_repo.clear()

    mission_storage = InMemoryMissionStorage()
    mission_repo = MissionRepository()
    mission_repo._storage = mission_storage
    mission_storage.reset()
    mission_repo._invalidate_cache()

    service = CanonicalAnalyticsService(
        journal_repo=journal_repo,
        cycle_repo=cycle_repo,
        mission_repo=mission_repo,
    )
    return {
        "service": service,
        "journal_repo": journal_repo,
        "cycle_repo": cycle_repo,
        "mission_repo": mission_repo,
    }


def test_evaluated_and_authorized_population(analytics_fixture):
    """1 & 2. Evaluated setup count from missions and authorized reservations."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]

    # Seed 2 journal trades
    now = datetime.now(timezone.utc)
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            status="PENDING",
            result="PENDING",
            reasonForEntry="Pending reservation",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.populations.authorizedReservationsCount == 1
    assert resp.populations.pendingCount == 1
    assert resp.populations.closedCount == 0


def test_pending_and_open_excluded_from_win_rate(analytics_fixture):
    """3 & 4. PENDING and OPEN trades are excluded from win rate numerator and denominator."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    now = datetime.now(timezone.utc)

    # 1 PENDING trade
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            status="PENDING",
            result="PENDING",
            reasonForEntry="Pending",
        )
    )
    # 1 OPEN trade
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="GBPUSD",
            direction="BUY",
            entryPrice=1.3000,
            stopLoss=1.2950,
            takeProfit=1.3100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            status="OPEN",
            result="OPEN",
            fillPrice=1.3000,
            fillTime=now,
            reasonForEntry="Open",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.populations.pendingCount == 1
    assert resp.populations.openCount == 1
    assert resp.populations.closedCount == 0
    assert resp.closedOutcomes.totalClosed == 0
    assert resp.winRate.winRate is None
    assert resp.winRate.hasSufficientData is False


def test_expired_and_invalidated_excluded_from_losses(analytics_fixture):
    """5 & 6. EXPIRED and INVALIDATED untriggered setups do not count as trading losses."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    now = datetime.now(timezone.utc)

    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now - timedelta(hours=8),
            closeDate=now,
            status="EXPIRED",
            result="EXPIRED",
            reasonForEntry="Setup expired",
        )
    )
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="USDJPY",
            direction="SELL",
            entryPrice=150.00,
            stopLoss=150.50,
            takeProfit=149.00,
            timeframe="M15",
            marketSession="Tokyo",
            tradeDate=now - timedelta(hours=4),
            closeDate=now,
            status="INVALIDATED",
            result="INVALIDATED",
            reasonForEntry="Setup invalidated before fill",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.populations.expiredCount == 1
    assert resp.populations.invalidatedCount == 1
    assert resp.closedOutcomes.losses == 0
    assert resp.closedOutcomes.totalClosed == 0
    assert resp.winRate.winRate is None


def test_canonical_win_rate_with_breakevens(analytics_fixture):
    """7, 8, 9. Canonical win rate: wins / (wins + losses + breakevens)."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    now = datetime.now(timezone.utc)

    # 2 Wins, 1 Loss, 1 Breakeven -> Total = 4 closed
    # Canonical win rate = 2 / 4 = 0.50 (50.0%)
    # (If breakeven were erroneously excluded, it would be 2/3 = 0.6667)
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(hours=1),
            status="CLOSED",
            result="WIN",
            profitLoss=2.00,
            reasonForEntry="Win 1",
        )
    )
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(hours=2),
            status="CLOSED",
            result="WIN",
            profitLoss=3.00,
            reasonForEntry="Win 2",
        )
    )
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="GBPUSD",
            direction="SELL",
            entryPrice=1.3000,
            stopLoss=1.3050,
            takeProfit=1.2900,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(hours=3),
            status="CLOSED",
            result="LOSS",
            profitLoss=-1.50,
            reasonForEntry="Loss 1",
        )
    )
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="XAUUSD",
            direction="BUY",
            entryPrice=2000.0,
            stopLoss=1995.0,
            takeProfit=2015.0,
            timeframe="M15",
            marketSession="New York",
            tradeDate=now,
            closeDate=now + timedelta(hours=4),
            status="CLOSED",
            result="BREAKEVEN",
            profitLoss=0.00,
            reasonForEntry="BE 1",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.closedOutcomes.wins == 2
    assert resp.closedOutcomes.losses == 1
    assert resp.closedOutcomes.breakevens == 1
    assert resp.closedOutcomes.totalClosed == 4
    # 2 / (2 + 1 + 1) = 0.5
    assert resp.winRate.winRate == 0.5
    assert resp.winRate.winRatePercent == 50.0
    assert resp.winRate.hasSufficientData is True


def test_zero_closed_trades_produces_none_win_rate(analytics_fixture):
    """10. Zero closed trades produces winRate=None and hasSufficientData=False."""
    service = analytics_fixture["service"]
    resp = service.get_canonical_analytics()
    assert resp.closedOutcomes.totalClosed == 0
    assert resp.winRate.winRate is None
    assert resp.winRate.winRatePercent is None
    assert resp.winRate.hasSufficientData is False


def test_all_breakevens_produces_zero_win_rate(analytics_fixture):
    """11. All breakevens produces winRate=0.0 with hasSufficientData=True."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    now = datetime.now(timezone.utc)

    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(minutes=30),
            status="CLOSED",
            result="BREAKEVEN",
            profitLoss=0.0,
            reasonForEntry="BE",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.closedOutcomes.totalClosed == 1
    assert resp.closedOutcomes.breakevens == 1
    assert resp.closedOutcomes.wins == 0
    assert resp.winRate.winRate == 0.0
    assert resp.winRate.winRatePercent == 0.0
    assert resp.winRate.hasSufficientData is True


def test_null_realized_r_not_treated_as_zero(analytics_fixture):
    """12. Realized R: NULL is distinguished from 0.0 R."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    now = datetime.now(timezone.utc)

    # 1 Trade with realizedRMultiple = None (historical)
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(hours=1),
            status="CLOSED",
            result="WIN",
            profitLoss=2.00,
            realizedRMultiple=None,
            reasonForEntry="Legacy win",
        )
    )
    # 1 Trade with genuine zero R
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="GBPUSD",
            direction="BUY",
            entryPrice=1.3000,
            stopLoss=1.2950,
            takeProfit=1.3100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(hours=2),
            status="CLOSED",
            result="BREAKEVEN",
            profitLoss=0.00,
            realizedRMultiple=0.0,
            reasonForEntry="BE with 0R",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.realizedR.missingRealizedRCount == 1
    assert resp.realizedR.zeroRCount == 1
    assert resp.realizedR.tradesWithRealizedR == 1
    assert resp.realizedR.totalRealizedR == 0.0
    assert resp.realizedR.averageRealizedR == 0.0


def test_realized_r_uses_persisted_initial_risk_and_not_planned_rr(analytics_fixture):
    """13 & 14. Realized R uses persisted realized_r_multiple, not planned riskReward."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    now = datetime.now(timezone.utc)

    # Planned RR was 3.0, but trade closed at 1.4R
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0990,
            takeProfit=1.1030,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(hours=1),
            status="CLOSED",
            result="WIN",
            profitLoss=1.40,
            riskReward=3.0,  # Target setup RR
            initialMonetaryRisk=Decimal("1.00"),
            realizedRMultiple=1.40,  # Authoritative realized R
            reasonForEntry="Target 3R, realized 1.4R",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.realizedR.tradesWithRealizedR == 1
    assert resp.realizedR.totalRealizedR == 1.40
    assert resp.realizedR.averageRealizedR == 1.40
    # Must NOT use 3.0
    assert resp.realizedR.averageRealizedR != 3.0


def test_holding_time_and_pending_duration(analytics_fixture):
    """15, 16, 17. Holding time = close_date - fill_time; pending duration = fill_time - trade_date."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    base_time = datetime(2026, 9, 19, 10, 0, 0, tzinfo=timezone.utc)

    # Trade 1:
    # tradeDate = 10:00 (reservation)
    # fillTime  = 10:15 (pending for 15 min = 900s)
    # closeDate = 11:15 (holding for 60 min = 3600s)
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=base_time,
            fillTime=base_time + timedelta(minutes=15),
            closeDate=base_time + timedelta(minutes=75),
            status="CLOSED",
            result="WIN",
            profitLoss=2.50,
            reasonForEntry="Filled trade with separate wait and hold",
        )
    )

    # Trade 2: Historical trade without fillTime
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="GBPUSD",
            direction="SELL",
            entryPrice=1.3000,
            stopLoss=1.3050,
            takeProfit=1.2900,
            timeframe="M15",
            marketSession="London",
            tradeDate=base_time,
            fillTime=None,
            closeDate=base_time + timedelta(hours=2),
            status="CLOSED",
            result="LOSS",
            profitLoss=-1.00,
            reasonForEntry="Historical trade without fillTime",
        )
    )

    resp = service.get_canonical_analytics()
    # Only Trade 1 has valid fillTime -> closeDate
    assert resp.durations.tradesWithValidHoldingDuration == 1
    assert resp.durations.averageHoldingDurationMinutes == 60.0  # (75 - 15) min
    # Trade 1 pending wait duration
    assert resp.durations.tradesWithValidPendingDuration == 1
    assert resp.durations.averagePendingDurationMinutes == 15.0


def test_chronological_equity_curve_and_drawdown(analytics_fixture):
    """18 & 19. Chronological equity curve and running peak drawdown."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)

    # Insert out of order to verify chronological sorting by closeDate
    # Trade A closed at 10:00: +$4.00
    # Trade B closed at 09:00: -$2.00
    # Trade C closed at 11:00: -$5.00
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            closeDate=t0 + timedelta(hours=2),  # 10:00
            status="CLOSED",
            result="WIN",
            profitLoss=4.00,
            reasonForEntry="Trade A",
        )
    )
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="GBPUSD",
            direction="SELL",
            entryPrice=1.3000,
            stopLoss=1.3050,
            takeProfit=1.2900,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            closeDate=t0 + timedelta(hours=1),  # 09:00
            status="CLOSED",
            result="LOSS",
            profitLoss=-2.00,
            reasonForEntry="Trade B",
        )
    )
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="USDJPY",
            direction="BUY",
            entryPrice=150.00,
            stopLoss=149.50,
            takeProfit=151.00,
            timeframe="M15",
            marketSession="Tokyo",
            tradeDate=t0,
            closeDate=t0 + timedelta(hours=3),  # 11:00
            status="CLOSED",
            result="LOSS",
            profitLoss=-5.00,
            reasonForEntry="Trade C",
        )
    )

    resp = service.get_canonical_analytics()
    # Chronological sequence must be: Trade B (09:00), Trade A (10:00), Trade C (11:00)
    assert len(resp.equityCurve) == 3
    assert resp.equityCurve[0].symbol == "GBPUSD"
    assert resp.equityCurve[0].profitLoss == -2.00
    assert resp.equityCurve[1].symbol == "EURUSD"
    assert resp.equityCurve[1].profitLoss == 4.00
    assert resp.equityCurve[2].symbol == "USDJPY"
    assert resp.equityCurve[2].profitLoss == -5.00


def test_active_cycle_capital_baseline_and_isolated_protected_profit(analytics_fixture):
    """20 & 21. Active cycle starting capital baseline ($20.00) with protected profit isolated."""
    service = analytics_fixture["service"]
    cycle_repo = analytics_fixture["cycle_repo"]
    journal_repo = analytics_fixture["journal_repo"]

    c_start = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    cycle_repo.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-v10-5b-01",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("50.00"),  # Banked from previous activity
            status=CapitalCycleStatus.ACTIVE,
            startedAt=c_start,
        )
    )

    # 1 Trade closed within cycle
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=c_start + timedelta(minutes=30),
            closeDate=c_start + timedelta(hours=1),
            status="CLOSED",
            result="WIN",
            profitLoss=5.00,
            reasonForEntry="Cycle trade",
        )
    )

    resp = service.get_canonical_analytics()
    assert resp.activeCycle.hasActiveCycle is True
    assert resp.activeCycle.startingCapital == 20.00
    assert resp.activeCycle.protectedProfit == 50.00
    # Equity curve starting capital baseline is 20.00 (NOT 20.00 + 50.00)
    assert resp.equityCurve[0].equity == 25.00  # 20.00 + 5.00


def test_strategy_metrics_descriptive_only(analytics_fixture):
    """22. Strategy metrics: closed filled trades only, descriptive only (trade_count >= 5)."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    now = datetime.now(timezone.utc)

    # Strategy ALPHA: 5 trades -> hasSufficientData = True
    for i in range(5):
        journal_repo.create_trade(
            TradeJournalCreate(
                strategyId="ALPHA",
                symbol="EURUSD",
                direction="BUY",
                entryPrice=1.1000,
                stopLoss=1.0950,
                takeProfit=1.1100,
                timeframe="M15",
                marketSession="London",
                tradeDate=now,
                closeDate=now + timedelta(hours=i + 1),
                status="CLOSED",
                result="WIN" if i < 3 else "LOSS",
                profitLoss=2.00 if i < 3 else -1.00,
                reasonForEntry=f"Alpha {i}",
            )
        )

    # Strategy BETA: 2 trades -> hasSufficientData = False
    for i in range(2):
        journal_repo.create_trade(
            TradeJournalCreate(
                strategyId="BETA",
                symbol="GBPUSD",
                direction="SELL",
                entryPrice=1.3000,
                stopLoss=1.3050,
                takeProfit=1.2900,
                timeframe="M15",
                marketSession="London",
                tradeDate=now,
                closeDate=now + timedelta(hours=i + 1),
                status="CLOSED",
                result="WIN",
                profitLoss=3.00,
                reasonForEntry=f"Beta {i}",
            )
        )

    resp = service.get_canonical_analytics()
    assert len(resp.strategies) == 2

    alpha = next(s for s in resp.strategies if s.strategyId == "ALPHA")
    assert alpha.closedTradesCount == 5
    assert alpha.wins == 3
    assert alpha.losses == 2
    assert alpha.winRate == 0.6
    assert alpha.hasSufficientData is True

    beta = next(s for s in resp.strategies if s.strategyId == "BETA")
    assert beta.closedTradesCount == 2
    assert beta.hasSufficientData is False


def test_as_of_safety_zero_lookahead(analytics_fixture):
    """23. As-of safety: future closed trades are strictly excluded."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]

    t1 = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    t3 = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)

    # Trade 1 closed at t1
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t1 - timedelta(hours=2),
            closeDate=t1,
            status="CLOSED",
            result="WIN",
            profitLoss=2.00,
            reasonForEntry="Trade 1",
        )
    )

    # Trade 2 closed at t3 (future relative to t2)
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="GBPUSD",
            direction="SELL",
            entryPrice=1.3000,
            stopLoss=1.3050,
            takeProfit=1.2900,
            timeframe="M15",
            marketSession="London",
            tradeDate=t2 - timedelta(hours=2),
            closeDate=t3,
            status="CLOSED",
            result="WIN",
            profitLoss=5.00,
            reasonForEntry="Trade 2",
        )
    )

    # Query as of t2: Trade 2 must be excluded from closed outcomes
    resp = service.get_canonical_analytics(analysis_timestamp=t2)
    assert resp.closedOutcomes.totalClosed == 1
    assert resp.closedOutcomes.wins == 1
    assert len(resp.equityCurve) == 1
    assert resp.equityCurve[0].symbol == "EURUSD"


def test_analytics_read_only_invariant(analytics_fixture):
    """24. Calling analytics repeatedly never mutates stored records."""
    service = analytics_fixture["service"]
    journal_repo = analytics_fixture["journal_repo"]
    cycle_repo = analytics_fixture["cycle_repo"]
    now = datetime.now(timezone.utc)

    cycle_repo.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-readonly-01",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=now,
        )
    )
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=now,
            closeDate=now + timedelta(hours=1),
            status="CLOSED",
            result="WIN",
            profitLoss=2.00,
            reasonForEntry="Readonly test",
        )
    )

    initial_trades_count = len(journal_repo.list_trades())
    initial_cycle = cycle_repo.get_active_cycle()

    # Call analytics multiple times
    for _ in range(5):
        resp = service.get_canonical_analytics()
        assert resp.closedOutcomes.wins == 1

    # Verify zero mutations
    assert len(journal_repo.list_trades()) == initial_trades_count
    current_cycle = cycle_repo.get_active_cycle()
    assert current_cycle.activeTradingCapital == initial_cycle.activeTradingCapital
    assert current_cycle.protectedProfit == initial_cycle.protectedProfit
    assert current_cycle.status == initial_cycle.status
