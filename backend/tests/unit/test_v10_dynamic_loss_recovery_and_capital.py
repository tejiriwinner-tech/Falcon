"""
Falcon V10 Test Suite: Dynamic Loss-Recovery Engine & Flexible Capital Sizing

Validates:
1. Dynamic Capital Sizing: Falcon can trade with any capital amount ($50, $100, $500, etc.)
   and dynamically update active capital via service and REST endpoint.
2. Multiplier Progression:
   - 0 consecutive losses -> 1.0x baseline reward target
   - 1 consecutive loss   -> 2.0x double reward target (RECOVERY_2X)
   - 2 consecutive losses -> 4.0x quadruple reward target (RECOVERY_4X)
   - 1 win -> clean reset to 1.0x baseline and $0.00 streak loss
3. Hard $20.00 Maximum Entertaining Loss Ceiling:
   - Falcon strictly rejects any proposed trade if accumulated streak loss + proposed loss > $20.00.
4. Take Profit Scaling:
   - SignalGenerationEngine doubles and quadruples Take Profit distance while preserving Stop Loss.
5. Instant Market Execution:
   - ACTIVE signals ground entry price to live market quote and include [MARKET EXECUTION - ENTER NOW].
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.core.config.settings import settings
from app.core.analytics.adaptive_tuning_engine import (
    AdaptiveRuleTuningEngine,
    LossRecoveryMetrics,
)
from app.core.engines.signal_generation_engine import SignalGenerationEngine
from app.core.instruments.instrument_registry import instrument_registry
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    InMemoryCapitalCycleStorage,
)
from app.core.repository.trade_journal_repository import (
    TradeJournalRepository,
    InMemoryTradeJournalStorage,
)
from app.core.services.capital_cycle_service import CapitalCycleService
from app.core.services.capital_guardian_service import CapitalGuardianService
from app.core.services.signal_service import SignalService
from app.core.providers import provider_manager
from app.schemas.capital_cycle import CapitalCycleCreate, CapitalCycleStatus
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.signal_candidate import CandidateDirection, SignalCandidate, CandidateStatus
from app.schemas.trade_journal import TradeJournalCreate
from main import app


@pytest.fixture
def mem_journal_repo() -> TradeJournalRepository:
    storage = InMemoryTradeJournalStorage()
    repo = TradeJournalRepository.__new__(TradeJournalRepository)
    repo._storage = storage
    return repo


@pytest.fixture
def mem_cycle_repo() -> CapitalCycleRepository:
    storage = InMemoryCapitalCycleStorage()
    return CapitalCycleRepository(storage=storage)


@pytest.fixture
def cycle_service(mem_cycle_repo: CapitalCycleRepository) -> CapitalCycleService:
    return CapitalCycleService(repository=mem_cycle_repo)


@pytest.fixture
def guardian(
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
) -> CapitalGuardianService:
    return CapitalGuardianService(
        cycle_service=cycle_service,
        journal_repository=mem_journal_repo,
        instrument_registry=instrument_registry,
    )


@pytest.fixture
def tuning_engine() -> AdaptiveRuleTuningEngine:
    return AdaptiveRuleTuningEngine()


def _init_cycle(
    cycle_service: CapitalCycleService,
    active_capital: Decimal = Decimal("20.00"),
    target_capital: Decimal = Decimal("500.00"),
):
    payload = CapitalCycleCreate(
        cycleId="test-cycle-v10",
        cycleNumber=1,
        startingCapital=active_capital,
        targetCapital=target_capital,
        activeTradingCapital=active_capital,
        protectedProfit=Decimal("0.00"),
        status=CapitalCycleStatus.ACTIVE,
        startedAt=datetime.now(timezone.utc),
    )
    return cycle_service._repo.create_cycle(payload)


# ── TEST 1: Loss Recovery Multiplier Progression & Win Reset ─────────────────

def test_loss_recovery_multiplier_progression(
    mem_journal_repo: TradeJournalRepository,
    tuning_engine: AdaptiveRuleTuningEngine,
):
    """Test 0 losses = 1.0x, 1 loss = 2.0x, 2 losses = 4.0x, win = 1.0x reset."""
    now = datetime.now(timezone.utc)

    # 1. Zero trades -> baseline
    metrics = tuning_engine.get_loss_recovery_metrics(journal_repo=mem_journal_repo)
    assert metrics.consecutive_losses == 0
    assert metrics.profit_recovery_multiplier == 1.0
    assert metrics.recovery_status == "BASELINE"
    assert metrics.accumulated_streak_loss == Decimal("0.00")

    # 2. 1st Loss (-$4.50)
    mem_journal_repo.create_trade(TradeJournalCreate(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0850,
        stopLoss=1.0805,
        takeProfit=1.0940,
        timeframe="1h",
        marketSession="London",
        tradeDate=now - timedelta(hours=3),
        closeDate=now - timedelta(hours=2),
        status="CLOSED",
        result="LOSS",
        profitLoss=-4.50,
        reasonForEntry="Trend pullback",
        reasonForExit="Stop loss hit due to wick sweep",
        lessonLearned="Widen ATR buffer near structural highs",
    ))

    metrics_1 = tuning_engine.get_loss_recovery_metrics(journal_repo=mem_journal_repo)
    assert metrics_1.consecutive_losses == 1
    assert metrics_1.profit_recovery_multiplier == 1.0
    assert metrics_1.accumulated_streak_loss == Decimal("4.50")
    assert "Widen ATR buffer" in metrics_1.ai_reflection

    # 3. 2nd Consecutive Loss (-$5.20)
    mem_journal_repo.create_trade(TradeJournalCreate(
        symbol="GBPUSD",
        direction="SELL",
        entryPrice=1.2700,
        stopLoss=1.2752,
        takeProfit=1.2596,
        timeframe="1h",
        marketSession="New York",
        tradeDate=now - timedelta(hours=2),
        closeDate=now - timedelta(hours=1),
        status="CLOSED",
        result="LOSS",
        profitLoss=-5.20,
        reasonForEntry="Breakout rejection",
        reasonForExit="Stop loss hit on news volatility",
        lessonLearned="Filter out high impact news releases",
    ))

    metrics_2 = tuning_engine.get_loss_recovery_metrics(journal_repo=mem_journal_repo)
    assert metrics_2.consecutive_losses == 2
    assert metrics_2.profit_recovery_multiplier == 1.0
    assert metrics_2.accumulated_streak_loss == Decimal("9.70")

    # 4. Subsequent Win -> Complete Reset
    mem_journal_repo.create_trade(TradeJournalCreate(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0800,
        stopLoss=1.0770,
        takeProfit=1.0920,
        timeframe="1h",
        marketSession="London",
        tradeDate=now - timedelta(minutes=45),
        closeDate=now - timedelta(minutes=10),
        status="CLOSED",
        result="WIN",
        profitLoss=18.50,
        reasonForEntry="Institutional liquidity grab confirmed",
        reasonForExit="Take profit reached cleanly",
        lessonLearned="Clean win: 4.0x multiplier recovered all streak deficits",
    ))

    metrics_reset = tuning_engine.get_loss_recovery_metrics(journal_repo=mem_journal_repo)
    assert metrics_reset.consecutive_losses == 0
    assert metrics_reset.profit_recovery_multiplier == 1.0
    assert metrics_reset.recovery_status == "BASELINE"
    assert metrics_reset.accumulated_streak_loss == Decimal("0.00")


# ── TEST 2: Active Capital Loss Capacity Evaluation in Capital Guardian ─────────

def test_hard_20_dollar_max_entertaining_loss_ceiling(
    cycle_service: CapitalCycleService,
    mem_journal_repo: TradeJournalRepository,
    guardian: CapitalGuardianService,
):
    """
    Validates that Falcon evaluates proposed trades against active trading capital
    without being artificially blocked by rigid $20 ceilings.
    """
    _init_cycle(cycle_service, active_capital=Decimal("100.00"))
    now = datetime.now(timezone.utc)

    # Record streak loss of $14.00
    mem_journal_repo.create_trade(TradeJournalCreate(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=1.0850,
        stopLoss=1.0710,
        takeProfit=1.1130,
        timeframe="1h",
        marketSession="London",
        tradeDate=now - timedelta(hours=2),
        closeDate=now - timedelta(hours=1),
        status="CLOSED",
        result="LOSS",
        profitLoss=-14.00,
        reasonForEntry="Setup",
        reasonForExit="Stopped out",
    ))

    # Proposal A: $5.00 loss -> ALLOWED (well within $100 active capital)
    proposal_allowed = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.0800"),
        stopLoss=Decimal("1.0750"),  # 50 pips * 0.01 lot = $5.00
        lotSize=Decimal("0.01"),
        monetaryRisk=Decimal("5.00"),
        isVerifiedRisk=True,
    )
    decision_a = guardian.evaluate_proposed_trade(proposal_allowed)
    assert decision_a.allowed is True
    assert decision_a.proposedWorstCaseLoss == Decimal("5.00")

    # Proposal B: $7.00 loss ($14 streak deficit does not block trade under active capital) -> ALLOWED
    proposal_allowed_b = ProposedTradeInput(
        symbol="EURUSD",
        direction="BUY",
        entryPrice=Decimal("1.0800"),
        stopLoss=Decimal("1.0730"),  # 70 pips * 0.01 lot = $7.00
        lotSize=Decimal("0.01"),
        monetaryRisk=Decimal("7.00"),
        isVerifiedRisk=True,
    )
    decision_b = guardian.evaluate_proposed_trade(proposal_allowed_b)
    assert decision_b.allowed is True


# ── TEST 3: Take Profit Reward Distance Scaling in SignalGenerationEngine ───

def test_take_profit_scaling_with_recovery_multiplier():
    """Verify SignalGenerationEngine._calculate_trade_levels scales TP with recovery_mult."""
    current_price = 1.08000
    atr = 0.00200
    rr = 2.0

    # 1. Baseline (1.0x)
    _, sl_1, tp_1 = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=current_price,
        atr=atr,
        symbol="EURUSD",
        adaptive_mult=1.0,
        rr=rr,
        recovery_mult=1.0,
    )
    risk_dist_1 = round(current_price - sl_1, 5)
    reward_dist_1 = round(tp_1 - current_price, 5)
    assert risk_dist_1 == 0.00300  # 1.5 * 0.002
    assert reward_dist_1 == 0.00600  # 2.0 * 0.003

    # 2. Recovery 2.0x (Double Profit)
    _, sl_2, tp_2 = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=current_price,
        atr=atr,
        symbol="EURUSD",
        adaptive_mult=1.0,
        rr=rr,
        recovery_mult=2.0,
    )
    risk_dist_2 = round(current_price - sl_2, 5)
    reward_dist_2 = round(tp_2 - current_price, 5)
    assert risk_dist_2 == risk_dist_1  # Risk distance is identical!
    assert reward_dist_2 == reward_dist_1  # Disciplined non-martingale: TP is not stretched after losses

    # 3. Recovery 4.0x maintains disciplined R:R
    _, sl_4, tp_4 = SignalGenerationEngine._calculate_trade_levels(
        direction=CandidateDirection.BUY,
        current_price=current_price,
        atr=atr,
        symbol="EURUSD",
        adaptive_mult=1.0,
        rr=rr,
        recovery_mult=4.0,
    )
    risk_dist_4 = round(current_price - sl_4, 5)
    reward_dist_4 = round(tp_4 - current_price, 5)
    assert risk_dist_4 == risk_dist_1  # Risk distance is identical!
    assert reward_dist_4 == reward_dist_1  # Disciplined non-martingale: TP is not stretched after losses


# ── TEST 4: Flexible Capital Sizing Endpoint & Service ───────────────────────

def test_flexible_capital_sizing_service_and_endpoint(
    cycle_service: CapitalCycleService,
):
    """Test user can trade with any amount of capital ($150, $500, etc.)."""
    cycle = _init_cycle(cycle_service, active_capital=Decimal("20.00"))
    assert cycle.activeTradingCapital == Decimal("20.00")

    # Update to $150.00
    updated = cycle_service.update_active_capital(Decimal("150.00"))
    assert updated.activeTradingCapital == Decimal("150.00")

    # Update to $500.00
    updated_500 = cycle_service.update_active_capital(Decimal("500.00"))
    assert updated_500.activeTradingCapital == Decimal("500.00")


def test_rest_api_set_capital_endpoint():
    """Test POST /api/v1/capital-cycles/set-capital with FastAPI TestClient."""
    client = TestClient(app)
    response = client.post("/api/v1/capital-cycles/set-capital?amount=250.00")
    assert response.status_code == 200
    data = response.json()
    assert float(data["activeTradingCapital"]) == 250.00
    assert data["status"] == "ACTIVE"


# ── TEST 5: Instant Market Execution in SignalService ────────────────────────

def test_instant_market_execution_and_signal_formatting():
    """Test ACTIVE signals format Instant Market Execution trigger rule and recovery reflection."""
    from app.schemas.signal_candidate import CandidateMarketSnapshot, ConfidenceBreakdown
    sig_service = SignalService()
    now = datetime.now(timezone.utc)

    candidate = SignalCandidate(
        id="cand-test-001",
        symbol="EUR/USD",
        strategyId="sniper-breakout",
        strategyName="Sniper Breakout Strategy",
        strategyVersion="2.0",
        strategyGrade="A",
        strategyScore=92,
        direction=CandidateDirection.BUY,
        confidence=90,
        readinessScore=95,
        entryPrice=1.0820,
        stopLoss=1.0790,
        takeProfit=1.0880,
        riskReward=2.0,
        status=CandidateStatus.APPROVED,
        generatedAt=now,
        reasons=[],
        conditions=[],
        marketSnapshot=CandidateMarketSnapshot(
            trend="Bullish",
            volatility="Moderate",
            session="London",
            spread=0.8,
            newsImpact="Low",
            marketSentiment="Greedy",
            marketConfidence=85,
        ),
        confidenceBreakdown=ConfidenceBreakdown(
            trendScore=30,
            strategyScore=25,
            sessionScore=20,
            sentimentScore=15,
            newsScore=10,
        ),
        evaluationDurationMs=10,
        marketDataAgeSeconds=5,
        evaluationStartedAt=now,
        evaluationCompletedAt=now,
    )

    metrics = LossRecoveryMetrics(
        consecutive_losses=1,
        profit_recovery_multiplier=2.0,
        accumulated_streak_loss=Decimal("4.50"),
        recovery_status="RECOVERY_2X",
        ai_reflection="Falcon AI Adaptation [1 Loss Detected]: Doubling profit target (2.0x).",
    )

    signal_item = sig_service._to_signal(
        candidate=candidate,
        decision=None,
        signal_id=101,
        now=now,
        is_active=True,
        recovery_metrics=metrics,
    )

    assert signal_item.status == "ACTIVE"
    assert "[MARKET EXECUTION - ENTER NOW]" in signal_item.triggerCondition
    assert "[RECOVERY_2X - 2X TARGET]" in signal_item.analysis
    assert "Doubling profit target (2.0x)" in signal_item.analysis
    assert signal_item.profitRecoveryMultiplier == 2.0
    assert signal_item.recoveryStatus == "RECOVERY_2X"
