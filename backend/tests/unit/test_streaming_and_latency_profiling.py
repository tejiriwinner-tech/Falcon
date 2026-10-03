"""
Unit tests for OANDA Streaming Service, Local Candle Aggregator, and Latency Profiling.
"""
from datetime import datetime, timezone
import pytest

from app.core.providers.oanda_streaming_service import OandaStreamingService
from app.core.services.local_candle_aggregator import LocalCandleAggregator
from app.schemas.execution_order import (
    ExecutionOrderCreate,
    ExecutionOrderConfirm,
    OrderAction,
    OrderType,
)
from app.services.execution.order_execution_service import OrderExecutionService


def test_oanda_streaming_price_tick_dispatch():
    stream_svc = OandaStreamingService()
    received_ticks = []

    def mock_listener(symbol, bid, ask, last, ts):
        received_ticks.append((symbol, bid, ask, last))

    stream_svc.register_tick_listener(mock_listener)

    # Simulate raw OANDA PRICE message
    msg = {
        "type": "PRICE",
        "instrument": "GBP_USD",
        "bids": [{"price": "1.32500"}],
        "asks": [{"price": "1.32520"}],
    }

    stream_svc._process_price_tick(msg)

    latest = stream_svc.get_latest_tick("GBPUSD")
    assert latest is not None
    assert latest["symbol"] == "GBPUSD"
    assert latest["bid"] == 1.32500
    assert latest["ask"] == 1.32520
    assert latest["last"] == 1.32510
    assert latest["spread"] == 0.00020
    assert len(received_ticks) == 1
    assert received_ticks[0][0] == "GBPUSD"


def test_local_candle_aggregator_building_bars():
    agg = LocalCandleAggregator()
    now = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)

    # Tick 1: Open bar at 1.1000
    agg.on_tick("EURUSD", 1.1000, 1.1002, 1.1001, now)
    bar1 = agg.get_developing_bar("EURUSD", "15m")
    assert bar1 is not None
    assert bar1.open == 1.1001
    assert bar1.high == 1.1001
    assert bar1.low == 1.1001
    assert bar1.close == 1.1001
    assert bar1.volume == 1

    # Tick 2: High moves to 1.1010
    agg.on_tick("EURUSD", 1.1009, 1.1011, 1.1010, now)
    bar2 = agg.get_developing_bar("EURUSD", "15m")
    assert bar2.high == 1.1010
    assert bar2.close == 1.1010
    assert bar2.volume == 2

    # Tick 3: Low moves to 1.0990
    agg.on_tick("EURUSD", 1.0989, 1.0991, 1.0990, now)
    bar3 = agg.get_developing_bar("EURUSD", "15m")
    assert bar3.high == 1.1010
    assert bar3.low == 1.0990
    assert bar3.close == 1.0990
    assert bar3.volume == 3


def test_order_execution_latency_profiling():
    from unittest.mock import MagicMock, patch
    exec_svc = OrderExecutionService()

    order_in = ExecutionOrderCreate(
        symbol="EURUSD",
        action=OrderAction.BUY,
        lot_size=0.02,
        order_type=OrderType.LIMIT,
        entry_price=1.1000,
        stop_loss=1.0950,
        take_profit=1.1100,
    )
    with patch("app.services.alerts.telegram_alert_service.telegram_alert_service.dispatch_raw_message"), \
         patch("app.core.services.signal_authorization_service.signal_authorization_service.authorize_and_reserve") as mock_auth:
        mock_auth.return_value = (MagicMock(allowed=True), MagicMock())
        order = exec_svc.create_order(order_in)

        # Confirm execution with 0.3 pips slippage
        confirm_in = ExecutionOrderConfirm(
            ticket_number=888999,
            fill_price=1.10003,
            slippage_pips=0.3,
            broker_name="OANDA",
        )
        confirmed = exec_svc.confirm_execution(order.order_id, confirm_in)

    assert confirmed is not None
    assert confirmed.ticket_number == 888999
    assert confirmed.slippage_pips == 0.3

    metrics = exec_svc.get_execution_latency_metrics()
    assert metrics["total_orders"] >= 1
    assert metrics["avg_slippage_pips"] == 0.3
    assert "broker_status" in metrics
