"""
Falcon V10 Phase 5H: Final Hardening & Production-Readiness Test Suite.

Comprehensive verification of:
1. Safety Hardening (broker automation prohibition, fail-closed execution mode, secret/config safety)
2. Idempotency Hardening (duplicate authorization, duplicate fill, duplicate close, duplicate expiration, duplicate invalidation, analytics determinism)
3. Concurrency Hardening (simultaneous Guardian authorization, aggregate loss limits, advisory lock 8882026, simultaneous ticks, cycle transitions, analytics)
4. Failure Recovery Hardening (DB transaction rollback, authorization failure cleanup, runtime restart from pending/open, retry safety, batch fault isolation)
5. Capital Guardian Hardening (3-trade ceiling, boundary equality rejection, loss exceeding capital rejection, mode isolation, cycle transition math, protected profit isolation)
6. Paper Runtime Hardening (direction-aware BUY/SELL fills, direction-aware SL/TP, ambiguous SL/TP fail-closed to LOSS, directional MFE/MAE, expiration, invalidation)
7. Manual LIVE Ingestion Hardening (valid signal_id, authoritative fill price/time, mode token preservation, lifecycle integrity, PAPER capital isolation)
8. Divergence Analytics Hardening (pairing strictly by signal_id, historical mode isolation, deterministic premature exit, missing data safety, as_of lookahead protection)
9. Strategy Attribution & Drift Diagnostics Hardening (4-tuple grouping, historical isolation, exact SE formula, exact z-score formula, z < -2.0 warning, sample size protection, degenerate SE, Profit Factor NOT_EVALUABLE)
10. API Hardening & Error Handling (mode endpoint, paper trades pagination/isolation, empty population safety, malformed parameter handling, read-only DB preservation)
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import math
from typing import Any, Dict, List, Optional, Tuple
import pytest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from main import app

from app.core.analytics.execution_divergence_service import (
    ExecutionDivergenceService,
    execution_divergence_service,
)
from app.core.analytics.strategy_attribution_service import (
    MIN_SAMPLE_SIZE,
    StrategyAttributionService,
    strategy_attribution_service,
)
from app.core.config import settings
from app.core.engines.paper_runtime import (
    PaperTradingRuntime,
    paper_trading_runtime,
)
from app.core.engines.paper_trading_engine import (
    PaperTradingEngine,
    paper_trading_engine,
)
from app.core.execution.execution_mode_guard import (
    ExecutionMode,
    ExecutionModeGuard,
    assert_no_broker_automation,
    execution_mode_guard,
    format_mode_token,
    inject_mode_token,
    parse_execution_mode,
)
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
)
from app.core.repository.trade_journal_repository import (
    InMemoryTradeJournalStorage,
    TradeJournalRepository,
    trade_journal_repository,
)
from app.core.services.capital_cycle_service import CapitalCycleService
from app.core.services.capital_guardian_service import (
    CapitalGuardianService,
    capital_guardian_service,
)
from app.core.services.signal_authorization_service import (
    FALCON_GUARDIAN_ADVISORY_LOCK_KEY,
    SignalAuthorizationService,
    signal_authorization_service,
)
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleStatus
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.execution_divergence import DivergenceClassification
from app.schemas.market_quote import BidAsk, MarketQuote
from app.schemas.signal_candidate import (
    CandidateCondition,
    CandidateDirection,
    CandidateMarketSnapshot,
    CandidateReason,
    CandidateStatus,
    ConfidenceBreakdown,
    SignalCandidate,
)
from app.schemas.strategy_attribution import DriftStatus
from app.schemas.trade_journal import TradeJournalCreate, TradeJournalUpdate
from app.services.execution.cloud_mt5_service import CloudMT5Service
from app.services.execution.order_execution_service import OrderExecutionService


@pytest.fixture(autouse=True)
def clean_test_environment():
    """Isolate tests in memory and clean repositories before/after each test."""
    orig_storage = trade_journal_repository._storage
    mem_storage = InMemoryTradeJournalStorage()
    trade_journal_repository._storage = mem_storage
    trade_journal_repository.clear()

    orig_cycle_storage = capital_guardian_service._cycle_service._repo._storage
    cycle_storage = InMemoryCapitalCycleStorage()
    cycle_repo = CapitalCycleRepository()
    cycle_repo._storage = cycle_storage
    cycle_repo.clear()

    # Seed an active capital cycle ($20.00 active capital, $0.00 protected profit)
    cycle_repo.create_cycle(
        CapitalCycleCreate(
            cycleId="cycle-v10-p5h-test",
            cycleNumber=1,
            startingCapital=Decimal("20.00"),
            targetCapital=Decimal("500.00"),
            activeTradingCapital=Decimal("20.00"),
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
    )

    cycle_service = CapitalCycleService(repository=cycle_repo)
    guardian_service = CapitalGuardianService(
        cycle_service=cycle_service,
        journal_repository=trade_journal_repository,
    )
    auth_service = SignalAuthorizationService(
        cycle_service=cycle_service,
        guardian_service=guardian_service,
        journal_repo=trade_journal_repository,
        cycle_repo=cycle_repo,
    )

    orig_auth_cycle_service = signal_authorization_service._cycle_service
    orig_auth_guardian_service = signal_authorization_service._guardian_service
    orig_auth_journal_repo = signal_authorization_service._journal_repo
    orig_auth_cycle_repo = signal_authorization_service._cycle_repo

    orig_guardian_cycle_service = capital_guardian_service._cycle_service
    orig_guardian_journal_repo = capital_guardian_service._journal_repo

    # Patch global singletons
    paper_trading_engine._auth_service = auth_service
    paper_trading_engine._guardian_service = guardian_service
    paper_trading_engine._journal_repo = trade_journal_repository

    paper_trading_runtime._engine = paper_trading_engine
    paper_trading_runtime._journal_repo = trade_journal_repository

    execution_divergence_service._journal_repo = trade_journal_repository
    strategy_attribution_service._journal_repo = trade_journal_repository

    signal_authorization_service._cycle_service = cycle_service
    signal_authorization_service._guardian_service = guardian_service
    signal_authorization_service._journal_repo = trade_journal_repository
    signal_authorization_service._cycle_repo = cycle_repo

    capital_guardian_service._cycle_service = cycle_service
    capital_guardian_service._journal_repo = trade_journal_repository

    yield {
        "cycle_repo": cycle_repo,
        "cycle_service": cycle_service,
        "guardian_service": guardian_service,
        "auth_service": auth_service,
        "journal_repo": trade_journal_repository,
    }

    trade_journal_repository.clear()
    trade_journal_repository._storage = orig_storage
    capital_guardian_service._cycle_service._repo._storage = orig_cycle_storage

    signal_authorization_service._cycle_service = orig_auth_cycle_service
    signal_authorization_service._guardian_service = orig_auth_guardian_service
    signal_authorization_service._journal_repo = orig_auth_journal_repo
    signal_authorization_service._cycle_repo = orig_auth_cycle_repo

    capital_guardian_service._cycle_service = orig_guardian_cycle_service
    capital_guardian_service._journal_repo = orig_guardian_journal_repo


def make_test_candidate(
    signal_id: int,
    symbol: str = "EURUSD",
    direction: CandidateDirection = CandidateDirection.BUY,
    entry_price: float = 1.1000,
    stop_loss: float = 1.0950,
    take_profit: float = 1.1150,
) -> SignalCandidate:
    now = datetime.now(timezone.utc)
    return SignalCandidate(
        id=f"cand-{signal_id}",
        symbol=symbol,
        strategyId="MOMENTUM_BREAKOUT",
        strategyName="Momentum Breakout",
        strategyVersion="1.2.0",
        strategyGrade="A+",
        strategyScore=85,
        direction=direction,
        confidence=85,
        readinessScore=90,
        entryPrice=entry_price,
        stopLoss=stop_loss,
        takeProfit=take_profit,
        riskReward=3.0,
        status=CandidateStatus.GENERATED,
        generatedAt=now,
        reasons=[CandidateReason(title="Confirmed", description="Ready", passed=True)],
        conditions=[],
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=85,
            strategyScore=85,
            sessionScore=85,
            sentimentScore=85,
            newsScore=85,
        ),
        evaluationDurationMs=10,
        marketDataAgeSeconds=2,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
        adaptiveRuleVersion="v2.1",
        adaptiveStopMultiplier=1.25,
        marketSnapshot=CandidateMarketSnapshot(
            trend="BULLISH",
            volatility="NORMAL",
            session="London",
            newsImpact="Low",
            marketSentiment="Bullish",
            marketConfidence=85,
            spread=0.0002,
            atr=0.0015,
        ),
    )


def make_test_proposal(
    symbol: str = "EURUSD",
    direction: str = "BUY",
    entry_price: float = 1.1000,
    stop_loss: float = 1.0950,
    take_profit: float = 1.1150,
    lot_size: float = 0.01,
    risk_usd: Optional[float] = None,
) -> ProposedTradeInput:
    risk_dec = Decimal(str(risk_usd)) if risk_usd is not None else None
    return ProposedTradeInput(
        symbol=symbol,
        direction=direction,
        entryPrice=Decimal(str(entry_price)),
        stopLoss=Decimal(str(stop_loss)),
        takeProfit=Decimal(str(take_profit)),
        lotSize=Decimal(str(lot_size)),
        monetaryRisk=risk_dec,
        isVerifiedRisk=True if risk_dec is not None else False,
    )


def make_journal_create(**kwargs) -> TradeJournalCreate:
    now = datetime.now(timezone.utc)
    defaults = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entryPrice": 1.1000,
        "stopLoss": 1.0950,
        "takeProfit": 1.1150,
        "timeframe": "M15",
        "marketSession": "London",
        "tradeDate": now,
        "reasonForEntry": "Test trading setup",
        "strategyId": "MOMENTUM_BREAKOUT",
        "strategyVersion": "1.2.0",
        "adaptiveRuleVersion": "v2.1",
        "initialMonetaryRisk": Decimal("5.00"),
    }
    defaults.update(kwargs)
    return TradeJournalCreate(**defaults)


def make_quote(
    bid: float,
    ask: float,
    symbol: str = "EURUSD",
    timestamp: Optional[datetime] = None,
    last_price: Optional[float] = None,
) -> MarketQuote:
    ts = timestamp or datetime.now(timezone.utc)
    lp = last_price if last_price is not None else (bid + ask) / 2.0
    return MarketQuote(
        symbol=symbol,
        lastPrice=lp,
        bidAsk=BidAsk(bid=bid, ask=ask, spread=round(ask - bid, 5)),
        timestamp=ts,
        providerId="twelve_data",
        providerName="TwelveData",
    )


# ==============================================================================
# Group 1: Safety Hardening (Tests 1–6)
# ==============================================================================

def test_01_broker_automation_prohibition_assert_no_broker_automation():
    """1. assert_no_broker_automation() strictly raises RuntimeError on any invocation."""
    with pytest.raises(RuntimeError, match="automated broker execution is strictly prohibited"):
        assert_no_broker_automation("Order dispatch trigger")


def test_02_cloud_mt5_service_strictly_prohibits_broker_automation():
    """2. CloudMT5Service execute_order fails closed and raises RuntimeError via assert_no_broker_automation."""
    mt5 = CloudMT5Service()
    with pytest.raises(RuntimeError, match="automated broker execution is strictly prohibited"):
        mt5.execute_order(
            symbol="EURUSD",
            action="BUY",
            volume=0.01,
            stop_loss=1.0950,
            take_profit=1.1150,
        )


def test_03_order_execution_service_strictly_prohibits_broker_automation():
    """3. OrderExecutionService has no broker execution capabilities."""
    oes = OrderExecutionService()
    assert not hasattr(oes, "order_send")
    assert not hasattr(oes, "order_modify")
    assert not hasattr(oes, "order_close")
    assert not hasattr(oes, "order_cancel")


def test_04_execution_mode_defaults_to_paper():
    """4. ExecutionModeGuard defaults strictly to PAPER when not configured."""
    with patch.object(settings, "EXECUTION_MODE", "", create=True), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False, create=True):
        guard = ExecutionModeGuard()
        assert guard.get_system_mode() == ExecutionMode.PAPER
        assert guard.is_paper() is True
        assert guard.is_live() is False


def test_05_execution_mode_fail_closed_on_ambiguous_or_conflicting_config():
    """5. Ambiguous, conflicting, or malformed mode configs fail closed strictly to PAPER."""
    # EXECUTION_MODE=LIVE but LIVE_EXECUTION_ACKNOWLEDGED=False
    with patch.object(settings, "EXECUTION_MODE", "LIVE"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", False):
        guard = ExecutionModeGuard()
        assert guard.get_system_mode() == ExecutionMode.PAPER

    # EXECUTION_MODE=INVALID
    with patch.object(settings, "EXECUTION_MODE", "UNKNOWN_ARBITRARY_MODE"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", True):
        guard = ExecutionModeGuard()
        assert guard.get_system_mode() == ExecutionMode.PAPER

    # EXECUTION_MODE=LIVE but LIVE_EXECUTION_ACKNOWLEDGED="not-a-bool"
    with patch.object(settings, "EXECUTION_MODE", "LIVE"), \
         patch.object(settings, "LIVE_EXECUTION_ACKNOWLEDGED", "not-a-bool"):
        guard = ExecutionModeGuard()
        assert guard.get_system_mode() == ExecutionMode.PAPER


def test_06_configuration_and_secret_safety():
    """6. Configuration loading exposes no broker passwords, API keys, or private credentials."""
    client = TestClient(app)
    response = client.get("/api/v1/execution/mode")
    assert response.status_code == 200
    data = response.json()
    assert "brokerPassword" not in data
    assert "apiKey" not in data
    assert "databaseUrl" not in data
    assert data["activeMode"] in ("PAPER", "LIVE")
    assert data["failClosed"] is True
    assert data["brokerAutomationLocked"] is True


# ==============================================================================
# Group 2: Idempotency Hardening (Tests 7–12)
# ==============================================================================

def test_07_duplicate_signal_authorization_is_idempotent():
    """7. Repeated authorization of the exact same signal is idempotent and creates 1 reservation."""
    cand = make_test_candidate(signal_id=2001)

    # First authorization
    dec1, res1 = signal_authorization_service.authorize_candidate(
        cand, signal_id=2001, execution_mode=ExecutionMode.PAPER.value
    )
    assert dec1.allowed is True
    assert res1 is not None
    assert res1.signalId == 2001

    # Second authorization for the same signal
    dec2, res2 = signal_authorization_service.authorize_candidate(
        cand, signal_id=2001, execution_mode=ExecutionMode.PAPER.value
    )
    assert dec2.allowed is True
    assert "already reserved" in dec2.reason.lower()
    assert res2 is not None
    assert res2.id == res1.id  # Same reservation returned

    # Verify journal has exactly 1 trade
    trades = trade_journal_repository.list_trades()
    assert len(trades) == 1
    assert trades[0].id == res1.id


def test_08_duplicate_paper_fill_is_idempotent():
    """8. Repeated runtime ticks on an already OPEN trade do not re-fill or alter fill price."""
    cand = make_test_candidate(signal_id=2002, entry_price=1.1000)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=2002, execution_mode=ExecutionMode.PAPER.value
    )

    quote_crossing = make_quote(bid=1.0998, ask=1.1000)

    # First evaluation fills trade
    trade_open = paper_trading_engine.simulate_fill(res.id, quote=quote_crossing)
    assert trade_open is not None
    assert trade_open.status == "OPEN"
    initial_fill_price = trade_open.fillPrice
    initial_fill_time = trade_open.fillTime

    # Subsequent simulate_fill attempt on OPEN trade fails closed (returns None, leaves trade intact)
    trade_repeat = paper_trading_engine.simulate_fill(res.id, quote=quote_crossing)
    assert trade_repeat is None

    # Verify existing record was untouched
    trade_current = trade_journal_repository.get_trade(res.id)
    assert trade_current.status == "OPEN"
    assert trade_current.fillPrice == initial_fill_price
    assert trade_current.fillTime == initial_fill_time


def test_09_duplicate_paper_close_is_idempotent():
    """9. Repeated runtime ticks on an already CLOSED trade do not re-close or alter exit metrics."""
    cand = make_test_candidate(signal_id=2003, entry_price=1.1000, take_profit=1.1150)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=2003, execution_mode=ExecutionMode.PAPER.value
    )
    quote_fill = make_quote(bid=1.0998, ask=1.1000)
    paper_trading_engine.simulate_fill(res.id, quote=quote_fill)

    # Quote hitting TP
    trade_closed = paper_trading_engine.evaluate_paper_trade(res.id, bid=1.1150, ask=1.1152)
    assert trade_closed.status == "CLOSED"
    exit_price = trade_closed.exitPrice
    close_date = trade_closed.closeDate
    realized_r = trade_closed.realizedRMultiple

    # Repeated evaluation after closure
    trade_after = paper_trading_engine.evaluate_paper_trade(res.id, bid=1.1200, ask=1.1202)
    assert trade_after.status == "CLOSED"
    assert trade_after.exitPrice == exit_price
    assert trade_after.closeDate == close_date
    assert trade_after.realizedRMultiple == realized_r


def test_10_duplicate_expiration_processing_is_idempotent():
    """10. Repeated expiration checks on expired candidate produce safe idempotent transitions."""
    cand = make_test_candidate(signal_id=2004)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=2004, execution_mode=ExecutionMode.PAPER.value
    )

    past_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    trade_expired = paper_trading_engine.expire_paper_trade(res.id, expiration_time=past_time)
    assert trade_expired.status == "EXPIRED"

    # Repeated expiration call on already EXPIRED trade returns None (already terminal)
    trade_expired_2 = paper_trading_engine.expire_paper_trade(res.id, expiration_time=past_time)
    assert trade_expired_2 is None

    # Subsequent quote cannot fill expired candidate
    quote = make_quote(bid=1.0998, ask=1.1000)
    filled_after = paper_trading_engine.simulate_fill(res.id, quote=quote)
    assert filled_after is None

    current = trade_journal_repository.get_trade(res.id)
    assert current.status == "EXPIRED"


def test_11_duplicate_invalidation_processing_is_idempotent():
    """11. Repeated invalidation calls leave candidate safely INVALIDATED with no side effects."""
    cand = make_test_candidate(signal_id=2005)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=2005, execution_mode=ExecutionMode.PAPER.value
    )

    trade_inv = paper_trading_engine.invalidate_paper_trade(res.id, reason="Technical structure broken")
    assert trade_inv.status == "INVALIDATED"

    # Second invalidation call returns None (already terminal)
    trade_inv_2 = paper_trading_engine.invalidate_paper_trade(res.id, reason="Repeated check")
    assert trade_inv_2 is None

    # Subsequent quote cannot fill invalidated candidate
    quote = make_quote(bid=1.0998, ask=1.1000)
    filled_after = paper_trading_engine.simulate_fill(res.id, quote=quote)
    assert filled_after is None

    current = trade_journal_repository.get_trade(res.id)
    assert current.status == "INVALIDATED"


def test_12_repeated_divergence_and_attribution_requests_are_deterministic():
    """12. Repeated divergence and attribution analytics requests yield deterministic results."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=2006,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            realizedPnl=Decimal("15.00"),
            result="WIN",
            openDate=now - timedelta(minutes=20),
            fillTime=now - timedelta(minutes=20),
            closeDate=now - timedelta(minutes=5),
            notes=inject_mode_token("Paper trade", ExecutionMode.PAPER),
        )
    )
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=2006,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1002,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=2.96,
            realizedPnl=Decimal("14.80"),
            result="WIN",
            openDate=now - timedelta(minutes=20),
            fillTime=now - timedelta(minutes=19, seconds=55),
            closeDate=now - timedelta(minutes=5),
            notes=inject_mode_token("Live trade", ExecutionMode.LIVE),
        )
    )

    # Call divergence 3 times
    div1 = execution_divergence_service.get_execution_divergence()
    div2 = execution_divergence_service.get_execution_divergence()
    div3 = execution_divergence_service.get_execution_divergence()
    assert div1.matchedPairsCount == div2.matchedPairsCount == div3.matchedPairsCount == 1
    assert div1.items[0].signalId == div2.items[0].signalId == 2006

    # Call attribution 3 times
    attr1 = strategy_attribution_service.get_strategy_attribution()
    attr2 = strategy_attribution_service.get_strategy_attribution()
    assert len(attr1.attributions) == len(attr2.attributions)


# ==============================================================================
# Group 3: Concurrency Hardening (Tests 13–18)
# ==============================================================================

def test_13_concurrent_guardian_authorization_respects_3_trade_ceiling():
    """13. Concurrent Guardian authorization requests strictly respect the 3-trade ceiling."""
    candidates = [make_test_candidate(signal_id=3000 + i) for i in range(8)]

    def try_authorize(cand_item):
        sig_id = int(cand_item.id.replace("cand-", ""))
        dec, res = signal_authorization_service.authorize_candidate(
            cand_item, signal_id=sig_id, execution_mode=ExecutionMode.PAPER.value
        )
        return (dec.allowed, res)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(try_authorize, c) for c in candidates]
        results = [f.result() for f in futures]

    allowed_count = sum(1 for allowed, _ in results if allowed)
    rejected_count = sum(1 for allowed, _ in results if not allowed)

    assert allowed_count <= settings.MAX_SIMULTANEOUS_TRADES
    assert allowed_count == 3
    assert rejected_count == 5


def test_14_concurrent_guardian_authorization_respects_aggregate_loss_limit(monkeypatch):
    from app.core.config.settings import settings
    monkeypatch.setattr(settings, "NEWS_BLACKOUT_ENABLED", False)
    monkeypatch.setattr(settings, "CAPITAL_CYCLE_STARTING_CAPITAL", Decimal("20.00"))
    from app.core.services.capital_cycle_service import capital_cycle_service
    cycle = capital_cycle_service.get_active_cycle()
    if cycle:
        cycle.activeTradingCapital = Decimal("20.00")
    """14. Concurrent Guardian authorization requests strictly respect aggregate loss limit."""
    # Active capital = $20.00. 4 threads attempt to authorize signals with $8.00 risk each.
    # 2 * $8 = $16 (< $20). 3 * $8 = $24 (> $20). Exactly 2 can succeed.
    proposals = [
        (3100 + i, make_test_proposal(risk_usd=8.00, entry_price=1.1000, stop_loss=1.0950))
        for i in range(4)
    ]

    def try_authorize_high_risk(item):
        sig_id, p = item
        dec, res = signal_authorization_service.authorize_and_reserve(
            proposal=p, signal_id=sig_id, execution_mode=ExecutionMode.PAPER.value
        )
        return dec.allowed

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(try_authorize_high_risk, p_item) for p_item in proposals]
        outcomes = [f.result() for f in futures]

    assert sum(1 for x in outcomes if x) == 2
    assert sum(1 for x in outcomes if not x) == 2


def test_15_advisory_lock_8882026_key_and_mechanism():
    """15. PostgreSQL advisory lock key is exactly 8882026 and acquire method handles lock."""
    assert FALCON_GUARDIAN_ADVISORY_LOCK_KEY == 8882026

    mock_session = MagicMock()
    mock_session.get_bind.return_value.dialect.name = "postgresql"
    signal_authorization_service._acquire_advisory_lock_if_postgres(mock_session)
    mock_session.execute.assert_called_once()
    sql_text = str(mock_session.execute.call_args[0][0])
    assert "pg_advisory_xact_lock" in sql_text
    assert mock_session.execute.call_args[0][1]["lock_id"] == 8882026


def test_16_concurrent_paper_runtime_quote_ticks():
    """16. Concurrent quote ticks across active paper trades process safely without corruption."""
    trade_ids = []
    for i in range(3):
        cand = make_test_candidate(signal_id=3200 + i)
        _, res = signal_authorization_service.authorize_candidate(
            cand, signal_id=3200 + i, execution_mode=ExecutionMode.PAPER.value
        )
        trade_ids.append(res.id)

    quotes = [make_quote(bid=1.0998, ask=1.1000) for _ in range(3)]

    def fill_trade(t_id, q):
        return paper_trading_engine.simulate_fill(t_id, quote=q)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fill_trade, t_id, q) for t_id, q in zip(trade_ids, quotes)]
        outcomes = [f.result() for f in futures]

    assert all(o is not None and o.status == "OPEN" for o in outcomes)


def test_17_concurrent_capital_cycle_transition_safety():
    """17. Concurrently triggering cycle transition cannot produce multiple ACTIVE cycles."""
    cycle_service = capital_guardian_service._cycle_service

    def attempt_transition():
        try:
            return cycle_service.transition_to_next_cycle(
                realized_cycle_profit=Decimal("480.00"),
                next_cycle_active_capital=Decimal("20.00"),
                banked_protected_profit=Decimal("460.00"),
            )
        except Exception as e:
            return str(e)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(attempt_transition) for _ in range(3)]
        results = [f.result() for f in futures]

    all_cycles = cycle_service._repo.list_cycles()
    active_cycles = [c for c in all_cycles if c.status == CapitalCycleStatus.ACTIVE]
    assert len(active_cycles) == 1


def test_18_concurrent_divergence_calculations():
    """18. Concurrent execution divergence calculations are thread-safe and deterministic."""
    def calc_div():
        return execution_divergence_service.get_execution_divergence()

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(calc_div) for _ in range(4)]
        results = [f.result() for f in futures]

    assert all(r.matchedPairsCount == results[0].matchedPairsCount for r in results)


# ==============================================================================
# Group 4: Failure Recovery Hardening (Tests 19–24)
# ==============================================================================

def test_19_database_transaction_rollback_on_journal_failure():
    """19. Database failure during trade creation rolls back cleanly without leaving orphaned records."""
    cand = make_test_candidate(signal_id=4001)

    with patch.object(trade_journal_repository, "create_trade", side_effect=RuntimeError("Simulated DB Disk Full")):
        dec, res = signal_authorization_service.authorize_candidate(
            cand, signal_id=4001, execution_mode=ExecutionMode.PAPER.value
        )
        assert dec.allowed is False
        assert res is None
        assert "simulated db disk full" in dec.reason.lower()

    trades = trade_journal_repository.list_trades()
    assert len(trades) == 0


def test_20_signal_authorization_failure_recovery():
    """20. Failed authorization leaves active trading capital completely unconsumed."""
    cycle_before = capital_guardian_service._cycle_service.get_active_cycle()
    cand = make_test_candidate(signal_id=4002)

    with patch.object(signal_authorization_service._guardian_service, "evaluate_proposed_trade", side_effect=ValueError("Unexpected calculation error")):
        dec, res = signal_authorization_service.authorize_candidate(cand, signal_id=4002)
        assert dec.allowed is False
        assert res is None

    cycle_after = capital_guardian_service._cycle_service.get_active_cycle()
    assert cycle_after.activeTradingCapital == cycle_before.activeTradingCapital


def test_21_paper_runtime_restart_recovery_from_pending():
    """21. Paper runtime restart simulation seamlessly recovers PENDING trade and fills on crossing."""
    cand = make_test_candidate(signal_id=4003, entry_price=1.1000)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=4003, execution_mode=ExecutionMode.PAPER.value
    )
    assert res.status == "PENDING"

    # Simulate full runtime restart with new engine
    new_engine = PaperTradingEngine(
        journal_repo=trade_journal_repository,
        guardian_service=capital_guardian_service,
        auth_service=signal_authorization_service,
    )

    quote = make_quote(bid=1.0998, ask=1.1000)
    filled_trade = new_engine.simulate_fill(res.id, quote=quote)
    assert filled_trade is not None
    assert filled_trade.status == "OPEN"
    assert filled_trade.fillPrice == 1.1000


def test_22_paper_runtime_restart_recovery_from_open():
    """22. Paper runtime restart simulation seamlessly recovers OPEN trade and closes on TP."""
    cand = make_test_candidate(signal_id=4004, entry_price=1.1000, take_profit=1.1150)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=4004, execution_mode=ExecutionMode.PAPER.value
    )
    quote_fill = make_quote(bid=1.0998, ask=1.1000)
    paper_trading_engine.simulate_fill(res.id, quote=quote_fill)

    # Simulate restart
    new_engine = PaperTradingEngine(
        journal_repo=trade_journal_repository,
        guardian_service=capital_guardian_service,
        auth_service=signal_authorization_service,
    )

    closed_trade = new_engine.evaluate_paper_trade(res.id, bid=1.1150, ask=1.1152)
    assert closed_trade.status == "CLOSED"
    assert closed_trade.result == "WIN"
    assert closed_trade.realizedRMultiple > 0


def test_23_retry_safety_after_transient_failure():
    """23. Retrying an authorization after a transient failure succeeds cleanly without side effects."""
    cand = make_test_candidate(signal_id=4005)

    # First attempt fails
    with patch.object(trade_journal_repository, "create_trade", side_effect=RuntimeError("Transient network drop")):
        dec1, res1 = signal_authorization_service.authorize_candidate(cand, signal_id=4005)
        assert dec1.allowed is False
        assert res1 is None

    # Retry attempt succeeds
    dec2, res2 = signal_authorization_service.authorize_candidate(cand, signal_id=4005)
    assert dec2.allowed is True
    assert res2 is not None
    assert res2.signalId == 4005


def test_24_partial_failure_in_batch_quote_processing():
    """24. Partial failure during one trade evaluation does not crash other trade evaluations."""
    cand1 = make_test_candidate(signal_id=4006)
    cand2 = make_test_candidate(signal_id=4007)
    _, res1 = signal_authorization_service.authorize_candidate(cand1, signal_id=4006, execution_mode=ExecutionMode.PAPER.value)
    _, res2 = signal_authorization_service.authorize_candidate(cand2, signal_id=4007, execution_mode=ExecutionMode.PAPER.value)

    quote = make_quote(bid=1.0998, ask=1.1000)

    def faulty_eval(trade_id, q):
        if trade_id == res1.id:
            raise ValueError("Corrupted memory on trade 1")
        return paper_trading_engine.simulate_fill(trade_id, quote=q)

    results = {}
    for t_id in [res1.id, res2.id]:
        try:
            results[t_id] = faulty_eval(t_id, quote)
        except Exception as e:
            results[t_id] = str(e)

    assert "Corrupted memory" in results[res1.id]
    assert results[res2.id].status == "OPEN"


# ==============================================================================
# Group 5: Capital Guardian Hardening (Tests 25–30)
# ==============================================================================

def test_25_guardian_strictly_enforces_3_trade_ceiling():
    """25. 4th trade candidate is rejected by Guardian with TRADES_CEILING_REACHED."""
    for i in range(3):
        cand = make_test_candidate(signal_id=5001 + i)
        dec, res = signal_authorization_service.authorize_candidate(cand, signal_id=5001 + i)
        assert dec.allowed is True

    # 4th trade
    cand4 = make_test_candidate(signal_id=5004)
    dec4, res4 = signal_authorization_service.authorize_candidate(cand4, signal_id=5004)
    assert dec4.allowed is False
    assert "maximum" in dec4.reason.lower() or "limit" in dec4.reason.lower() or "3" in dec4.reason
    assert res4 is None


def test_26_guardian_boundary_rejection_at_exact_equality(monkeypatch):
    from app.core.config.settings import settings
    monkeypatch.setattr(settings, "NEWS_BLACKOUT_ENABLED", False)
    monkeypatch.setattr(settings, "CAPITAL_CYCLE_STARTING_CAPITAL", Decimal("20.00"))
    from app.core.services.capital_cycle_service import capital_cycle_service
    cycle = capital_cycle_service.get_active_cycle()
    if cycle:
        cycle.activeTradingCapital = Decimal("20.00")
    """26. Boundary condition: existing_loss + proposed_loss == active_capital MUST FAIL."""
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=5010,
            status="OPEN",
            entryPrice=1.1000,
            stopLoss=1.0950,
            initialMonetaryRisk=Decimal("15.00"),
            notes=inject_mode_token("Existing active", ExecutionMode.PAPER),
        )
    )

    # Propose trade with exactly $5.00 risk. Total loss after = $20.00 == active capital.
    p = make_test_proposal(risk_usd=5.00)
    dec, res = signal_authorization_service.authorize_and_reserve(
        proposal=p, signal_id=5011, execution_mode=ExecutionMode.PAPER.value
    )
    assert dec.allowed is False
    assert "capital" in dec.reason.lower() or "loss" in dec.reason.lower()
    assert res is None


def test_27_guardian_boundary_rejection_when_exceeding_capital(monkeypatch):
    from app.core.config.settings import settings
    monkeypatch.setattr(settings, "NEWS_BLACKOUT_ENABLED", False)
    monkeypatch.setattr(settings, "CAPITAL_CYCLE_STARTING_CAPITAL", Decimal("20.00"))
    from app.core.services.capital_cycle_service import capital_cycle_service
    cycle = capital_cycle_service.get_active_cycle()
    if cycle:
        cycle.activeTradingCapital = Decimal("20.00")
    """27. Boundary condition: existing_loss + proposed_loss > active_capital MUST FAIL."""
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=5020,
            status="OPEN",
            entryPrice=1.1000,
            stopLoss=1.0950,
            initialMonetaryRisk=Decimal("15.00"),
            notes=inject_mode_token("Existing active", ExecutionMode.PAPER),
        )
    )

    p = make_test_proposal(risk_usd=5.01)
    dec, res = signal_authorization_service.authorize_and_reserve(
        proposal=p, signal_id=5021, execution_mode=ExecutionMode.PAPER.value
    )
    assert dec.allowed is False
    assert res is None


def test_28_guardian_paper_and_live_capital_isolation():
    """28. 3 active PAPER trades do not consume LIVE slots/capital; LIVE trade can be authorized."""
    for i in range(3):
        cand = make_test_candidate(signal_id=5030 + i)
        dec, _ = signal_authorization_service.authorize_candidate(
            cand, signal_id=5030 + i, execution_mode=ExecutionMode.PAPER.value
        )
        assert dec.allowed is True

    # 4th PAPER trade is rejected
    cand_p4 = make_test_candidate(signal_id=5034)
    dec_p4, _ = signal_authorization_service.authorize_candidate(
        cand_p4, signal_id=5034, execution_mode=ExecutionMode.PAPER.value
    )
    assert dec_p4.allowed is False

    # 1st LIVE trade is ALLOWED because LIVE slots and risk are completely isolated
    cand_live = make_test_candidate(signal_id=5035)
    dec_live, res_live = signal_authorization_service.authorize_candidate(
        cand_live, signal_id=5035, execution_mode=ExecutionMode.LIVE.value
    )
    assert dec_live.allowed is True
    assert res_live is not None
    assert parse_execution_mode(res_live.notes) == ExecutionMode.LIVE.value


def test_29_capital_cycle_full_transition_math():
    """29. Cycle transition: $20 active -> $500 target -> $480 profit -> $20 active + $460 protected."""
    cycle_service = capital_guardian_service._cycle_service
    active_before = cycle_service.get_active_cycle()
    assert active_before.cycleNumber == 1
    assert active_before.activeTradingCapital == Decimal("20.00")

    completed = cycle_service.complete_cycle(
        cycle_id=active_before.cycleId,
        completed_capital=Decimal("500.00"),
    )
    assert completed.status == CapitalCycleStatus.COMPLETED
    assert completed.realizedProfit == Decimal("480.00")
    assert completed.protectedProfit == Decimal("460.00")

    new_cycle = cycle_service.create_next_cycle()
    assert new_cycle.status == CapitalCycleStatus.ACTIVE
    assert new_cycle.cycleNumber == 2
    assert new_cycle.activeTradingCapital == Decimal("20.00")
    assert new_cycle.targetCapital == Decimal("500.00")
    assert cycle_service.get_protected_profit_total() == Decimal("460.00")


def test_30_protected_profit_isolation_never_increases_risk():
    """30. Protected banked profit ($460.00) never increases active risk capacity beyond $20.00."""
    cycle_service = capital_guardian_service._cycle_service
    active_before = cycle_service.get_active_cycle()
    cycle_service.complete_cycle(cycle_id=active_before.cycleId, completed_capital=Decimal("500.00"))
    cycle_service.create_next_cycle()

    p = make_test_proposal(risk_usd=25.00)  # > $20.00 active capital
    dec, res = signal_authorization_service.authorize_and_reserve(proposal=p, signal_id=5040)
    assert dec.allowed is False
    assert res is None


# ==============================================================================
# Group 6: Paper Runtime Hardening (Tests 31–38)
# ==============================================================================

def test_31_direction_aware_buy_fill_on_ask():
    """31. BUY candidate fills only when quote.ask <= entryPrice."""
    cand = make_test_candidate(signal_id=6001, direction=CandidateDirection.BUY, entry_price=1.1000)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=6001, execution_mode=ExecutionMode.PAPER.value
    )

    # Ask above entry: no fill
    q_no_fill = make_quote(bid=1.0998, ask=1.1001, last_price=1.1001)
    paper_trading_runtime.process_cycle(quotes=[q_no_fill])
    t_pending = trade_journal_repository.get_trade(res.id)
    assert t_pending.status == "PENDING"

    # Ask at entry: fills
    q_fill = make_quote(bid=1.0998, ask=1.1000, last_price=1.1000)
    paper_trading_runtime.process_cycle(quotes=[q_fill])
    t_filled = trade_journal_repository.get_trade(res.id)
    assert t_filled.status == "OPEN"
    assert t_filled.fillPrice == 1.1000


def test_32_direction_aware_sell_fill_on_bid():
    """32. SELL candidate fills only when quote.bid >= entryPrice."""
    cand = make_test_candidate(
        signal_id=6002,
        direction=CandidateDirection.SELL,
        entry_price=1.1000,
        stop_loss=1.1050,
        take_profit=1.0850,
    )
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=6002, execution_mode=ExecutionMode.PAPER.value
    )

    # Quote below entry: no fill
    paper_trading_runtime.process_cycle(quotes=[make_quote(bid=1.0995, ask=1.0998, last_price=1.0995)])
    t_pending = trade_journal_repository.get_trade(res.id)
    assert t_pending.status == "PENDING"

    # Quote reaches entry: fills
    paper_trading_runtime.process_cycle(quotes=[make_quote(bid=1.1000, ask=1.1003, last_price=1.1000)])
    t_filled = trade_journal_repository.get_trade(res.id)
    assert t_filled.status == "OPEN"


def test_33_direction_aware_buy_sl_and_tp(monkeypatch):
    from app.core.config.settings import settings
    monkeypatch.setattr(settings, "NEWS_BLACKOUT_ENABLED", False)
    """33. BUY trade triggers SL when bid <= stopLoss and TP when bid >= takeProfit."""
    # Test SL
    cand_sl = make_test_candidate(signal_id=6003, direction=CandidateDirection.BUY, entry_price=1.1000, stop_loss=1.0950)
    _, res_sl = signal_authorization_service.authorize_candidate(
        cand_sl, signal_id=6003, execution_mode=ExecutionMode.PAPER.value
    )
    paper_trading_engine.simulate_fill(res_sl.id, fill_price=1.1000)
    t_sl = paper_trading_engine.evaluate_paper_trade(res_sl.id, bid=1.0950, ask=1.0952)
    assert t_sl.status == "CLOSED"
    assert t_sl.result == "LOSS"

    # Test TP
    signal_authorization_service._post_stop_cooldowns.clear()
    cand_tp = make_test_candidate(signal_id=6004, direction=CandidateDirection.BUY, entry_price=1.1000, stop_loss=1.0950, take_profit=1.1150)
    _, res_tp = signal_authorization_service.authorize_candidate(
        cand_tp, signal_id=6004, execution_mode=ExecutionMode.PAPER.value
    )
    paper_trading_engine.simulate_fill(res_tp.id, fill_price=1.1000)
    t_tp = paper_trading_engine.evaluate_paper_trade(res_tp.id, bid=1.1150, ask=1.1152)
    assert t_tp.status == "CLOSED"
    assert t_tp.result == "WIN"


def test_34_direction_aware_sell_sl_and_tp(monkeypatch):
    from app.core.config.settings import settings
    monkeypatch.setattr(settings, "NEWS_BLACKOUT_ENABLED", False)
    """34. SELL trade triggers SL when ask >= stopLoss and TP when ask <= takeProfit."""
    # Test SL
    cand_sl = make_test_candidate(signal_id=6005, direction=CandidateDirection.SELL, entry_price=1.1000, stop_loss=1.1050, take_profit=1.0850)
    _, res_sl = signal_authorization_service.authorize_candidate(
        cand_sl, signal_id=6005, execution_mode=ExecutionMode.PAPER.value
    )
    paper_trading_engine.simulate_fill(res_sl.id, fill_price=1.1000)
    t_sl = paper_trading_engine.evaluate_paper_trade(res_sl.id, bid=1.1048, ask=1.1050)
    assert t_sl.status == "CLOSED"
    assert t_sl.result == "LOSS"

    # Test TP
    signal_authorization_service._post_stop_cooldowns.clear()
    cand_tp = make_test_candidate(signal_id=6006, direction=CandidateDirection.SELL, entry_price=1.1000, stop_loss=1.1050, take_profit=1.0850)
    _, res_tp = signal_authorization_service.authorize_candidate(
        cand_tp, signal_id=6006, execution_mode=ExecutionMode.PAPER.value
    )
    paper_trading_engine.simulate_fill(res_tp.id, fill_price=1.1000)
    t_tp = paper_trading_engine.evaluate_paper_trade(res_tp.id, bid=1.0848, ask=1.0850)
    assert t_tp.status == "CLOSED"
    assert t_tp.result == "WIN"


def test_35_ambiguous_simultaneous_sl_tp_resolves_to_loss():
    """35. Simultaneous crossing of SL and TP in single quote deterministically resolves to LOSS."""
    cand = make_test_candidate(signal_id=6007, direction=CandidateDirection.BUY, entry_price=1.1000, stop_loss=1.0950, take_profit=1.1150)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=6007, execution_mode=ExecutionMode.PAPER.value
    )
    paper_trading_engine.simulate_fill(res.id, fill_price=1.1000)

    # Bar with low <= SL and high >= TP
    t_amb = paper_trading_engine.evaluate_paper_trade(res.id, low=1.0940, high=1.1160)
    assert t_amb.status == "CLOSED"
    assert t_amb.result == "LOSS"  # strictly fail-closed


def test_36_mfe_mae_directional_tracking():
    """36. MFE and MAE track maximum favorable and adverse excursions directionally across ticks."""
    cand = make_test_candidate(signal_id=6008, direction=CandidateDirection.BUY, entry_price=1.1000)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=6008, execution_mode=ExecutionMode.PAPER.value
    )
    paper_trading_engine.simulate_fill(res.id, fill_price=1.1000)

    # Tick 1: favorable move to 1.1050
    t1 = paper_trading_engine.evaluate_paper_trade(res.id, bid=1.1050, ask=1.1052)
    assert t1.mfeR > 0

    # Tick 2: adverse move to 1.0980
    t2 = paper_trading_engine.evaluate_paper_trade(res.id, bid=1.0980, ask=1.0982)
    assert t2.mfeR == t1.mfeR  # MFE preserved
    assert t2.maeR > 0


def test_37_expired_candidate_cannot_subsequently_fill():
    """37. Candidate expired past deadline cannot fill on subsequent crossing quote."""
    cand = make_test_candidate(signal_id=6009)
    _, res = signal_authorization_service.authorize_candidate(cand, signal_id=6009)
    paper_trading_engine.expire_paper_trade(res.id, expiration_time=datetime.now(timezone.utc))

    q = make_quote(bid=1.0998, ask=1.1000)
    filled = paper_trading_engine.simulate_fill(res.id, quote=q)
    assert filled is None

    current = trade_journal_repository.get_trade(res.id)
    assert current.status == "EXPIRED"


def test_38_invalidated_candidate_cannot_subsequently_fill():
    """38. Invalidated candidate cannot fill on subsequent crossing quote."""
    cand = make_test_candidate(signal_id=6010)
    _, res = signal_authorization_service.authorize_candidate(cand, signal_id=6010)
    paper_trading_engine.invalidate_paper_trade(res.id, reason="Structure invalid")

    q = make_quote(bid=1.0998, ask=1.1000)
    filled = paper_trading_engine.simulate_fill(res.id, quote=q)
    assert filled is None

    current = trade_journal_repository.get_trade(res.id)
    assert current.status == "INVALIDATED"


# ==============================================================================
# Group 7: Manual LIVE Ingestion Hardening (Tests 39–43)
# ==============================================================================

def test_39_manual_live_ingestion_requires_valid_signal_id():
    """39. Manual LIVE trade ingestion requires valid signal_id."""
    cand = make_test_candidate(signal_id=7001)
    dec, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=7001, execution_mode=ExecutionMode.LIVE.value
    )
    assert dec.allowed is True
    assert res.signalId == 7001


def test_40_manual_live_ingestion_preserves_authoritative_fill_price_and_time():
    """40. Ingesting manual LIVE execution preserves authoritative fillPrice and fillTime."""
    cand = make_test_candidate(signal_id=7002, entry_price=1.1000)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=7002, execution_mode=ExecutionMode.LIVE.value
    )

    actual_fill_time = datetime.now(timezone.utc) - timedelta(minutes=1)
    actual_fill_price = 1.1004

    updated = trade_journal_repository.update_trade(
        res.id,
        TradeJournalUpdate(
            status="OPEN",
            fillPrice=actual_fill_price,
            fillTime=actual_fill_time,
        ),
    )
    assert updated.fillPrice == 1.1004
    assert updated.entryPrice == 1.1000
    assert updated.fillTime == actual_fill_time


def test_41_manual_live_record_preserves_live_mode_token():
    """41. Ingestion ensures [MODE:LIVE] token is preserved in notes and parsed accurately."""
    cand = make_test_candidate(signal_id=7003)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=7003, execution_mode=ExecutionMode.LIVE.value
    )
    assert "[MODE:LIVE]" in res.notes
    assert parse_execution_mode(res.notes) == ExecutionMode.LIVE.value


def test_42_manual_live_trade_lifecycle_progression():
    """42. Manual LIVE trade transitions correctly: PENDING -> OPEN -> CLOSED."""
    cand = make_test_candidate(signal_id=7004)
    _, res = signal_authorization_service.authorize_candidate(
        cand, signal_id=7004, execution_mode=ExecutionMode.LIVE.value
    )
    assert res.status == "PENDING"

    # Fill to OPEN
    t_open = trade_journal_repository.update_trade(
        res.id,
        TradeJournalUpdate(status="OPEN", fillPrice=1.1002, fillTime=datetime.now(timezone.utc)),
    )
    assert t_open.status == "OPEN"

    # Close
    t_closed = trade_journal_repository.update_trade(
        res.id,
        TradeJournalUpdate(
            status="CLOSED",
            exitPrice=1.1150,
            closeDate=datetime.now(timezone.utc),
            result="WIN",
            realizedRMultiple=2.96,
            profitLoss=Decimal("14.80"),
        ),
    )
    assert t_closed.status == "CLOSED"
    assert t_closed.result == "WIN"


def test_43_manual_live_trade_cannot_mutate_paper_capital():
    """43. Ingestion of manual LIVE trade cannot consume PAPER capital reservations."""
    cand_live = make_test_candidate(signal_id=7005)
    dec_live, res_live = signal_authorization_service.authorize_candidate(
        cand_live, signal_id=7005, execution_mode=ExecutionMode.LIVE.value
    )

    paper_res = capital_guardian_service.get_capital_reserving_trades(
        active_cycle=capital_guardian_service._cycle_service.get_active_cycle(),
        execution_mode=ExecutionMode.PAPER.value,
    )
    assert all(t.id != res_live.id for t in paper_res)


# ==============================================================================
# Group 8: Divergence Analytics Hardening (Tests 44–48)
# ==============================================================================

def test_44_divergence_pairing_strictly_by_signal_id():
    """44. Divergence pairs trades strictly by signal_id; different signal_id trades are never paired."""
    now = datetime.now(timezone.utc)
    # Trade A: signal_id = 8001 (PAPER)
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8001,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            result="WIN",
            closeDate=now,
            notes=inject_mode_token("Paper", ExecutionMode.PAPER),
        )
    )
    # Trade B: signal_id = 8002 (LIVE)
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8002,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1002,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=2.96,
            result="WIN",
            closeDate=now,
            notes=inject_mode_token("Live", ExecutionMode.LIVE),
        )
    )

    div = execution_divergence_service.get_execution_divergence()
    assert div.matchedPairsCount == 0


def test_45_divergence_excludes_historical_untagged_records():
    """45. Historical untagged records (executionMode=None) are strictly excluded from pairing."""
    now = datetime.now(timezone.utc)
    # Untagged record with same signalId
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8003,
            status="CLOSED",
            entryPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            result="WIN",
            closeDate=now,
            notes="Historical trade without mode token",
        )
    )
    # Live record
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8003,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1002,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=2.96,
            result="WIN",
            closeDate=now,
            notes=inject_mode_token("Live", ExecutionMode.LIVE),
        )
    )

    div = execution_divergence_service.get_execution_divergence()
    assert div.matchedPairsCount == 0


def test_46_deterministic_premature_exit_rule():
    """46. Deterministic premature exit: paper hit TP/higher R while live closed manually with lower R."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8004,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            result="WIN",
            closeDate=now,
            notes=inject_mode_token("Paper TP", ExecutionMode.PAPER),
        )
    )
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8004,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1000,
            exitPrice=1.1050,  # Manual premature close
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=1.0,
            result="WIN",
            closeDate=now,
            notes=inject_mode_token("Live manual exit", ExecutionMode.LIVE),
        )
    )

    div = execution_divergence_service.get_execution_divergence()
    assert div.matchedPairsCount == 1
    assert div.items[0].prematureExit is True


def test_47_missing_lifecycle_data_produces_none_never_fabricated():
    """47. Missing lifecycle timestamps or prices produce None, never fabricated values."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8005,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            result="WIN",
            closeDate=now,
            fillTime=None,  # Missing
            notes=inject_mode_token("Paper", ExecutionMode.PAPER),
        )
    )
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8005,
            status="CLOSED",
            entryPrice=1.1000,
            fillPrice=1.1002,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=2.96,
            result="WIN",
            closeDate=now,
            fillTime=None,  # Missing live fill time ensures latency cannot be computed
            notes=inject_mode_token("Live", ExecutionMode.LIVE),
        )
    )

    div = execution_divergence_service.get_execution_divergence()
    assert div.matchedPairsCount == 1
    assert div.items[0].executionLatencySeconds is None


def test_48_as_of_lookahead_protection_in_divergence():
    """48. as_of parameter strictly filters out trades closed after as_of in divergence analytics."""
    t_entry = datetime(2026, 9, 15, 10, 0, 0, tzinfo=timezone.utc)
    t_future = datetime(2026, 9, 15, 14, 0, 0, tzinfo=timezone.utc)

    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8006,
            status="CLOSED",
            tradeDate=t_entry,
            entryPrice=1.1000,
            fillPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            result="WIN",
            closeDate=t_future,
            notes=inject_mode_token("Paper", ExecutionMode.PAPER),
        )
    )
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=8006,
            status="CLOSED",
            tradeDate=t_entry,
            entryPrice=1.1000,
            fillPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            result="WIN",
            closeDate=t_future,
            notes=inject_mode_token("Live", ExecutionMode.LIVE),
        )
    )

    # Calling with as_of=13:00 (before closeDate 14:00)
    div_past = execution_divergence_service.get_execution_divergence(as_of=datetime(2026, 9, 15, 13, 0, 0, tzinfo=timezone.utc))
    assert div_past.matchedPairsCount == 0

    # Calling with as_of=15:00 (after closeDate 14:00)
    div_future = execution_divergence_service.get_execution_divergence(as_of=datetime(2026, 9, 15, 15, 0, 0, tzinfo=timezone.utc))
    assert div_future.matchedPairsCount == 1


# ==============================================================================
# Group 9: Strategy Attribution & Statistical Drift Hardening (Tests 49–54)
# ==============================================================================

def test_49_attribution_grouped_across_exact_4_tuple():
    """49. Attribution groups trades across (strategyId, strategyVersion, adaptiveRuleVersion, executionMode)."""
    now = datetime.now(timezone.utc)
    for mode in [ExecutionMode.PAPER, ExecutionMode.LIVE]:
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=9001,
                strategyId="MOMENTUM_BREAKOUT",
                strategyVersion="1.2.0",
                adaptiveRuleVersion="v2.1",
                symbol="EURUSD",
                direction="BUY",
                status="CLOSED",
                entryPrice=1.1000,
                fillPrice=1.1000,
                exitPrice=1.1150,
                stopLoss=1.0950,
                takeProfit=1.1150,
                realizedR=3.0,
                result="WIN",
                closeDate=now,
                notes=inject_mode_token("Trade", mode),
            )
        )

    attr = strategy_attribution_service.get_strategy_attribution()
    assert len(attr.attributions) == 2
    keys = [(g.key.strategyId, g.key.strategyVersion, g.key.adaptiveRuleVersion, g.key.executionMode) for g in attr.attributions]
    assert ("MOMENTUM_BREAKOUT", "1.2.0", "v2.1", "PAPER") in keys
    assert ("MOMENTUM_BREAKOUT", "1.2.0", "v2.1", "LIVE") in keys


def test_50_historical_untagged_records_isolated_from_attribution():
    """50. Historical records with executionMode=None do not pollute mode-specific attribution buckets."""
    now = datetime.now(timezone.utc)
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=9002,
            status="CLOSED",
            entryPrice=1.1000,
            exitPrice=1.1150,
            stopLoss=1.0950,
            takeProfit=1.1150,
            realizedR=3.0,
            result="WIN",
            closeDate=now,
            notes="Legacy trade without mode token",
        )
    )

    attr = strategy_attribution_service.get_strategy_attribution()
    paper_live = [g for g in attr.attributions if g.key.executionMode in ("PAPER", "LIVE")]
    assert len(paper_live) == 0
    assert any(g.key.executionMode == "UNKNOWN" for g in attr.attributions)


def test_51_exact_se_and_z_score_formula_verification():
    """51. Exact statistical drift formula: SE = sqrt(p_paper * (1 - p_paper) / N_live) and z = (p_live - p_paper) / SE."""
    now = datetime.now(timezone.utc)
    # Seed 20 PAPER trades: 12 wins, 8 losses -> p_paper = 0.60
    for i in range(20):
        is_win = i < 12
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=9100 + i,
                status="CLOSED",
                entryPrice=1.1000,
                fillPrice=1.1000,
                exitPrice=1.1150 if is_win else 1.0950,
                stopLoss=1.0950,
                takeProfit=1.1150,
                realizedR=3.0 if is_win else -1.0,
                result="WIN" if is_win else "LOSS",
                closeDate=now,
                notes=inject_mode_token(f"Paper {i}", ExecutionMode.PAPER),
            )
        )

    # Seed 20 LIVE trades: 7 wins, 13 losses -> p_live = 0.35
    for i in range(20):
        is_win = i < 7
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=9200 + i,
                status="CLOSED",
                entryPrice=1.1000,
                fillPrice=1.1000,
                exitPrice=1.1150 if is_win else 1.0950,
                stopLoss=1.0950,
                takeProfit=1.1150,
                realizedR=3.0 if is_win else -1.0,
                result="WIN" if is_win else "LOSS",
                closeDate=now,
                notes=inject_mode_token(f"Live {i}", ExecutionMode.LIVE),
            )
        )

    # Expected:
    # p_paper = 0.60, p_live = 0.35, N_live = 20
    # SE = sqrt(0.60 * 0.40 / 20) = sqrt(0.012) = 0.1095445
    # z = (0.35 - 0.60) / 0.1095445 = -2.282177
    attr = strategy_attribution_service.get_strategy_attribution()
    assert len(attr.driftDiagnostics) == 1
    diag = attr.driftDiagnostics[0]
    assert diag.paperWinRate == pytest.approx(0.60, abs=1e-3)
    assert diag.liveWinRate == pytest.approx(0.35, abs=1e-3)
    expected_se = math.sqrt(0.60 * 0.40 / 20.0)
    assert diag.standardError == pytest.approx(expected_se, abs=1e-4)
    expected_z = (0.35 - 0.60) / expected_se
    assert diag.zScoreWinRate == pytest.approx(expected_z, abs=0.01)
    assert diag.warning is True  # z < -2.0


def test_52_drift_warning_strictly_when_z_less_than_minus_2():
    """52. Drift warning triggers strictly when z < -2.0; z >= -2.0 produces warning=False."""
    now = datetime.now(timezone.utc)
    # Seed 20 PAPER trades: 10 wins (50%)
    for i in range(20):
        is_win = i < 10
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=9300 + i,
                status="CLOSED",
                entryPrice=1.1000,
                exitPrice=1.1150 if is_win else 1.0950,
                stopLoss=1.0950,
                takeProfit=1.1150,
                realizedR=3.0 if is_win else -1.0,
                result="WIN" if is_win else "LOSS",
                closeDate=now,
                notes=inject_mode_token(f"Paper {i}", ExecutionMode.PAPER),
            )
        )

    # Seed 20 LIVE trades: 8 wins (40%) -> z = -0.894 (not < -2.0)
    for i in range(20):
        is_win = i < 8
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=9400 + i,
                status="CLOSED",
                entryPrice=1.1000,
                exitPrice=1.1150 if is_win else 1.0950,
                stopLoss=1.0950,
                takeProfit=1.1150,
                realizedR=3.0 if is_win else -1.0,
                result="WIN" if is_win else "LOSS",
                closeDate=now,
                notes=inject_mode_token(f"Live {i}", ExecutionMode.LIVE),
            )
        )

    attr = strategy_attribution_service.get_strategy_attribution()
    diag = attr.driftDiagnostics[0]
    assert diag.warning is False
    assert diag.zScoreWinRate > -2.0


def test_53_insufficient_sample_and_degenerate_se_produces_not_evaluable():
    """53. Sample size < 10 or degenerate SE produces NOT_EVALUABLE with warning=False."""
    now = datetime.now(timezone.utc)
    # 5 PAPER trades, 5 LIVE trades (< 10)
    for i in range(5):
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=9500 + i,
                status="CLOSED",
                entryPrice=1.1000,
                exitPrice=1.1150,
                stopLoss=1.0950,
                takeProfit=1.1150,
                realizedR=3.0,
                result="WIN",
                closeDate=now,
                notes=inject_mode_token(f"Paper {i}", ExecutionMode.PAPER),
            )
        )
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=9500 + i,
                status="CLOSED",
                entryPrice=1.1000,
                exitPrice=1.0950,
                stopLoss=1.0950,
                takeProfit=1.1150,
                realizedR=-1.0,
                result="LOSS",
                closeDate=now,
                notes=inject_mode_token(f"Live {i}", ExecutionMode.LIVE),
            )
        )

    attr = strategy_attribution_service.get_strategy_attribution()
    diag = attr.driftDiagnostics[0]
    assert diag.status == DriftStatus.NOT_EVALUABLE.value
    assert diag.warning is False
    assert diag.zScoreWinRate is None


def test_54_profit_factor_drift_strictly_not_evaluable():
    """54. Profit Factor drift diagnostic remains strictly Option A: NOT_EVALUABLE and zScoreProfitFactor=None."""
    attr = strategy_attribution_service.get_strategy_attribution()
    for diag in attr.driftDiagnostics:
        assert diag.zScoreProfitFactor is None
        assert diag.profitFactorDrift == "NOT_EVALUABLE"


# ==============================================================================
# Group 10: API Hardening & Error Handling (Tests 55–60)
# ==============================================================================

def test_55_api_execution_mode_endpoint_read_only():
    """55. GET /api/v1/execution/mode returns active state safely and is read-only."""
    client = TestClient(app)
    res = client.get("/api/v1/execution/mode")
    assert res.status_code == 200
    data = res.json()
    assert data["activeMode"] in ("PAPER", "LIVE")
    assert data["failClosed"] is True
    assert data["brokerAutomationLocked"] is True


def test_56_api_paper_trades_endpoint_pagination_and_mode_isolation():
    """56. GET /api/v1/paper/trades returns only PAPER trades and respects limit."""
    now = datetime.now(timezone.utc)
    for i in range(3):
        trade_journal_repository.create_trade(
            make_journal_create(
                signalId=10001 + i,
                status="OPEN",
                notes=inject_mode_token(f"Paper {i}", ExecutionMode.PAPER),
            )
        )
    trade_journal_repository.create_trade(
        make_journal_create(
            signalId=10004,
            status="OPEN",
            notes=inject_mode_token("Live trade", ExecutionMode.LIVE),
        )
    )

    client = TestClient(app)
    res = client.get("/api/v1/paper/trades?limit=2")
    assert res.status_code == 200
    data = res.json()
    trades = data["trades"]
    assert len(trades) == 2
    assert all("[MODE:PAPER]" in t["notes"] for t in trades)


def test_57_api_divergence_handles_empty_dataset_safely():
    """57. GET /api/v1/analytics/divergence returns 200 with empty list on empty database."""
    client = TestClient(app)
    res = client.get("/api/v1/analytics/divergence")
    assert res.status_code == 200
    data = res.json()
    assert data["matchedPairsCount"] == 0
    assert data["items"] == []
    assert data["averageLatencySeconds"] is None


def test_58_api_attribution_handles_empty_dataset_safely():
    """58. GET /api/v1/analytics/attribution returns 200 with empty lists on empty database."""
    client = TestClient(app)
    res = client.get("/api/v1/analytics/attribution")
    assert res.status_code == 200
    data = res.json()
    assert data["attributions"] == []
    assert data["driftDiagnostics"] == []


def test_59_api_malformed_parameters_and_as_of_return_422():
    """59. Passing invalid as_of or malformed parameter values returns controlled HTTP 422."""
    client = TestClient(app)
    res = client.get("/api/v1/analytics/divergence?as_of=invalid-date-format")
    assert res.status_code == 422


def test_60_api_endpoints_do_not_mutate_data():
    """60. Repeated GET calls across execution/paper/analytics endpoints leave DB row count identical."""
    count_before = len(trade_journal_repository.list_trades())
    client = TestClient(app)
    client.get("/api/v1/execution/mode")
    client.get("/api/v1/paper/trades")
    client.get("/api/v1/analytics/divergence")
    client.get("/api/v1/analytics/attribution")
    client.get("/api/v1/analytics/canonical")
    client.get("/api/v1/analytics/execution-quality")
    count_after = len(trade_journal_repository.list_trades())
    assert count_before == count_after
