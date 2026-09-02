"""
Falcon Order Execution Service
Manages order queue, MT5 bridge synchronization, trade journaling, and execution alerts.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.execution_order import (
    ExecutionOrderCreate,
    ExecutionOrderItem,
    ExecutionOrderConfirm,
    ExecutionSettings,
    OrderStatus,
    OrderAction,
)
from app.schemas.trade_journal import TradeJournalCreate
from app.core.repository.trade_journal_repository import trade_journal_repository
from app.services.alerts.telegram_alert_service import telegram_alert_service

logger = logging.getLogger("falcon.execution.service")


class OrderExecutionService:
    """Central service managing order lifecycle between Falcon Cloud and MT5."""

    def __init__(self):
        self._orders: Dict[str, ExecutionOrderItem] = {}
        self.settings = ExecutionSettings()

    def create_order(self, order_in: ExecutionOrderCreate) -> ExecutionOrderItem:
        """Create and queue a new execution order."""
        # Safety enforcement
        lot_size = max(0.01, min(self.settings.max_lot_size, order_in.lot_size))
        order_id = f"ord-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        item = ExecutionOrderItem(
            order_id=order_id,
            symbol=order_in.symbol.upper(),
            action=order_in.action,
            lot_size=lot_size,
            order_type=order_in.order_type,
            entry_price=order_in.entry_price,
            stop_loss=order_in.stop_loss,
            take_profit=order_in.take_profit,
            strategy_name=order_in.strategy_name or "Falcon Strategy",
            confidence=order_in.confidence or 80,
            magic_number=777888,
            comment=order_in.comment or "Falcon AI v4.2",
            status=OrderStatus.PENDING,
            created_at=now,
        )

        self._orders[order_id] = item
        logger.info(f"Order created and queued: {order_id} ({item.action.value} {item.lot_size} {item.symbol})")

        # Send Telegram notification about dispatched order
        mode_badge = "🧪 <b>DEMO MODE</b>" if self.settings.is_demo_mode else "⚠️ <b>LIVE MODE</b>"
        action_emoji = "🟢 BUY" if item.action == OrderAction.BUY else "🔴 SELL"
        msg = (
            f"⚡ <b>MT5 ORDER DISPATCHED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{mode_badge}\n"
            f"🎯 <b>Asset:</b> <code>{item.symbol}</code>\n"
            f"📊 <b>Action:</b> <b>{action_emoji}</b> | Lot: <code>{item.lot_size}</code>\n"
            f"💵 <b>Price Target:</b> <code>{item.entry_price}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{item.stop_loss}</code>\n"
            f"🎯 <b>Take Profit:</b> <code>{item.take_profit}</code>\n"
            f"🧠 <b>Strategy:</b> {item.strategy_name} ({item.confidence}%)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏳ <i>Waiting for MT5 Terminal Execution...</i>"
        )
        telegram_alert_service.dispatch_raw_message(msg)

        return item

    def get_pending_orders(self) -> List[ExecutionOrderItem]:
        """Return all orders waiting to be picked up by the MT5 EA or Bridge."""
        return [o for o in self._orders.values() if o.status == OrderStatus.PENDING]

    def get_order(self, order_id: str) -> Optional[ExecutionOrderItem]:
        return self._orders.get(order_id)

    def list_orders(self, limit: int = 50) -> List[ExecutionOrderItem]:
        """List orders ordered newest first."""
        sorted_orders = sorted(self._orders.values(), key=lambda x: x.created_at, reverse=True)
        return sorted_orders[:limit]

    def confirm_execution(self, order_id: str, confirm_in: ExecutionOrderConfirm) -> Optional[ExecutionOrderItem]:
        """Called by MT5 EA/Bridge when an order is filled."""
        order = self._orders.get(order_id)
        if not order:
            logger.warning(f"Confirm execution failed: Order {order_id} not found")
            return None

        now = datetime.now(timezone.utc)
        order.status = OrderStatus.EXECUTED
        order.ticket_number = confirm_in.ticket_number
        order.fill_price = confirm_in.fill_price
        order.slippage_pips = confirm_in.slippage_pips
        order.broker_name = confirm_in.broker_name
        order.executed_at = now

        logger.info(f"Order {order_id} executed by MT5. Ticket #{confirm_in.ticket_number} @ {confirm_in.fill_price}")

        # Automatically record into Falcon Trade Journal
        try:
            journal_entry = TradeJournalCreate(
                date=now.date(),
                instrument=order.symbol,
                direction=order.action.value,
                entryPrice=confirm_in.fill_price,
                exitPrice=None,
                positionSize=order.lot_size,
                stopLoss=order.stop_loss,
                takeProfit=order.take_profit,
                strategy=order.strategy_name,
                session="Live MT5",
                notes=f"Auto-executed via MT5 Bridge. Ticket #{confirm_in.ticket_number}",
                tags=["MT5", "Demo" if self.settings.is_demo_mode else "Live", order.strategy_name],
            )
            trade_journal_repository.create_trade(journal_entry)
        except Exception as e:
            logger.warning(f"Could not auto-journal executed trade {order_id}: {e}")

        # Send Telegram confirmation
        action_emoji = "🟢 BUY" if order.action == OrderAction.BUY else "🔴 SELL"
        msg = (
            f"✅ <b>MT5 TRADE EXECUTED</b> 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎫 <b>Ticket:</b> <code>#{confirm_in.ticket_number}</code>\n"
            f"🎯 <b>Asset:</b> <code>{order.symbol}</code>\n"
            f"📊 <b>Action:</b> <b>{action_emoji}</b> | Lot: <code>{order.lot_size}</code>\n"
            f"💵 <b>Fill Price:</b> <code>{confirm_in.fill_price}</code>\n"
            f"🛑 <b>Stop Loss:</b> <code>{order.stop_loss}</code>\n"
            f"🎯 <b>Take Profit:</b> <code>{order.take_profit}</code>\n"
            f"⚡ <b>Slippage:</b> {confirm_in.slippage_pips:.1f} pips\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <i>Logged to Falcon Trade Journal</i>"
        )
        telegram_alert_service.dispatch_raw_message(msg)

        return order

    def fail_order(self, order_id: str, reason: str) -> Optional[ExecutionOrderItem]:
        """Called when an order cannot be placed (e.g. market closed, insufficient margin)."""
        order = self._orders.get(order_id)
        if not order:
            return None

        order.status = OrderStatus.FAILED
        order.failure_reason = reason
        logger.warning(f"Order {order_id} failed in MT5: {reason}")

        msg = (
            f"❌ <b>MT5 ORDER FAILED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Asset:</b> <code>{order.symbol}</code>\n"
            f"⚠️ <b>Reason:</b> {reason}\n"
            f"🕒 <i>Check MT5 terminal logs</i>"
        )
        telegram_alert_service.dispatch_raw_message(msg)

        return order


order_execution_service = OrderExecutionService()
