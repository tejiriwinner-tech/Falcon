"""
Unit tests for OANDA Native Broker Execution (Pending Limit/Stop Orders with attached SL/TP).
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest

from app.core.config import settings
from app.core.providers.oanda_provider import OandaProvider
from app.schemas.execution_order import ExecutionOrderCreate, OrderAction
from app.services.execution.order_execution_service import OrderExecutionService


def test_oanda_provider_create_order_payload():
    """Verify OandaProvider.create_order formats pending LIMIT order with stop loss and take profit."""
    provider = OandaProvider(
        api_key="mock_test_key_12345",
        account_id="101-004-12345678-001",
        base_url="https://api-fxpractice.oanda.com",
    )
    assert provider.configured

    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "orderCreateTransaction": {
            "id": "78912",
            "type": "LIMIT_ORDER",
            "instrument": "GBP_USD",
            "units": "10000",
            "price": "1.32170",
            "timeInForce": "GTC",
        }
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        result = provider.create_order(
            symbol="GBPUSD",
            units=10000,
            order_type="LIMIT",
            price=1.32170,
            stop_loss=1.31970,
            take_profit=1.32670,
            client_tag="ord-12345678",
        )

        assert result is not None
        assert "orderCreateTransaction" in result
        assert result["orderCreateTransaction"]["id"] == "78912"

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        payload = call_kwargs["json"]["order"]
        assert payload["instrument"] == "GBP_USD"
        assert payload["units"] == "10000"
        assert payload["type"] == "LIMIT"
        assert payload["price"] == "1.32170"
        assert payload["stopLossOnFill"]["price"] == "1.31970"
        assert payload["takeProfitOnFill"]["price"] == "1.32670"
        assert payload["clientExtensions"]["id"] == "ord-12345678"


def test_order_execution_service_auto_execute_toggle():
    """Verify that OrderExecutionService dispatches to OANDA when OANDA_AUTO_EXECUTE=True."""
    service = OrderExecutionService()

    order_in = ExecutionOrderCreate(
        signal_id=8801,
        symbol="GBPJPY",
        action=OrderAction.BUY,
        order_type="LIMIT",
        lot_size=0.10,
        entry_price=190.50,
        stop_loss=190.10,
        take_profit=191.50,
        strategy_name="Guppy Breakout",
        confidence=88,
    )

    mock_oanda_resp = {
        "orderCreateTransaction": {
            "id": "99123",
            "type": "LIMIT_ORDER",
        }
    }

    with patch.object(settings, "OANDA_AUTO_EXECUTE", True), \
         patch("app.core.providers._oanda_provider._api_key", "mock_key"), \
         patch("app.core.providers._oanda_provider._account_id", "mock_acc"), \
         patch("app.core.providers._oanda_provider.create_order", return_value=mock_oanda_resp) as mock_create, \
         patch("app.services.alerts.telegram_alert_service.telegram_alert_service.dispatch_raw_message"), \
         patch("app.core.services.signal_authorization_service.signal_authorization_service.authorize_and_reserve",
               return_value=(MagicMock(allowed=True), MagicMock())):

        order_item = service.create_order(order_in)
        assert order_item is not None
        assert order_item.ticket_number == 99123
        assert order_item.broker_name == "OANDA"
        mock_create.assert_called_once()
