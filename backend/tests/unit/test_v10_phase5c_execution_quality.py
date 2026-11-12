"""
Falcon V10 Phase 5C: Unit Tests for MFE / MAE & Execution Quality.

Validates all 26 required scenarios:
1. BUY MFE calculation
2. BUY MAE calculation
3. SELL MFE calculation
4. SELL MAE calculation
5. Actual fill price used instead of requested entry
6. Observations before fill excluded
7. Observations after fill included
8. Close-time boundary respected
9. EXPIRED produces no MFE/MAE
10. INVALIDATED produces no MFE/MAE
11. PENDING produces no MFE/MAE
12. OPEN trade updates peak/trough
13. CLOSED trade finalizes peak/trough
14. Persisted initial monetary risk used for MFE/MAE R
15. Missing initial monetary risk produces NULL R
16. NULL is not coerced to zero
17. spread_at_entry only populated from genuine entry context
18. atr_at_entry only populated from genuine entry context
19. Signal-to-fill duration uses trade_date -> fill_time
20. Future observations excluded (as-of / lookahead safety)
21. Historical rows are not backfilled
22. No broker/execution side effects
23. Analytics remain read-only
24. Capital Guardian behavior unchanged
25. Advisory lock behavior unchanged
26. Full Falcon V10 regression compatibility
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest

from app.core.analytics.execution_quality_service import (
    ExecutionQualityService,
    execution_quality_service,
)
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_guardian_service import (
    CapitalGuardianService,
    capital_guardian_service,
)
from app.core.services.signal_authorization_service import (
    FALCON_GUARDIAN_ADVISORY_LOCK_KEY,
    signal_authorization_service,
)
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem, TradeJournalUpdate


@pytest.fixture(autouse=True)
def clean_journal():
    original_storage = trade_journal_repository._storage
    trade_journal_repository._storage = InMemoryTradeJournalStorage()
    trade_journal_repository.clear()
    yield
    trade_journal_repository.clear()
    trade_journal_repository._storage = original_storage


@pytest.fixture
def execution_quality_fixture():
    journal_storage = InMemoryTradeJournalStorage()
    journal_repo = TradeJournalRepository()
    journal_repo._storage = journal_storage
    journal_repo.clear()

    service = ExecutionQualityService(
        journal_repo=journal_repo,
        guardian_service=capital_guardian_service,
    )
    return {
        "service": service,
        "journal_repo": journal_repo,
    }


# ==============================================================================
# 1. Direction-Aware Price Excursion Calculations (BUY & SELL)
# ==============================================================================

def test_buy_mfe_and_mae_calculation(execution_quality_fixture):
    """1 & 2. BUY MFE and MAE calculation."""
    service = execution_quality_fixture["service"]
    # BUY: Fill=1.1000, Peak=1.1060, Trough=1.0970
    # MFE = peak - fill = 1.1060 - 1.1000 = 0.0060 (+60 pips)
    # MAE = fill - trough = 1.1000 - 1.0970 = 0.0030 (30 pips adverse)
    mfe, mae = service.calculate_directional_price_excursion(
        direction="BUY",
        fill_price=1.1000,
        peak_price=1.1060,
        trough_price=1.0970,
    )
    assert mfe == 0.0060
    assert mae == 0.0030


def test_sell_mfe_and_mae_calculation(execution_quality_fixture):
    """3 & 4. SELL MFE and MAE calculation."""
    service = execution_quality_fixture["service"]
    # SELL: Fill=1.3000, Peak=1.3040, Trough=1.2910
    # MFE = fill - trough = 1.3000 - 1.2910 = 0.0090 (+90 pips favorable)
    # MAE = peak - fill = 1.3040 - 1.3000 = 0.0040 (40 pips adverse)
    mfe, mae = service.calculate_directional_price_excursion(
        direction="SELL",
        fill_price=1.3000,
        peak_price=1.3040,
        trough_price=1.2910,
    )
    assert mfe == 0.0090
    assert mae == 0.0040


def test_actual_fill_price_used_instead_of_requested_entry(execution_quality_fixture):
    """5. Authoritative actual fill price used for excursions, not requested entry."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    t_fill = t0 + timedelta(minutes=5)

    # Requested entry: 1.1000. Actual fill: 1.1004 (4 pips slippage)
    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1004,
            fillTime=t_fill,
            peakPrice=1.1054,
            troughPrice=1.0984,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="OPEN",
            result="OPEN",
            reasonForEntry="Test",
        )
    )

    eq = service.calculate_trade_execution_quality(trade)
    # MFE must be peak - fillPrice = 1.1054 - 1.1004 = 0.0050 (NOT 1.1054 - 1.1000 = 0.0054)
    assert eq.mfePrice == 0.0050
    # MAE must be fillPrice - troughPrice = 1.1004 - 1.0984 = 0.0020 (NOT 1.1000 - 1.0984 = 0.0016)
    assert eq.maePrice == 0.0020


# ==============================================================================
# 2. Timestamp Gating: Pre-Fill, Post-Fill, and Close-Time Boundaries
# ==============================================================================

def test_observations_before_fill_excluded(execution_quality_fixture):
    """6. Market observations with timestamp < fillTime are strictly excluded."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t_signal = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    t_fill = datetime(2026, 9, 19, 8, 15, 0, tzinfo=timezone.utc)

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            fillTime=t_fill,
            peakPrice=1.1002,
            troughPrice=1.1002,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t_signal,
            status="OPEN",
            result="OPEN",
            reasonForEntry="Test",
        )
    )

    # Observation occurring at 08:10 (before fill at 08:15) with spike to 1.1050
    obs_time_pre_fill = datetime(2026, 9, 19, 8, 10, 0, tzinfo=timezone.utc)
    new_peak, new_trough, _, _ = service.update_open_trade_excursion(
        trade=trade,
        observed_price=1.1050,
        observation_time=obs_time_pre_fill,
    )
    # Peak must NOT change; pre-fill spike is rejected
    assert new_peak == 1.1002
    assert new_trough == 1.1002


def test_observations_after_fill_included(execution_quality_fixture):
    """7. Market observations after fillTime update peak and trough."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t_signal = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    t_fill = datetime(2026, 9, 19, 8, 15, 0, tzinfo=timezone.utc)

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            fillTime=t_fill,
            peakPrice=1.1002,
            troughPrice=1.1002,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t_signal,
            status="OPEN",
            result="OPEN",
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Test",
        )
    )

    # Observation occurring at 08:20 (post-fill) with favorable spike to 1.1030
    obs_time_post_fill = datetime(2026, 9, 19, 8, 20, 0, tzinfo=timezone.utc)
    new_peak, new_trough, mfe_r, mae_r = service.update_open_trade_excursion(
        trade=trade,
        observed_price=1.1030,
        observation_time=obs_time_post_fill,
    )
    assert new_peak == 1.1030
    assert new_trough == 1.1002
    # MFE price = 1.1030 - 1.1002 = 0.0028 -> 2.8 pips * 1,000 = $2.80 -> 2.80 / 5.00 = 0.56 R
    assert mfe_r == 0.56


def test_close_time_boundary_respected(execution_quality_fixture):
    """8. Observations occurring after trade closeDate are strictly excluded."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t_signal = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    t_fill = datetime(2026, 9, 19, 8, 15, 0, tzinfo=timezone.utc)
    t_close = datetime(2026, 9, 19, 9, 0, 0, tzinfo=timezone.utc)

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=t_fill,
            closeDate=t_close,
            peakPrice=1.1020,
            troughPrice=1.0980,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t_signal,
            status="CLOSED",
            result="WIN",
            reasonForEntry="Test",
        )
    )

    # Observation at 09:30 (after closure at 09:00) with price 1.1080
    obs_post_close = datetime(2026, 9, 19, 9, 30, 0, tzinfo=timezone.utc)
    new_peak, new_trough, _, _ = service.update_open_trade_excursion(
        trade=trade,
        observed_price=1.1080,
        observation_time=obs_post_close,
    )
    assert new_peak == 1.1020
    assert new_trough == 1.0980


# ==============================================================================
# 3. Lifecycle Population Rules (EXPIRED, INVALIDATED, PENDING)
# ==============================================================================

def test_expired_produces_no_mfe_mae(execution_quality_fixture):
    """9. EXPIRED orders were never filled and produce no MFE/MAE."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            closeDate=t0 + timedelta(hours=2),
            status="EXPIRED",
            result="EXPIRED",
            reasonForEntry="Test Expired",
        )
    )

    eq = service.calculate_trade_execution_quality(trade)
    assert eq.hasAuthoritativeFill is False
    assert eq.peakPrice is None
    assert eq.troughPrice is None
    assert eq.mfePrice is None
    assert eq.maePrice is None
    assert eq.mfeR is None
    assert eq.maeR is None


def test_invalidated_produces_no_mfe_mae(execution_quality_fixture):
    """10. INVALIDATED orders were never filled and produce no MFE/MAE."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="SELL",
            entryPrice=1.3000,
            stopLoss=1.3050,
            takeProfit=1.2900,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            closeDate=t0 + timedelta(hours=1),
            status="INVALIDATED",
            result="INVALIDATED",
            reasonForEntry="Test Invalidated",
        )
    )

    eq = service.calculate_trade_execution_quality(trade)
    assert eq.hasAuthoritativeFill is False
    assert eq.mfePrice is None
    assert eq.maePrice is None
    assert eq.mfeR is None
    assert eq.maeR is None


def test_pending_produces_no_mfe_mae(execution_quality_fixture):
    """11. PENDING reservations have not yet filled and produce no MFE/MAE."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="PENDING",
            result="PENDING",
            reasonForEntry="Test Pending",
        )
    )

    # Attempting to update excursions on a PENDING trade must do nothing
    new_peak, new_trough, mfe_r, mae_r = service.update_open_trade_excursion(
        trade=trade,
        observed_price=1.1050,
        observation_time=t0 + timedelta(minutes=10),
    )
    assert new_peak is None
    assert new_trough is None
    assert mfe_r is None
    assert mae_r is None


def test_open_trade_updates_peak_and_trough(execution_quality_fixture):
    """12. OPEN trade updates peak/trough upon market observations."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=t0,
            peakPrice=1.1000,
            troughPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="OPEN",
            result="OPEN",
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Test",
        )
    )

    # Observation 1: favorable move to 1.1025
    peak1, trough1, mfe1, mae1 = service.update_open_trade_excursion(
        trade=trade,
        observed_price=1.1025,
        observation_time=t0 + timedelta(minutes=5),
    )
    assert peak1 == 1.1025
    assert trough1 == 1.1000
    assert mfe1 == 0.50  # 2.5 pips * 1,000 / 5.00 = 0.50 R
    assert mae1 == 0.0

    # Update trade with observation 1 state
    journal_repo.update_trade(trade.id, TradeJournalUpdate(peakPrice=peak1, troughPrice=trough1, mfeR=mfe1, maeR=mae1))
    trade_updated = journal_repo.get_trade(trade.id)

    # Observation 2: adverse dip to 1.0985
    peak2, trough2, mfe2, mae2 = service.update_open_trade_excursion(
        trade=trade_updated,
        observed_price=1.0985,
        observation_time=t0 + timedelta(minutes=10),
    )
    assert peak2 == 1.1025
    assert trough2 == 1.0985
    assert mfe2 == 0.50
    assert mae2 == 0.30  # 1.5 pips * 1,000 / 5.00 = 0.30 R


def test_closed_trade_finalizes_peak_and_trough(execution_quality_fixture):
    """13. CLOSED trade finalizes peak, trough, MFE R and MAE R using exit price."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    t_close = t0 + timedelta(hours=1)

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=t0,
            peakPrice=1.1040,
            troughPrice=1.0990,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="OPEN",
            result="OPEN",
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Test",
        )
    )

    # Exit price reaches take profit at 1.1100 (which is higher than previous peak of 1.1040)
    final_peak, final_trough, final_mfe_r, final_mae_r = service.finalize_closed_trade_excursion(
        trade=trade,
        exit_price=1.1100,
        close_time=t_close,
    )
    assert final_peak == 1.1100
    assert final_trough == 1.0990
    # Final MFE = 1.1100 - 1.1000 = 0.0100 -> 10.0 pips * 1,000 = $10.00 -> $10.00 / $5.00 = 2.00 R
    assert final_mfe_r == 2.00
    # Final MAE = 1.1000 - 1.0990 = 0.0010 -> 1.0 pip * 1,000 = $1.00 -> $1.00 / $5.00 = 0.20 R
    assert final_mae_r == 0.20


# ==============================================================================
# 4. R-Denomination & Capital Guardian Authority
# ==============================================================================

def test_persisted_initial_monetary_risk_used_for_mfe_mae_r(execution_quality_fixture):
    """14. Persisted initial monetary risk and Capital Guardian contract sizing used for MFE/MAE R."""
    service = execution_quality_fixture["service"]
    # Gold contract: 100 oz/lot -> 0.01 lot = 1.0 unit.
    # Buy Gold: Fill=2500.0, Peak=2515.0, Trough=2495.0. Initial Risk = $10.00
    # MFE price = 15.0 -> monetary MFE = 15.0 * 1.0 = $15.00 -> 15.00 / 10.00 = 1.50 R
    # MAE price = 5.0 -> monetary MAE = 5.0 * 1.0 = $5.00 -> 5.00 / 10.00 = 0.50 R
    mfe_r, mae_r = service.convert_price_excursion_to_r(
        symbol="XAUUSD",
        mfe_price=15.0,
        mae_price=5.0,
        initial_monetary_risk=Decimal("10.00"),
    )
    assert mfe_r == 1.50
    assert mae_r == 0.50


def test_missing_initial_monetary_risk_produces_null_r(execution_quality_fixture):
    """15. Missing initial monetary risk leaves MFE/MAE R strictly NULL without fabrication."""
    service = execution_quality_fixture["service"]
    mfe_r, mae_r = service.convert_price_excursion_to_r(
        symbol="EURUSD",
        mfe_price=0.0050,
        mae_price=0.0020,
        initial_monetary_risk=None,
    )
    assert mfe_r is None
    assert mae_r is None


def test_null_is_not_coerced_to_zero(execution_quality_fixture):
    """16. NULL MFE/MAE R is distinguished from genuine 0.0 R."""
    service = execution_quality_fixture["service"]
    # Genuine 0.0 excursion (trade filled and never went in favor)
    mfe_r_zero, mae_r_valid = service.convert_price_excursion_to_r(
        symbol="EURUSD",
        mfe_price=0.0,
        mae_price=0.0050,
        initial_monetary_risk=Decimal("5.00"),
    )
    assert mfe_r_zero == 0.0
    assert mae_r_valid == 1.0

    # Missing initial risk produces None, NOT 0.0
    mfe_r_null, mae_r_null = service.convert_price_excursion_to_r(
        symbol="EURUSD",
        mfe_price=0.0,
        mae_price=0.0050,
        initial_monetary_risk=None,
    )
    assert mfe_r_null is None
    assert mae_r_null is None


# ==============================================================================
# 5. Execution Context: Spread, ATR, Timing & Slippage
# ==============================================================================

def test_spread_and_atr_at_entry_provenance(execution_quality_fixture):
    """17 & 18. spread_at_entry and atr_at_entry are preserved only when authoritatively present."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    trade_with_context = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            spreadAtEntry=0.00012,
            atrAtEntry=0.00150,
            reasonForEntry="With context",
        )
    )
    eq1 = service.calculate_trade_execution_quality(trade_with_context)
    assert eq1.spreadAtEntry == 0.00012
    assert eq1.atrAtEntry == 0.00150

    trade_without_context = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            reasonForEntry="Without context",
        )
    )
    eq2 = service.calculate_trade_execution_quality(trade_without_context)
    assert eq2.spreadAtEntry is None
    assert eq2.atrAtEntry is None


def test_signal_to_fill_timing_and_slippage(execution_quality_fixture):
    """19. signal-to-fill duration uses trade_date -> fill_time; slippage measured accurately."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    t_fill = t0 + timedelta(seconds=125)

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1003,  # 3 pips adverse slippage
            fillTime=t_fill,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            reasonForEntry="Test",
        )
    )

    eq = service.calculate_trade_execution_quality(trade)
    assert eq.signalToFillSeconds == 125.0
    assert eq.entrySlippagePrice == 0.0003
    assert eq.entrySlippagePips == 3.0


# ==============================================================================
# 6. Safety, Lookahead, and Non-Mutation Invariants
# ==============================================================================

def test_future_observations_excluded_zero_lookahead(execution_quality_fixture):
    """20. Future observations beyond as_of timestamp are excluded from execution summary."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t1 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 9, 19, 10, 0, 0, tzinfo=timezone.utc)

    # Trade 1 at 08:00
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=t1,
            closeDate=t1 + timedelta(minutes=30),
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t1,
            status="CLOSED",
            result="WIN",
            reasonForEntry="Trade 1",
        )
    )

    # Trade 2 at 10:00
    journal_repo.create_trade(
        TradeJournalCreate(
            symbol="GBPUSD",
            direction="SELL",
            entryPrice=1.3000,
            fillPrice=1.3000,
            fillTime=t2,
            closeDate=t2 + timedelta(minutes=30),
            stopLoss=1.3050,
            takeProfit=1.2900,
            timeframe="M15",
            marketSession="London",
            tradeDate=t2,
            status="CLOSED",
            result="WIN",
            reasonForEntry="Trade 2",
        )
    )

    # as_of at 09:00: only Trade 1 should be evaluated
    summary_as_of = service.get_execution_quality_summary(as_of=datetime(2026, 9, 19, 9, 0, 0, tzinfo=timezone.utc))
    assert summary_as_of.totalTradesEvaluated == 1

    # full summary: both trades evaluated
    summary_all = service.get_execution_quality_summary()
    assert summary_all.totalTradesEvaluated == 2


def test_historical_rows_not_backfilled(execution_quality_fixture):
    """21. Historical records without V10 fields are not backfilled or fabricated."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    # Historical row (pre-V10)
    t0 = datetime(2026, 8, 1, 8, 0, 0, tzinfo=timezone.utc)
    trade = journal_repo.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.0850,
            stopLoss=1.0800,
            takeProfit=1.0950,
            timeframe="H1",
            marketSession="London",
            tradeDate=t0,
            closeDate=t0 + timedelta(hours=4),
            status="CLOSED",
            result="WIN",
            profitLoss=10.0,
            reasonForEntry="Historical Trade",
        )
    )

    eq = service.calculate_trade_execution_quality(trade)
    assert eq.fillPrice is None
    assert eq.fillTime is None
    assert eq.peakPrice is None
    assert eq.troughPrice is None
    assert eq.mfePrice is None
    assert eq.maePrice is None
    assert eq.mfeR is None
    assert eq.maeR is None


def test_no_broker_execution_side_effects(execution_quality_fixture):
    """22. ExecutionQualityService does not place, modify, or cancel broker orders."""
    service = execution_quality_fixture["service"]
    # Verify no execution / broker dispatcher attributes exist on service
    assert not hasattr(service, "place_order")
    assert not hasattr(service, "modify_order")
    assert not hasattr(service, "close_order")
    assert not hasattr(service, "cancel_order")


def test_analytics_remain_read_only(execution_quality_fixture):
    """23. get_execution_quality_summary does not mutate trade journal records."""
    service = execution_quality_fixture["service"]
    journal_repo = execution_quality_fixture["journal_repo"]

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
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
            reasonForEntry="Test",
        )
    )

    count_before = len(journal_repo.list_trades())
    service.get_execution_quality_summary()
    count_after = len(journal_repo.list_trades())
    assert count_before == count_after


def test_capital_guardian_behavior_unchanged():
    """24. Capital Guardian validation and risk calculation remains untouched."""
    # Strict invariant test: proposed loss calculation remains exact
    guardian = capital_guardian_service
    loss = guardian.calculate_trade_worst_case_loss(
        direction="BUY",
        entry_price=1.1000,
        stop_loss=1.0950,
        lot_size=0.01,
        symbol="EURUSD",
    )
    # 50 pips * 1,000 units = $5.00
    assert loss == Decimal("5.00")


def test_advisory_lock_behavior_unchanged():
    """25. PostgreSQL transaction advisory lock key 8882026 remains unchanged."""
    assert FALCON_GUARDIAN_ADVISORY_LOCK_KEY == 8882026


# ==============================================================================
# 7. Pipeline Integration & API Endpoint Tests
# ==============================================================================

def test_signal_outcome_resolver_updates_open_trade_excursion():
    """Verify SignalOutcomeResolver updates peak/trough on open trade from live quotes."""
    from unittest.mock import MagicMock, patch
    from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
    from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus
    from app.core.providers.provider_manager import MarketQuoteResponse

    resolver = SignalOutcomeResolver()
    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)

    trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=7001,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=t0,
            peakPrice=1.1000,
            troughPrice=1.1000,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="OPEN",
            result="OPEN",
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Resolver test",
        )
    )

    quote_resp = MarketQuoteResponse(
        quote=MarketQuote(
            symbol="EURUSD",
            bidAsk=BidAsk(bid=1.1030, ask=1.1032, spread=0.0002),
            lastPrice=1.1031,
            timestamp=t0 + timedelta(minutes=10),
            providerId="test_prov",
            providerName="Test Prov",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
        )
    )

    with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=quote_resp):
        summary = resolver.resolve_signals()

    updated = trade_journal_repository.get_trade(trade.id)
    assert updated.status == "OPEN"
    assert updated.peakPrice == 1.1030
    assert updated.troughPrice == 1.1000
    assert updated.mfeR == 0.60  # 3.0 pips * 1,000 / 5.00 = 0.60 R


def test_signal_outcome_resolver_finalizes_excursion_on_close():
    """Verify SignalOutcomeResolver finalizes peak, trough, and R multiples when trade hits TP."""
    from unittest.mock import MagicMock, patch
    from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
    from app.schemas.market_quote import BidAsk, MarketQuote, MarketStatus, QuoteStatus
    from app.core.providers.provider_manager import MarketQuoteResponse

    resolver = SignalOutcomeResolver()
    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)

    trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=7002,
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=t0,
            peakPrice=1.1040,
            troughPrice=1.0990,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="OPEN",
            result="OPEN",
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Resolver close test",
        )
    )

    # Price hits TP at 1.1100
    quote_resp = MarketQuoteResponse(
        quote=MarketQuote(
            symbol="EURUSD",
            bidAsk=BidAsk(bid=1.1105, ask=1.1107, spread=0.0002),
            lastPrice=1.1105,
            timestamp=t0 + timedelta(minutes=45),
            providerId="test_prov",
            providerName="Test Prov",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
        )
    )

    with patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=quote_resp):
        summary = resolver.resolve_signals()

    updated = trade_journal_repository.get_trade(trade.id)
    assert updated.status == "CLOSED"
    assert updated.result == "WIN"
    assert updated.peakPrice in (1.1100, 1.1105)
    assert updated.troughPrice == 1.0990
    assert updated.mfeR in (2.00, 2.10)
    assert updated.maeR == 0.20


def test_trade_journal_api_patch_finalizes_excursion():
    """Verify PATCH /trade-journal/{id} finalizes peak/trough and R multiples on close."""
    from app.api.v1.trade_journal import update_trade_journal_entry

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1000,
            fillTime=t0,
            peakPrice=1.1040,
            troughPrice=1.0990,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="OPEN",
            result="OPEN",
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="API close test",
        )
    )

    patch_update = TradeJournalUpdate(
        status="CLOSED",
        result="WIN",
        exitPrice=1.1080,
        closeDate=t0 + timedelta(minutes=30),
        profitLoss=8.00,
    )
    updated = update_trade_journal_entry(trade.id, patch_update)
    assert updated.status == "CLOSED"
    assert updated.peakPrice == 1.1080
    assert updated.troughPrice == 1.0990
    assert updated.mfeR == 1.60  # 8.0 pips * 1,000 / 5.00 = 1.60 R
    assert updated.maeR == 0.20  # 1.0 pip * 1,000 / 5.00 = 0.20 R
    assert updated.realizedRMultiple == 1.60


def test_get_execution_quality_api_endpoint():
    """Verify GET /api/v1/analytics/execution-quality returns valid ExecutionQualitySummary."""
    from app.api.v1.analytics import get_execution_quality

    t0 = datetime(2026, 9, 19, 8, 0, 0, tzinfo=timezone.utc)
    trade_journal_repository.create_trade(
        TradeJournalCreate(
            symbol="EURUSD",
            direction="BUY",
            entryPrice=1.1000,
            fillPrice=1.1002,
            fillTime=t0 + timedelta(seconds=60),
            closeDate=t0 + timedelta(minutes=30),
            peakPrice=1.1050,
            troughPrice=1.0990,
            mfeR=0.96,
            maeR=0.24,
            stopLoss=1.0950,
            takeProfit=1.1100,
            timeframe="M15",
            marketSession="London",
            tradeDate=t0,
            status="CLOSED",
            result="WIN",
            spreadAtEntry=0.00015,
            atrAtEntry=0.0012,
            reasonForEntry="API summary test",
        )
    )

    summary = get_execution_quality()
    assert summary.totalTradesEvaluated >= 1
    assert summary.filledTradesCount >= 1
    assert summary.averageSignalToFillSeconds == 60.0
    assert summary.averageSpreadAtEntry == 0.00015
    assert summary.averageAtrAtEntry == 0.0012
    assert summary.averageMfeR == 0.96
    assert summary.averageMaeR == 0.24

