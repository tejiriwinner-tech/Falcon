"""
Stage 1 Comprehensive Verification Test Suite: Safety & Accounting

Verifies all five pre-deployment gates and priority remediations:
1. Authoritative Exit State Machine & Partial-Profit Accounting (Ghost Partial Prevention)
2. Cross-Worker 45-Minute Post-Stop Cooldown (Multi-process and restart safe)
3. Daily Rollover Blackout Boundaries (20:50:00 - 21:30:00 UTC)
4. Instrument-Specific Spread Caps & Strict Unit Accounting (Gold cash USD vs FX pips)
5. Fail-Closed Invariants on Stale (>30s) or Missing Quotes
6. Immutable Stop Distance (initialStopLoss) & Risk Preservation
"""

from datetime import datetime, timezone, timedelta, time
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.core.repository.capital_cycle_repository import CapitalCycleRepository, InMemoryCapitalCycleStorage
from app.core.repository.trade_journal_repository import InMemoryTradeJournalStorage, TradeJournalRepository
from app.core.services.capital_cycle_service import CapitalCycleService
from app.core.services.capital_guardian_service import CapitalGuardianService
from app.core.services.signal_authorization_service import SignalAuthorizationService
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.core.instruments.instrument_registry import instrument_registry
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleStatus
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.market_quote import MarketQuoteResponse, MarketQuote, BidAsk
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalItem, TradeJournalUpdate


@pytest.fixture
def stage1_env():
    """Provides isolated repositories and services for Stage 1 validation."""
    cycle_storage = InMemoryCapitalCycleStorage()
    journal_storage = InMemoryTradeJournalStorage()

    cycle_repo = CapitalCycleRepository(storage=cycle_storage)
    journal_repo = TradeJournalRepository.__new__(TradeJournalRepository)
    journal_repo._storage = journal_storage
    journal_repo.clear()

    cycle_service = CapitalCycleService(repository=cycle_repo)
    guardian_service = CapitalGuardianService(
        cycle_service=cycle_service,
        journal_repository=journal_repo,
        registry=instrument_registry,
    )
    auth_service = SignalAuthorizationService(
        cycle_service=cycle_service,
        guardian_service=guardian_service,
        journal_repo=journal_repo,
        cycle_repo=cycle_repo,
    )

    # Active $20 trading capital cycle
    cycle_repo.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-stage1-001",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("50.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=datetime.now(timezone.utc),
        )
    )

    resolver = SignalOutcomeResolver()

    return {
        "cycle_repo": cycle_repo,
        "journal_repo": journal_repo,
        "cycle_service": cycle_service,
        "guardian_service": guardian_service,
        "auth_service": auth_service,
        "resolver": resolver,
    }


# ==============================================================================
# GATE 1: PARTIAL-PROFIT ACCOUNTING & GHOST PARTIAL PREVENTION
# ==============================================================================

def test_ghost_partial_prevention_breakeven_without_fill_yields_zero_r(stage1_env):
    """
    Moving stop to BE alone (BE_PROTECTED) must NOT book +0.50R profit on breakeven exit
    unless 50% was actually confirmed filled. Must yield strictly 0.00R.
    """
    now = datetime.now(timezone.utc)
    journal_repo = stage1_env["journal_repo"]
    resolver = stage1_env["resolver"]

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            signalId=501,
            strategyId="strat-004",
            symbol="GBPUSD",
            direction="BUY",
            timeframe="M15",
            marketSession="London",
            entryPrice=1.2500,
            stopLoss=1.2500,  # Already moved to BE
            initialStopLoss=1.2450,  # Initial 50 pips risk
            takeProfit=1.2650,
            status="OPEN",
            tradeDate=now,
            confidence=85,
            notes="Falcon | [BE_PROTECTED: Locked at entry at +1.0R]",
            peakPrice=1.2550,
            mfeR=1.0,
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Momentum Entry",
            fillPrice=1.2500,
            fillTime=now,
        )
    )

    # Market retraces to entry (1.2500)
    mock_quote = MarketQuote(
        symbol="GBPUSD",
        providerId="oanda",
        providerName="OANDA",
        bid=1.2499,
        ask=1.2501,
        lastPrice=1.2500,
        spread=0.2,
        timestamp=now,
        bidAsk=BidAsk(bid=1.2499, ask=1.2501, spread=0.0002),
    )

    with patch("app.core.services.signal_outcome_resolver.trade_journal_repository", journal_repo), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=MarketQuoteResponse(quote=mock_quote)), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])):

        resolver.resolve_signals()

    closed = journal_repo.get_trade(trade.id)
    assert closed.status == "CLOSED"
    assert closed.result in ("BREAKEVEN", "BE")
    # STRICT INVARIANT: 0.00R realized, ZERO ghost profit
    assert closed.realizedRMultiple == 0.0
    assert closed.profitLoss == 0.0


def test_confirmed_partial_fill_at_1r_yields_half_r_on_breakeven(stage1_env):
    """
    When 50% scale-out is confirmed at +1.0R, subsequent breakeven exit
    realizes exactly: 0.5 * 1.0R + 0.5 * 0.0R = +0.50R.
    """
    now = datetime.now(timezone.utc)
    journal_repo = stage1_env["journal_repo"]
    resolver = stage1_env["resolver"]

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            signalId=502,
            strategyId="strat-004",
            symbol="GBPUSD",
            direction="BUY",
            timeframe="M15",
            marketSession="London",
            entryPrice=1.2500,
            stopLoss=1.2500,
            initialStopLoss=1.2450,
            takeProfit=1.2650,
            status="OPEN",
            tradeDate=now,
            confidence=85,
            notes="Falcon | [TP1_SCALED_OUT_50: 50% profit banked at +1.0R] | [BE_PROTECTED: Locked at entry at +1.0R]",
            peakPrice=1.2550,
            mfeR=1.0,
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Momentum Entry",
            fillPrice=1.2500,
            fillTime=now,
        )
    )

    mock_quote = MarketQuote(
        symbol="GBPUSD",
        providerId="oanda",
        providerName="OANDA",
        bid=1.2499,
        ask=1.2501,
        lastPrice=1.2500,
        spread=0.2,
        timestamp=now,
        bidAsk=BidAsk(bid=1.2499, ask=1.2501, spread=0.0002),
    )

    with patch("app.core.services.signal_outcome_resolver.trade_journal_repository", journal_repo), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=MarketQuoteResponse(quote=mock_quote)), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])):

        resolver.resolve_signals()

    closed = journal_repo.get_trade(trade.id)
    assert closed.status == "CLOSED"
    assert closed.result in ("BREAKEVEN", "BE")
    assert closed.realizedRMultiple == 0.50
    assert closed.profitLoss == 2.50  # 0.50R * $5.00 risk = $2.50


def test_confirmed_partial_fill_at_1_5r_yields_0_75r_on_breakeven(stage1_env):
    """
    When 50% scale-out is confirmed at +1.5R, subsequent breakeven exit
    realizes exactly: 0.5 * 1.5R + 0.5 * 0.0R = +0.75R.
    """
    now = datetime.now(timezone.utc)
    journal_repo = stage1_env["journal_repo"]
    resolver = stage1_env["resolver"]

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            signalId=503,
            strategyId="strat-006",
            symbol="EURUSD",
            direction="BUY",
            timeframe="M15",
            marketSession="London",
            entryPrice=1.1000,
            stopLoss=1.1000,
            initialStopLoss=1.0980,
            takeProfit=1.1060,
            status="OPEN",
            tradeDate=now,
            confidence=85,
            notes="Falcon | [TP1_SCALED_OUT_50: 50% profit banked at +1.5R] | [BE_PROTECTED: Locked at entry at +1.0R]",
            peakPrice=1.1030,
            mfeR=1.5,
            initialMonetaryRisk=Decimal("4.00"),
            reasonForEntry="Breakout Entry",
            fillPrice=1.1000,
            fillTime=now,
        )
    )

    mock_quote = MarketQuote(
        symbol="EURUSD",
        providerId="oanda",
        providerName="OANDA",
        bid=1.0999,
        ask=1.1001,
        lastPrice=1.1000,
        spread=0.2,
        timestamp=now,
        bidAsk=BidAsk(bid=1.0999, ask=1.1001, spread=0.0002),
    )

    with patch("app.core.services.signal_outcome_resolver.trade_journal_repository", journal_repo), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=MarketQuoteResponse(quote=mock_quote)), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])):

        resolver.resolve_signals()

    closed = journal_repo.get_trade(trade.id)
    assert closed.status == "CLOSED"
    assert closed.result in ("BREAKEVEN", "BE")
    assert closed.realizedRMultiple == 0.75
    assert closed.profitLoss == 3.00  # 0.75R * $4.00 risk = $3.00


def test_resolver_idempotence_on_repeated_calls(stage1_env):
    """
    Repeated resolver cycles on closed or open trades must be idempotent and
    not alter finalized outcomes or double-count profits.
    """
    now = datetime.now(timezone.utc)
    journal_repo = stage1_env["journal_repo"]
    resolver = stage1_env["resolver"]

    trade = journal_repo.create_trade(
        TradeJournalCreate(
            signalId=504,
            strategyId="strat-001",
            symbol="XAUUSD",
            direction="BUY",
            timeframe="M15",
            marketSession="London",
            entryPrice=2000.0,
            stopLoss=1995.0,
            initialStopLoss=1995.0,
            takeProfit=2015.0,
            status="OPEN",
            tradeDate=now,
            confidence=85,
            notes="Falcon Test Trade",
            initialMonetaryRisk=Decimal("5.00"),
            reasonForEntry="Gold Setup",
            fillPrice=2000.0,
            fillTime=now,
        )
    )

    # Price hits stop-loss (1995.0)
    mock_quote = MarketQuote(
        symbol="XAUUSD",
        providerId="oanda",
        providerName="OANDA",
        bid=1994.5,
        ask=1995.0,
        lastPrice=1994.8,
        spread=0.5,
        timestamp=now,
        bidAsk=BidAsk(bid=1994.5, ask=1995.0, spread=0.5),
    )

    with patch("app.core.services.signal_outcome_resolver.trade_journal_repository", journal_repo), \
         patch("app.core.services.signal_outcome_resolver.provider_manager.get_market_quote", return_value=MarketQuoteResponse(quote=mock_quote)), \
         patch("app.core.services.signal_outcome_resolver.signal_service.build_signals", return_value=MagicMock(signals=[])):

        summary1 = resolver.resolve_signals()
        summary2 = resolver.resolve_signals()

    assert summary1.lossesCount == 1
    assert summary2.lossesCount == 0  # Already closed, not processed twice!

    closed = journal_repo.get_trade(trade.id)
    assert closed.status == "CLOSED"
    assert closed.result in ("LOSS", "LOST")
    assert closed.realizedRMultiple == -1.0


# ==============================================================================
# GATE 2: CROSS-WORKER 45-MINUTE POST-STOP COOLDOWN
# ==============================================================================

def test_post_stop_cooldown_blocks_reentries_within_45_minutes(stage1_env):
    """
    A stopped-out trade on (strategy_id, symbol) strictly blocks new order proposals
    for 45 minutes across all processes.
    """
    now = datetime.now(timezone.utc)
    auth = stage1_env["auth_service"]
    journal_repo = stage1_env["journal_repo"]

    # Record a stop-loss trade closed 10 minutes ago on GBPJPY strat-016
    journal_repo.create_trade(
        TradeJournalCreate(
            signalId=910,
            strategyId="strat-016",
            symbol="GBPJPY",
            direction="BUY",
            timeframe="M15",
            marketSession="London",
            entryPrice=190.50,
            stopLoss=189.80,
            takeProfit=192.50,
            status="CLOSED",
            result="LOST",
            tradeDate=now - timedelta(minutes=25),
            closeDate=now - timedelta(minutes=10),  # Stopped out 10m ago!
            reasonForEntry="Dragon FVG",
            reasonForExit="Stop Loss Hit",
            initialMonetaryRisk=Decimal("5.00"),
        )
    )

    prop = ProposedTradeInput(
        symbol="GBPJPY",
        direction="BUY",
        entryPrice=Decimal("190.40"),
        stopLoss=Decimal("189.70"),
        takeProfit=Decimal("192.00"),
        lotSize=Decimal("0.01"),
    )

    decision, res = auth.authorize_and_reserve(
        proposal=prop,
        signal_id=911,
        strategy_id="strat-016",
    )

    assert not decision.allowed
    assert "POST-STOP COOLDOWN" in decision.reason
    assert "strat-016" in decision.reason
    assert res is None


def test_post_stop_cooldown_expires_after_45_minutes(stage1_env):
    """
    Once 46 minutes have elapsed since the stop-out, the strategy is unblocked.
    """
    now = datetime.now(timezone.utc)
    auth = stage1_env["auth_service"]
    journal_repo = stage1_env["journal_repo"]

    # Trade stopped out 46 minutes ago on GBPUSD
    journal_repo.create_trade(
        TradeJournalCreate(
            signalId=912,
            strategyId="strat-004",
            symbol="GBPUSD",
            direction="BUY",
            timeframe="M15",
            marketSession="London",
            entryPrice=1.2500,
            stopLoss=1.2450,
            takeProfit=1.2650,
            status="CLOSED",
            result="LOST",
            tradeDate=now - timedelta(minutes=60),
            closeDate=now - timedelta(minutes=46),  # 46m elapsed!
            reasonForEntry="Momentum Entry",
            reasonForExit="Stop Loss Hit",
            initialMonetaryRisk=Decimal("5.00"),
        )
    )

    prop = ProposedTradeInput(
        symbol="GBPUSD",
        direction="BUY",
        entryPrice=Decimal("1.2510"),
        stopLoss=Decimal("1.2460"),
        takeProfit=Decimal("1.2660"),
        lotSize=Decimal("0.01"),
    )

    decision, res = auth.authorize_and_reserve(
        proposal=prop,
        signal_id=913,
        strategy_id="strat-004",
    )

    assert decision.allowed
    assert res is not None
    assert res.status == "PENDING"


def test_post_stop_cooldown_is_strategy_and_symbol_specific(stage1_env):
    """
    Cooldown on strat-004 (GBPUSD) does NOT block strat-005 (different strategy)
    or strat-004 on a different symbol (EURUSD).
    """
    now = datetime.now(timezone.utc)
    auth = stage1_env["auth_service"]
    journal_repo = stage1_env["journal_repo"]

    journal_repo.create_trade(
        TradeJournalCreate(
            signalId=914,
            strategyId="strat-004",
            symbol="GBPUSD",
            direction="BUY",
            timeframe="M15",
            marketSession="London",
            entryPrice=1.2500,
            stopLoss=1.2450,
            takeProfit=1.2650,
            status="CLOSED",
            result="LOST",
            tradeDate=now - timedelta(minutes=20),
            closeDate=now - timedelta(minutes=5),
            reasonForEntry="Momentum Entry",
            reasonForExit="Stop Loss Hit",
            initialMonetaryRisk=Decimal("5.00"),
        )
    )

    # Different strategy on GBPUSD (strat-005 vs stopped out strat-004)
    prop1 = ProposedTradeInput(
        symbol="GBPUSD",
        direction="BUY",
        entryPrice=Decimal("1.2510"),
        stopLoss=Decimal("1.2460"),
        takeProfit=Decimal("1.2660"),
        lotSize=Decimal("0.01"),
    )
    dec1, res1 = auth.authorize_and_reserve(proposal=prop1, signal_id=915, strategy_id="strat-005")
    assert dec1.allowed
    assert res1 is not None

    # Same strategy on different symbol (EURUSD)
    prop2 = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.1000"),
        stopLoss=Decimal("1.0950"),
        takeProfit=Decimal("1.1150"),
        lotSize=Decimal("0.01"),
    )
    dec2, res2 = auth.authorize_and_reserve(proposal=prop2, signal_id=916, strategy_id="strat-004")
    assert dec2.allowed
    assert res2 is not None


# ==============================================================================
# GATE 3: ROLLOVER BLACKOUT, SPREAD CAPS & STALE QUOTE INVARIANTS
# ==============================================================================

def test_daily_rollover_blackout_boundary_conditions(stage1_env):
    """
    UTC Daily Rollover Blackout: 20:50:00 to 21:30:00 UTC.
    Tests boundary seconds explicitly:
      - 20:49:59 UTC: Allowed
      - 20:50:00 UTC: Blocked
      - 21:15:00 UTC: Blocked
      - 21:30:00 UTC: Blocked
      - 21:30:01 UTC: Allowed
    """
    auth = stage1_env["auth_service"]

    # 1. 20:49:59 UTC -> Outside blackout (Allowed)
    t_allowed1 = datetime(2026, 10, 21, 20, 49, 59, tzinfo=timezone.utc)
    ok1, reason1 = auth.validate_market_and_spread_conditions(
        symbol="EURUSD", now_utc=t_allowed1, bypass_quote_check=True
    )
    assert ok1
    assert reason1 is None

    # 2. 20:50:00 UTC -> Start of blackout (Blocked)
    t_blocked_start = datetime(2026, 10, 21, 20, 50, 0, tzinfo=timezone.utc)
    ok2, reason2 = auth.validate_market_and_spread_conditions(
        symbol="EURUSD", now_utc=t_blocked_start, bypass_quote_check=True
    )
    assert not ok2
    assert "DAILY ROLLOVER BLACKOUT" in reason2

    # 3. 21:15:00 UTC -> Mid-blackout (Blocked)
    t_blocked_mid = datetime(2026, 10, 21, 21, 15, 0, tzinfo=timezone.utc)
    ok3, reason3 = auth.validate_market_and_spread_conditions(
        symbol="EURUSD", now_utc=t_blocked_mid, bypass_quote_check=True
    )
    assert not ok3
    assert "DAILY ROLLOVER BLACKOUT" in reason3

    # 4. 21:30:00 UTC -> End boundary of blackout (Blocked)
    t_blocked_end = datetime(2026, 10, 21, 21, 30, 0, tzinfo=timezone.utc)
    ok4, reason4 = auth.validate_market_and_spread_conditions(
        symbol="EURUSD", now_utc=t_blocked_end, bypass_quote_check=True
    )
    assert not ok4
    assert "DAILY ROLLOVER BLACKOUT" in reason4

    # 5. 21:30:01 UTC -> Outside blackout (Allowed)
    t_allowed2 = datetime(2026, 10, 21, 21, 30, 1, tzinfo=timezone.utc)
    ok5, reason5 = auth.validate_market_and_spread_conditions(
        symbol="EURUSD", now_utc=t_allowed2, bypass_quote_check=True
    )
    assert ok5
    assert reason5 is None


def test_quote_freshness_fails_closed_on_stale_or_missing_quotes(stage1_env):
    """
    Orders are strictly rejected if broker quotes are missing or >30 seconds stale.
    """
    auth = stage1_env["auth_service"]
    t_eval = datetime(2026, 10, 21, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Missing quote (None) -> Rejected
    ok_none, reason_none = auth.validate_market_and_spread_conditions(
        symbol="EURUSD", quote_resp=None, now_utc=t_eval
    )
    assert not ok_none
    assert "QUOTE UNAVAILABLE" in reason_none

    # 2. Stale quote (35 seconds old > 30s threshold) -> Rejected
    stale_time = t_eval - timedelta(seconds=35)
    stale_quote = MarketQuote(
        symbol="EURUSD",
        providerId="oanda",
        providerName="OANDA",
        bid=1.1000,
        ask=1.1001,
        lastPrice=1.10005,
        spread=0.1,
        timestamp=stale_time,
        bidAsk=BidAsk(bid=1.1000, ask=1.1001, spread=0.00010),
    )
    ok_stale, reason_stale = auth.validate_market_and_spread_conditions(
        symbol="EURUSD",
        quote_resp=MarketQuoteResponse(quote=stale_quote),
        now_utc=t_eval,
    )
    assert not ok_stale
    assert "STALE QUOTE" in reason_stale

    # 3. Fresh quote (5 seconds old) -> Allowed
    fresh_time = t_eval - timedelta(seconds=5)
    fresh_quote = MarketQuote(
        symbol="EURUSD",
        providerId="oanda",
        providerName="OANDA",
        bid=1.1000,
        ask=1.1001,
        lastPrice=1.10005,
        spread=0.1,
        timestamp=fresh_time,
        bidAsk=BidAsk(bid=1.1000, ask=1.1001, spread=0.00010),
    )
    ok_fresh, reason_fresh = auth.validate_market_and_spread_conditions(
        symbol="EURUSD",
        quote_resp=MarketQuoteResponse(quote=fresh_quote),
        now_utc=t_eval,
    )
    assert ok_fresh
    assert reason_fresh is None


def test_gold_spread_cap_enforced_in_cash_usd(stage1_env):
    """
    Gold maximum allowable spread is $0.80 USD cash.
    Explicitly tests that Gold price differences are NOT treated as pips.
    """
    auth = stage1_env["auth_service"]
    t_eval = datetime(2026, 10, 21, 14, 0, 0, tzinfo=timezone.utc)

    def _gold_quote(spread_usd: float):
        return MarketQuoteResponse(
            quote=MarketQuote(
                symbol="XAUUSD",
                providerId="oanda",
                providerName="OANDA",
                bid=2000.0,
                ask=2000.0 + spread_usd,
                lastPrice=2000.0,
                spread=spread_usd,
                timestamp=t_eval,
                bidAsk=BidAsk(bid=2000.0, ask=2000.0 + spread_usd, spread=spread_usd),
            )
        )

    # $0.50 spread -> Allowed (<= $0.80)
    ok1, reason1 = auth.validate_market_and_spread_conditions(
        symbol="XAUUSD", quote_resp=_gold_quote(0.50), now_utc=t_eval
    )
    assert ok1
    assert reason1 is None

    # $0.80 spread -> Allowed (boundary)
    ok2, reason2 = auth.validate_market_and_spread_conditions(
        symbol="XAUUSD", quote_resp=_gold_quote(0.80), now_utc=t_eval
    )
    assert ok2

    # $0.85 spread -> Rejected (exceeds $0.80 USD cap)
    ok3, reason3 = auth.validate_market_and_spread_conditions(
        symbol="XAUUSD", quote_resp=_gold_quote(0.85), now_utc=t_eval
    )
    assert not ok3
    assert "SPREAD SPIKE" in reason3
    assert "$0.85 USD" in reason3
    assert "$0.80 USD cap" in reason3


def test_forex_spread_caps_majors_and_crosses(stage1_env):
    """
    Forex Major Cap: 2.0 pips (0.00020 EURUSD / 0.020 USDJPY).
    Forex Cross Cap: 3.5 pips (0.035 GBPJPY / 0.00035 EURGBP).
    """
    auth = stage1_env["auth_service"]
    t_eval = datetime(2026, 10, 21, 14, 0, 0, tzinfo=timezone.utc)

    # 1. EURUSD Major (Cap: 2.0 pips)
    def _eur_quote(pips: float):
        spread_val = pips * 0.00010
        return MarketQuoteResponse(
            quote=MarketQuote(
                symbol="EURUSD",
                providerId="oanda",
                providerName="OANDA",
                bid=1.1000,
                ask=1.1000 + spread_val,
                lastPrice=1.1000,
                spread=pips,
                timestamp=t_eval,
                bidAsk=BidAsk(bid=1.1000, ask=1.1000 + spread_val, spread=spread_val),
            )
        )

    ok_eur1, _ = auth.validate_market_and_spread_conditions("EURUSD", _eur_quote(1.8), now_utc=t_eval)
    assert ok_eur1  # 1.8 <= 2.0

    ok_eur2, reason_eur2 = auth.validate_market_and_spread_conditions("EURUSD", _eur_quote(2.3), now_utc=t_eval)
    assert not ok_eur2  # 2.3 > 2.0
    assert "SPREAD SPIKE" in reason_eur2
    assert "2.0 pips cap" in reason_eur2

    # 2. GBPJPY Cross (Cap: 3.5 pips)
    def _gbpjpy_quote(pips: float):
        spread_val = pips * 0.010
        return MarketQuoteResponse(
            quote=MarketQuote(
                symbol="GBPJPY",
                providerId="oanda",
                providerName="OANDA",
                bid=190.0,
                ask=190.0 + spread_val,
                lastPrice=190.0,
                spread=pips,
                timestamp=t_eval,
                bidAsk=BidAsk(bid=190.0, ask=190.0 + spread_val, spread=spread_val),
            )
        )

    ok_gj1, _ = auth.validate_market_and_spread_conditions("GBPJPY", _gbpjpy_quote(3.2), now_utc=t_eval)
    assert ok_gj1  # 3.2 <= 3.5

    ok_gj2, reason_gj2 = auth.validate_market_and_spread_conditions("GBPJPY", _gbpjpy_quote(3.8), now_utc=t_eval)
    assert not ok_gj2  # 3.8 > 3.5
    assert "SPREAD SPIKE" in reason_gj2
    assert "3.5 pips cap" in reason_gj2
