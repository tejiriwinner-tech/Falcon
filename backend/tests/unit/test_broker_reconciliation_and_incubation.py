"""
Unit tests for Broker State Reconciliation and Strategy Paper Incubation.
Verifies bidirectional sync with OANDA and auto-recovery of quarantined strategies.
"""
from datetime import datetime, timezone
import pytest
from unittest.mock import MagicMock

from app.core.analytics.regime_memory_engine import RegimeMemoryEngine, StrategyHealthStatus
from app.core.services.broker_reconciliation_service import BrokerReconciliationService
from app.schemas.trade_journal import TradeJournalItem


def test_broker_reconciliation_detects_external_close():
    # Mock OANDA provider returning no open trades (trade closed externally on broker)
    mock_provider = MagicMock()
    mock_provider.configured = True
    mock_provider.get_open_trades.return_value = []  # No open trades
    mock_provider.get_trade_details.return_value = {
        "id": "12345",
        "realizedPL": "25.50",
        "averageClosePrice": "1.3260",
    }

    # Mock active trade in journal
    active_trade = MagicMock(spec=TradeJournalItem)
    active_trade.id = 1
    active_trade.symbol = "GBPUSD"
    active_trade.direction = "BUY"
    active_trade.entryPrice = 1.3200
    active_trade.stopLoss = 1.3150
    active_trade.status = "OPEN"
    active_trade.closeDate = None
    active_trade.notes = "ticket:12345"

    mock_journal = MagicMock()
    mock_journal.list_trades.return_value = [active_trade]

    reconciler = BrokerReconciliationService(
        oanda_provider=mock_provider,
        journal_repo=mock_journal,
    )

    res = reconciler.reconcile_state()

    assert res["status"] == "SUCCESS"
    assert res["closed_synced"] == 1
    # Verify journal was updated to CLOSED and WON
    mock_journal.update_trade.assert_called_once()
    args, kwargs = mock_journal.update_trade.call_args
    update_payload = args[1]
    assert update_payload.status == "CLOSED"
    assert update_payload.result == "WON"
    assert update_payload.profitLoss == 25.50


def test_strategy_paper_incubation_auto_recovery():
    engine = RegimeMemoryEngine()
    strat_id = "test_incubating_strat"

    # Create historical losing streak (3 losses)
    now = datetime.now(timezone.utc)
    losing_history = [
        {"strategyId": strat_id, "result": "LOST", "profit_loss": -10.0, "status": "CLOSED", "close_date": now},
        {"strategyId": strat_id, "result": "LOST", "profit_loss": -10.0, "status": "CLOSED", "close_date": now},
        {"strategyId": strat_id, "result": "LOST", "profit_loss": -10.0, "status": "CLOSED", "close_date": now},
    ]

    # Without paper incubation, strategy is QUARANTINED_PAPER
    score_before = engine.evaluate_strategy_health(strat_id, trade_history=losing_history)
    assert score_before.health_status == StrategyHealthStatus.QUARANTINED_PAPER
    assert score_before.recommended_weight == 0.0

    # Record 5 winning paper incubation trades
    for i in range(5):
        engine.record_paper_incubation_trade(strat_id, "WON", profit_loss=15.0)

    # After probationary paper recovery (5 wins >= 50%), strategy recovers to HEALTHY
    score_after = engine.evaluate_strategy_health(strat_id, trade_history=losing_history)
    assert score_after.health_status == StrategyHealthStatus.HEALTHY
    assert score_after.recommended_weight == 1.0
    assert "Auto-recovered from paper incubation" in score_after.rationale
