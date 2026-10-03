"""
Unit tests for Falcon Trade Lifecycle (WON, LOST, BREAKEVEN) and RegimeMemoryEngine Closed-Loop Learning.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import pytest

from app.core.analytics.regime_memory_engine import RegimeMemoryEngine, RootCauseType, StrategyHealthStatus
from app.core.providers import provider_manager
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_outcome_resolver import SignalOutcomeResolver
from app.schemas.trade_journal import TradeJournalCreate


@pytest.fixture(autouse=True)
def clean_ledger():
    regime_engine = RegimeMemoryEngine()
    regime_engine.clear_memory()
    yield
    regime_engine.clear_memory()


def test_regime_memory_diagnose_won_trade():
    """Verify that a WON trade reinforces strategy conviction and records TAKE_PROFIT_HIT."""
    engine = RegimeMemoryEngine()

    trade_record = {
        "trade_id": "trade-001",
        "symbol": "GBPUSD",
        "strategy_id": "SMC_OrderBlock",
        "result": "WON",
        "profit_loss": 50.0,
        "direction": "BUY",
        "entry_price": 1.3200,
        "take_profit": 1.3250,
        "stop_loss": 1.3175,
        "exit_price": 1.3250,
    }

    diag = engine.diagnose_trade_outcome(trade_record)
    assert diag.outcome == "WIN"
    assert diag.root_cause == RootCauseType.TAKE_PROFIT_HIT
    assert diag.prescribed_adaptation["action"] == "REINFORCE_STRATEGY"
    assert diag.prescribed_adaptation["reinforce_strategy"] is True


def test_regime_memory_diagnose_breakeven_trade():
    """Verify that a BREAKEVEN trade is recognized as capital defense and does not trigger loss penalties."""
    engine = RegimeMemoryEngine()

    trade_record = {
        "trade_id": "trade-002",
        "symbol": "EURUSD",
        "strategy_id": "SMC_LiquiditySweep",
        "result": "BREAKEVEN",
        "profit_loss": 0.0,
        "direction": "BUY",
        "entry_price": 1.1000,
        "take_profit": 1.1050,
        "stop_loss": 1.1001,
        "exit_price": 1.1001,
        "reason_for_exit": "Break-Even Stop Hit (Capital Defended after TP1)",
    }

    diag = engine.diagnose_trade_outcome(trade_record)
    assert diag.outcome == "BREAKEVEN"
    assert "Capital defended" in diag.lesson_learned
    assert diag.prescribed_adaptation["action"] == "MAINTAIN_CURRENT_RISK"
    assert diag.prescribed_adaptation["recommended_weight"] == 1.0


def test_regime_memory_diagnose_liquidity_sweep_loss():
    """Verify that an institutional liquidity sweep stop-out prescribes +35% ATR stop buffer expansion."""
    engine = RegimeMemoryEngine()

    trade_record = {
        "trade_id": "trade-003",
        "symbol": "XAUUSD",
        "strategy_id": "Gold_Sniper",
        "result": "LOST",
        "profit_loss": -25.0,
        "direction": "BUY",
        "entry_price": 2650.0,
        "stop_loss": 2640.0,
        "exit_price": 2640.0,
        "take_profit": 2680.0,
        "trough_price": 2638.0,  # Pierced SL
    }

    market_ctx = {
        "subsequent_direction": "BUY",
        "post_stop_price": 2665.0,  # Reversal back past entry
    }

    diag = engine.diagnose_trade_outcome(trade_record, market_context=market_ctx)
    assert diag.outcome == "LOSS"
    assert diag.root_cause == RootCauseType.INSTITUTIONAL_LIQUIDITY_SWEEP
    assert diag.prescribed_adaptation["action"] == "EXPAND_ATR_STOP_BUFFER"
    assert diag.prescribed_adaptation["atr_stop_multiplier_delta"] == 0.35


def test_signal_outcome_resolver_breakeven_classification():
    """Verify SignalOutcomeResolver classifies stop-out with SL >= entry as BREAKEVEN (+0.75R)."""
    resolver = SignalOutcomeResolver()

    # Create a trade where SL has been moved to Breakeven
    trade = trade_journal_repository.create_trade(
        TradeJournalCreate(
            signalId=7701,
            symbol="USDJPY",
            direction="BUY",
            entryPrice=150.00,
            fillPrice=150.00,
            fillTime=datetime.now(timezone.utc),
            stopLoss=150.01,  # Breakeven + spread
            takeProfit=151.00,
            timeframe="M15",
            marketSession="Tokyo",
            tradeDate=datetime.now(timezone.utc),
            status="OPEN",
            result="PENDING",
            profitLoss=0.0,
            riskReward=2.0,
            confidence=85,
            reasonForEntry="Test Breakeven Entry",
            notes="[BE_PROTECTED: TP1 reached; SL moved to 150.01]",
        )
    )

    mock_quote = MagicMock()
    mock_quote.quote.lastPrice = 150.00  # Pulls back to hit BE stop loss
    mock_quote.quote.bidAsk.bid = 149.99
    mock_quote.quote.bidAsk.ask = 150.01
    mock_quote.quote.bidAsk.spread = 0.02

    with patch.object(provider_manager, "get_market_quote", return_value=mock_quote):
        summary = resolver.resolve_signals()

    resolved_trade = trade_journal_repository.get_trade(trade.id)
    assert resolved_trade is not None
    assert resolved_trade.status.upper() == "CLOSED"
    assert resolved_trade.result.upper() == "BREAKEVEN"
    assert resolved_trade.realizedRMultiple == 0.75
