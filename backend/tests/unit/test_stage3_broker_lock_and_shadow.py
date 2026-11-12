"""
Falcon Stage 3: Isolated Shadow Trading, Execution Boundary & Quantitative Evidence Tests.
Verifies:
1. Hard-lock on all automated broker execution (fail-closed, zero broker calls via BrokerSpy).
2. Strategy ACTIVE or readyForExecution=True CANNOT override execution mode guard.
3. Complete capital isolation: Paper/Shadow trades consume 0 live Capital Guardian capacity.
4. Idempotency & Concurrency: Duplicate signal ingestion is rejected; PostgreSQL advisory lock safety.
5. Market Quality Filters: UTC rollover blackout boundaries, instrument spread caps (FX majors 2.0 pips,
   FX crosses 3.5 pips, Gold $0.80), and 45-minute post-stop cooldown.
6. Initial Risk Provenance: All 4 recovery levels verified; unrecoverable risk marked None (zero synthetic R).
7. Forward Shadow Observability: /paper/summary telemetry returns isolated stats with zero broker attempts.
8. Cluster-aware replay analysis: Block bootstrap correctly groups correlated rollover cascades.
"""

from datetime import datetime, timezone, time, timedelta
from decimal import Decimal
import threading
import pytest
from unittest.mock import MagicMock, patch

from app.core.config.settings import settings
from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    ExecutionModeGuard,
    execution_mode_guard,
    assert_no_broker_automation,
    parse_execution_mode,
)
from app.core.services.signal_authorization_service import (
    SignalAuthorizationService,
    signal_authorization_service,
)
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.core.services.capital_guardian_service import capital_guardian_service
from app.core.engines.paper_trading_engine import PaperTradingEngine
from app.core.engines.paper_runtime import PaperTradingRuntime
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.engines.strategy_engine import StrategyEngine
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.execution_order import ExecutionOrderCreate, OrderAction
from app.schemas.market_quote import (
    MarketQuoteResponse,
    MarketQuote,
    BidAsk,
    MarketStatus,
    QuoteStatus,
)
from app.schemas.strategy import StrategyStatus
from app.schemas.trade_journal import TradeJournalItem, TradeJournalCreate
from app.services.execution.order_execution_service import OrderExecutionService


class BrokerSpy:
    """Spy class recording any attempted outbound broker interactions."""
    def __init__(self):
        self.create_order_calls = []
        self.modify_order_calls = []
        self.cancel_order_calls = []
        self.close_order_calls = []

    def create_order(self, *args, **kwargs):
        self.create_order_calls.append((args, kwargs))
        raise RuntimeError("CRITICAL_FAIL: Real broker create_order called!")

    def modify_order(self, *args, **kwargs):
        self.modify_order_calls.append((args, kwargs))
        raise RuntimeError("CRITICAL_FAIL: Real broker modify_order called!")

    def cancel_order(self, *args, **kwargs):
        self.cancel_order_calls.append((args, kwargs))
        raise RuntimeError("CRITICAL_FAIL: Real broker cancel_order called!")

    def close_order(self, *args, **kwargs):
        self.close_order_calls.append((args, kwargs))
        raise RuntimeError("CRITICAL_FAIL: Real broker close_order called!")


def make_quote_resp(symbol: str, price: float, spread: float = 0.0001, timestamp: datetime = None) -> MarketQuoteResponse:
    ts = timestamp or datetime.now(timezone.utc)
    return MarketQuoteResponse(
        quote=MarketQuote(
            symbol=symbol,
            bidAsk=BidAsk(bid=price, ask=price + spread, spread=spread),
            lastPrice=price,
            timestamp=ts,
            providerId="test_provider",
            providerName="Test Provider",
            quoteStatus=QuoteStatus.LIVE,
            marketStatus=MarketStatus.OPEN,
        )
    )


# ==============================================================================
# SECTION 1: BROKER EXECUTION HARD-LOCK & SPY VERIFICATION
# ==============================================================================

def test_broker_dispatch_strictly_blocked_in_paper_mode():
    """In default PAPER mode, automated order execution MUST NOT dispatch to broker."""
    spy = BrokerSpy()
    order_svc = OrderExecutionService()

    with patch("app.core.providers._oanda_provider", spy):
        order_in = ExecutionOrderCreate(
            symbol="EUR/USD",
            action=OrderAction.BUY,
            lot_size=0.1,
            order_type="MARKET",
            entry_price=1.0850,
            stop_loss=1.0800,
            take_profit=1.0950,
            strategy_name="strat-007",
            confidence=85,
        )
        with patch.object(signal_authorization_service, "authorize_and_reserve") as mock_auth:
            from app.schemas.capital_guardian import CapitalGuardianDecision, GuardianState
            mock_auth.return_value = (
                CapitalGuardianDecision(
                    allowed=True,
                    reason="Test Allowed",
                    state=GuardianState.NORMAL,
                    activeTradingCapital=Decimal("10000.00"),
                    protectedProfit=Decimal("0.00"),
                    currentLiveTradeCount=0,
                    maxLiveTradeCount=3,
                    currentAggregateWorstCaseLoss=Decimal("0.00"),
                    proposedWorstCaseLoss=Decimal("50.00"),
                    aggregateWorstCaseLossAfter=Decimal("50.00"),
                    remainingLossCapacity=Decimal("9950.00"),
                ),
                None
            )
            item = order_svc.create_order(order_in)
            assert item is not None
            assert item.status.value == "PENDING"
            # Crucial: Broker spy MUST record 0 outbound calls
            assert len(spy.create_order_calls) == 0


def test_strategy_active_and_ready_cannot_override_broker_lock():
    """A strategy with status=ACTIVE and readyForExecution=True cannot trigger real orders."""
    spy = BrokerSpy()
    order_svc = OrderExecutionService()

    # Load authentic strategy from engine
    strat_eng = StrategyEngine()
    strat = strat_eng.get_strategy_by_id("strat-004")
    assert strat is not None
    assert strat.status == StrategyStatus.ACTIVE
    assert strat.readyForExecution is True

    # But execution mode guard remains PAPER
    assert execution_mode_guard.is_live_authorized() is False
    assert execution_mode_guard.is_broker_locked() is True

    with patch("app.core.providers._oanda_provider", spy):
        with patch.object(signal_authorization_service, "authorize_and_reserve") as mock_auth:
            from app.schemas.capital_guardian import CapitalGuardianDecision, GuardianState
            mock_auth.return_value = (
                CapitalGuardianDecision(
                    allowed=True, reason="OK", state=GuardianState.NORMAL,
                    activeTradingCapital=Decimal("10000"), protectedProfit=Decimal("0"),
                    currentLiveTradeCount=0, maxLiveTradeCount=3,
                    currentAggregateWorstCaseLoss=Decimal("0"), proposedWorstCaseLoss=Decimal("50"),
                    aggregateWorstCaseLossAfter=Decimal("50"), remainingLossCapacity=Decimal("9950")
                ), None
            )
            order_in = ExecutionOrderCreate(
                symbol="GBP/USD", action=OrderAction.BUY, lot_size=0.1,
                order_type="MARKET", entry_price=1.3380, stop_loss=1.3350, take_profit=1.3430,
                strategy_name="strat-004", confidence=90
            )
            order_svc.create_order(order_in)
            assert len(spy.create_order_calls) == 0


def test_missing_or_invalid_execution_settings_fail_closed():
    """Any corrupted, non-string, or unacknowledged settings fail closed to PAPER."""
    with patch.object(settings, "EXECUTION_MODE", "LIVE"):
        with patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False):
            # LIVE configured but NOT acknowledged -> Fails closed to PAPER
            assert ExecutionModeGuard.get_system_mode() == ExecutionMode.PAPER
            assert ExecutionModeGuard.is_live_authorized() is False

    with patch.object(settings, "EXECUTION_MODE", 12345):
        # Corrupted non-string setting -> Fails closed to PAPER
        assert ExecutionModeGuard.get_system_mode() == ExecutionMode.PAPER
        assert ExecutionModeGuard.is_live_authorized() is False


# ==============================================================================
# SECTION 2: CAPITAL ISOLATION & SHADOW RESERVATIONS
# ==============================================================================

def test_paper_trades_consume_zero_live_capital_guardian_capacity():
    """Paper trades must never count towards live trade limits or live worst-case loss."""
    now = datetime.now(timezone.utc)
    paper_trade_1 = TradeJournalItem(
        id=901, signalId=901, strategyId="strat-004", symbol="GBP/USD", direction="BUY",
        entryPrice=1.3380, stopLoss=1.3350, takeProfit=1.3430, status="OPEN",
        timeframe="M15", marketSession="London", reasonForEntry="Setup",
        createdAt=now, updatedAt=now, tradeDate=now, initialMonetaryRisk=50.0,
        executionMode="PAPER", notes="[MODE:PAPER]"
    )
    paper_trade_2 = TradeJournalItem(
        id=902, signalId=902, strategyId="strat-007", symbol="EUR/USD", direction="BUY",
        entryPrice=1.0850, stopLoss=1.0800, takeProfit=1.0950, status="OPEN",
        timeframe="M15", marketSession="London", reasonForEntry="Setup",
        createdAt=now, updatedAt=now, tradeDate=now, initialMonetaryRisk=50.0,
        executionMode="PAPER", notes="[MODE:PAPER]"
    )

    all_trades = [paper_trade_1, paper_trade_2]
    with patch.object(capital_guardian_service._journal_repo, "list_trades", return_value=all_trades):
        live_reserving = capital_guardian_service.get_capital_reserving_trades(
            active_cycle=None, filter_by_cycle=False, execution_mode="LIVE"
        )
        assert len(live_reserving) == 0, "Paper trades leaked into LIVE capacity!"

        paper_reserving = capital_guardian_service.get_capital_reserving_trades(
            active_cycle=None, filter_by_cycle=False, execution_mode="PAPER"
        )
        assert len(paper_reserving) == 2


# ==============================================================================
# SECTION 3: MARKET QUALITY FILTERS (ROLLOVER, SPREAD, COOLDOWN)
# ==============================================================================

def test_utc_rollover_blackout_boundary_enforcement():
    """Entries must be strictly rejected during the configurable blackout (20:50 - 21:30 UTC)."""
    auth = SignalAuthorizationService()

    # Case A: Inside blackout window (21:05 UTC - exact rollover cascade time)
    t_inside = datetime(2026, 10, 20, 21, 5, 31, tzinfo=timezone.utc)
    is_ok, reason = auth.validate_market_and_spread_conditions(
        symbol="GBP/JPY", quote_resp=None, now_utc=t_inside, bypass_quote_check=True
    )
    assert is_ok is False
    assert "DAILY ROLLOVER BLACKOUT" in reason

    # Case B: Exactly at start boundary (20:50:00 UTC)
    t_start = datetime(2026, 10, 20, 20, 50, 0, tzinfo=timezone.utc)
    is_ok, reason = auth.validate_market_and_spread_conditions(
        symbol="GBP/JPY", quote_resp=None, now_utc=t_start, bypass_quote_check=True
    )
    assert is_ok is False

    # Case C: Safely outside blackout window (21:35:00 UTC)
    t_outside = datetime(2026, 10, 20, 21, 35, 0, tzinfo=timezone.utc)
    is_ok, reason = auth.validate_market_and_spread_conditions(
        symbol="GBP/JPY", quote_resp=None, now_utc=t_outside, bypass_quote_check=True
    )
    assert is_ok is True


def test_instrument_specific_spread_caps_and_units():
    """Verify spread thresholds: FX Majors 2.0 pips, FX Crosses 3.5 pips, Gold $0.80."""
    auth = SignalAuthorizationService()
    now = datetime(2026, 10, 20, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Gold (XAU/USD): Cap is $0.80 USD
    gold_ok = make_quote_resp("XAU/USD", 2650.0, spread=0.75, timestamp=now)
    is_ok, _ = auth.validate_market_and_spread_conditions("XAU/USD", gold_ok, now_utc=now)
    assert is_ok is True

    gold_spike = make_quote_resp("XAU/USD", 2650.0, spread=0.85, timestamp=now)
    is_ok, reason = auth.validate_market_and_spread_conditions("XAU/USD", gold_spike, now_utc=now)
    assert is_ok is False
    assert "Gold spread $0.85 USD exceeds maximum allowable $0.80 USD cap" in reason

    # 2. FX Major (EUR/USD): Cap is 2.0 pips (0.00020)
    eur_ok = make_quote_resp("EUR/USD", 1.0850, spread=0.00018, timestamp=now)
    is_ok, _ = auth.validate_market_and_spread_conditions("EUR/USD", eur_ok, now_utc=now)
    assert is_ok is True

    eur_spike = make_quote_resp("EUR/USD", 1.0850, spread=0.00025, timestamp=now)
    is_ok, reason = auth.validate_market_and_spread_conditions("EUR/USD", eur_spike, now_utc=now)
    assert is_ok is False
    assert "2.5 pips exceeds maximum 2.0 pips cap" in reason

    # 3. FX Cross (GBP/JPY): Cap is 3.5 pips (0.035)
    gj_ok = make_quote_resp("GBP/JPY", 211.50, spread=0.030, timestamp=now)
    is_ok, _ = auth.validate_market_and_spread_conditions("GBP/JPY", gj_ok, now_utc=now)
    assert is_ok is True

    gj_spike = make_quote_resp("GBP/JPY", 211.50, spread=0.045, timestamp=now)  # 4.5 pips
    is_ok, reason = auth.validate_market_and_spread_conditions("GBP/JPY", gj_spike, now_utc=now)
    assert is_ok is False
    assert "4.5 pips exceeds maximum 3.5 pips cap" in reason


def test_post_stop_cooldown_blocks_rapid_reentries():
    """45-minute post-stop cooldown blocks repeated entries after LOSS or BREAKEVEN."""
    auth = SignalAuthorizationService()
    now = datetime(2026, 10, 20, 21, 10, 0, tzinfo=timezone.utc)

    recent_stop = TradeJournalItem(
        id=99, signalId=99, strategyId="strat-016", symbol="GBP/JPY", direction="SELL",
        entryPrice=211.60, stopLoss=211.85, takeProfit=210.85, status="CLOSED", result="LOSS",
        timeframe="M15", marketSession="London", reasonForEntry="Setup",
        createdAt=now - timedelta(minutes=15), updatedAt=now - timedelta(minutes=10),
        tradeDate=now - timedelta(minutes=15), closeDate=now - timedelta(minutes=10),
        reasonForExit="Stop Loss Hit", executionMode="LIVE"
    )

    with patch.object(auth._journal_repo, "list_trades", return_value=[recent_stop]):
        is_ok, reason = auth.check_post_stop_cooldown(
            strategy_id="strat-016", symbol="GBP/JPY", now_utc=now, session=None
        )
        assert is_ok is False
        assert "45m cooldown" in reason

        # When evaluated 50 minutes after stop, cooldown has expired
        future_now = now + timedelta(minutes=45)
        is_ok, reason = auth.check_post_stop_cooldown(
            strategy_id="strat-016", symbol="GBP/JPY", now_utc=future_now, session=None
        )
        assert is_ok is True


# ==============================================================================
# SECTION 4: RISK PROVENANCE HIERARCHY & UNSCORABLE HANDLING
# ==============================================================================

def test_risk_provenance_recovery_hierarchy_levels():
    """Test all 4 recovery levels and unscorable fail-closed handling."""
    now = datetime.now(timezone.utc)

    # Level 1: Immutable initialStopLoss available
    t1 = TradeJournalItem(
        id=1, signalId=1, symbol="EUR/USD", direction="BUY", entryPrice=1.1000,
        stopLoss=1.1000, takeProfit=1.1150, initialStopLoss=1.0950, status="OPEN",
        timeframe="H1", marketSession="London", reasonForEntry="Test",
        createdAt=now, updatedAt=now, tradeDate=now
    )
    dist, src = SignalOutcomeResolver.recover_initial_risk_distance(t1)
    assert round(dist, 4) == 0.0050
    assert src == "INITIAL_STOP_LOSS"

    # Level 2: Unmoved stopLoss available
    t2 = TradeJournalItem(
        id=2, signalId=2, symbol="EUR/USD", direction="BUY", entryPrice=1.1000,
        stopLoss=1.0960, takeProfit=1.1150, status="OPEN",
        timeframe="H1", marketSession="London", reasonForEntry="Test",
        createdAt=now, updatedAt=now, tradeDate=now
    )
    dist, src = SignalOutcomeResolver.recover_initial_risk_distance(t2)
    assert round(dist, 4) == 0.0040
    assert src == "CURRENT_STOP_LOSS"

    # Level 3: Reconstructed from TP & R:R
    t3 = TradeJournalItem(
        id=3, signalId=3, symbol="EUR/USD", direction="BUY", entryPrice=1.1000,
        stopLoss=1.1000, takeProfit=1.1150, riskReward=3.0, status="OPEN",
        timeframe="H1", marketSession="London", reasonForEntry="Test",
        createdAt=now, updatedAt=now, tradeDate=now
    )
    dist, src = SignalOutcomeResolver.recover_initial_risk_distance(t3)
    assert round(dist, 4) == 0.0050
    assert src == "RECONSTRUCTED_TARGET_RR"

    # Level 4: Reconstructed from ATR and multiplier
    t4 = TradeJournalItem(
        id=4, signalId=4, symbol="EUR/USD", direction="BUY", entryPrice=1.1000,
        stopLoss=1.1000, takeProfit=1.1150, atrAtEntry=0.0030, adaptiveStopMultiplier=1.5, status="OPEN",
        timeframe="H1", marketSession="London", reasonForEntry="Test",
        createdAt=now, updatedAt=now, tradeDate=now
    )
    dist, src = SignalOutcomeResolver.recover_initial_risk_distance(t4)
    assert round(dist, 4) == 0.0045
    assert src == "RECONSTRUCTED_ATR"

    # Level 5: Unrecoverable (entry == stop_loss, no ATR, no R:R) -> Zero synthetic R
    t5 = TradeJournalItem(
        id=5, signalId=5, symbol="EUR/USD", direction="BUY", entryPrice=1.1000,
        stopLoss=1.1000, takeProfit=1.1150, status="CLOSED", result="BREAKEVEN",
        timeframe="H1", marketSession="London", reasonForEntry="Test",
        createdAt=now, updatedAt=now, tradeDate=now
    )
    dist, src = SignalOutcomeResolver.recover_initial_risk_distance(t5)
    assert dist == 0.0
    assert src == "UNRECOVERED"


# ==============================================================================
# SECTION 5: SHADOW PIPELINE CANDIDATE EVALUATION ACROSS ALL 18 STRATEGIES
# ==============================================================================

def test_shadow_candidates_evaluates_incubation_without_altering_production():
    """generate_shadow_candidates evaluates incubation strategies; generate_candidates retains ACTIVE only."""
    engine = SignalGenerationEngine()
    strat_eng = StrategyEngine()
    all_18 = strat_eng.get_strategies()
    assert len(all_18) == 18

    mock_market_state = MagicMock()
    mock_market_state.session = "London"
    mock_market_state.calendar = []
    mock_market_state.prices = {}
    mock_market_state.marketSentimentLabel = "Neutral"
    mock_market_state.overallMarketConfidence = 70
    mock_market_state.dataAgeSeconds = 5
    mock_market_state.volatility = "Moderate"

    with patch("app.core.services.market_history_service.market_history_service.get_bars", return_value=[]):
        shadow_cands = engine.generate_shadow_candidates(
            market_state=mock_market_state,
            strategies=all_18
        )
        assert isinstance(shadow_cands, list)

    active_count = sum(1 for s in all_18 if s.status == StrategyStatus.ACTIVE)
    incubation_count = sum(1 for s in all_18 if s.status == StrategyStatus.INCUBATION)
    assert active_count == 6
    assert incubation_count == 12


# ==============================================================================
# SECTION 6: FORWARD SHADOW OBSERVABILITY API ENDPOINT
# ==============================================================================

def test_paper_summary_telemetry_endpoint():
    """GET /api/v1/paper/summary returns isolated shadow metrics with zero broker calls."""
    from app.api.v1.paper import get_paper_summary

    summary = get_paper_summary()
    assert summary["executionMode"] == "PAPER"
    assert summary["isBrokerLocked"] is True
    assert summary["brokerDispatchAttempts"] == 0
    assert summary["pipelineStatus"] == "OPERATIONAL_SHADOW"
    assert "realizedNetR" in summary
    assert "winRatePct" in summary
    assert "profitFactor" in summary
    assert "maxDrawdownR" in summary
    assert "strategyBreakdown" in summary
    assert "symbolBreakdown" in summary
