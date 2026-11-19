"""
Falcon Order Execution Service
Manages order queue, MT5 bridge synchronization, trade journaling, and execution alerts.
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from app.core.repository.trade_journal_repository import trade_journal_repository
from app.core.services.signal_authorization_service import signal_authorization_service
from app.schemas.capital_guardian import ProposedTradeInput
from app.schemas.execution_order import (
    ExecutionOrderCreate,
    ExecutionOrderItem,
    ExecutionOrderConfirm,
    ExecutionSettings,
    OrderStatus,
    OrderAction,
)
from app.schemas.trade_journal import TradeJournalCreate
from app.services.alerts.telegram_alert_service import telegram_alert_service

logger = logging.getLogger("falcon.execution.service")


class OrderExecutionService:
    """Central service managing order lifecycle between Falcon Cloud and MT5."""

    def __init__(self):
        self._orders: Dict[str, ExecutionOrderItem] = {}
        self.settings = ExecutionSettings()
        self._execution_metrics: List[Dict[str, Any]] = []

    def create_order(self, order_in: ExecutionOrderCreate) -> ExecutionOrderItem:
        """Create and queue a new execution order."""
        # Safety enforcement
        lot_size = max(0.01, min(self.settings.max_lot_size, order_in.lot_size))
        order_id = f"ord-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        # Capital Guardian Safety Gate: verify existing reservation or authorize now
        existing_res = None
        if order_in.signal_id is not None:
            existing_trades = trade_journal_repository.list_trades()
            existing_res = next(
                (
                    t for t in existing_trades
                    if t.signalId == order_in.signal_id
                    and (t.status or "").upper() in ("PENDING", "OPEN", "FILLED")
                    and t.closeDate is None
                ),
                None
            )

        if existing_res is None:
            proposal = ProposedTradeInput(
                symbol=order_in.symbol.upper(),
                direction=order_in.action.value.upper(),
                entryPrice=Decimal(str(order_in.entry_price)),
                stopLoss=Decimal(str(order_in.stop_loss)),
                takeProfit=Decimal(str(order_in.take_profit)),
                lotSize=Decimal(str(lot_size)),
            )
            decision, res_item = signal_authorization_service.authorize_and_reserve(
                proposal=proposal,
                signal_id=order_in.signal_id,
                strategy_id=order_in.strategy_name,
                notes=f"Order {order_id} execution reservation",
            )
            if not decision.allowed:
                logger.warning(f"Order {order_id} rejected by Capital Guardian: {decision.reason}")
                raise ValueError(f"Order rejected by Capital Guardian: {decision.reason}")

        item = ExecutionOrderItem(
            order_id=order_id,
            signal_id=order_in.signal_id,
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

        # Phase 5F / Stage 3 Safety Gate: Authoritative Execution Mode Guard
        from app.core.config import settings
        from app.core.execution.execution_mode_guard import execution_mode_guard

        # Hard fail-closed: If not affirmatively authorized as LIVE, broker dispatch is strictly blocked
        if not execution_mode_guard.is_live_authorized():
            logger.info(
                f"Order {order_id} recorded for decision-support tracking. "
                "Automated broker order placement is strictly disabled in PAPER/SHADOW mode."
            )
        elif getattr(settings, "OANDA_AUTO_EXECUTE", False):
            try:
                from app.core.providers import _oanda_provider
                if _oanda_provider and _oanda_provider.configured:
                    sym_u = item.symbol.upper()
                    if "XAU" in sym_u or "GOLD" in sym_u:
                        mult = 100
                    elif "XAG" in sym_u:
                        mult = 5000
                    elif sym_u in ("NAS100", "US30", "SPX500", "BTCUSD", "ETHUSD"):
                        mult = 1
                    else:
                        mult = 100000
                    units_val = int(round(float(item.lot_size) * mult))
                    if item.action == OrderAction.SELL:
                        units_val = -units_val

                    raw_ot = item.order_type.value.upper() if hasattr(item.order_type, "value") else str(item.order_type).upper()
                    if raw_ot in ("LIMIT", "PENDING"):
                        o_type = "LIMIT"
                    elif raw_ot == "STOP":
                        o_type = "STOP"
                    else:
                        o_type = "MARKET"
                    oanda_resp = _oanda_provider.create_order(
                        symbol=item.symbol,
                        units=units_val,
                        order_type=o_type,
                        price=item.entry_price,
                        stop_loss=item.stop_loss,
                        take_profit=item.take_profit,
                        client_tag=item.order_id,
                    )
                    if oanda_resp:
                        tx = oanda_resp.get("orderCreateTransaction") or oanda_resp.get("orderFillTransaction") or {}
                        tx_id = tx.get("id")
                        if tx_id:
                            item.ticket_number = int(tx_id)
                            item.broker_name = "OANDA"
                            logger.info(f"OANDA order placed natively: Ticket #{tx_id}")
            except Exception as ex:
                logger.warning(f"Error dispatching native OANDA order for {order_id}: {ex}")
        else:
            logger.info(
                f"Order {order_id} recorded for decision-support tracking. "
                "Automated broker order placement is strictly disabled."
            )


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
        if hasattr(telegram_alert_service, "dispatch_raw_message"):
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

        # Record Latency and Slippage Metrics
        latency_ms = (now - order.created_at).total_seconds() * 1000.0
        slippage = confirm_in.slippage_pips or 0.0
        self._execution_metrics.append({
            "order_id": order_id,
            "symbol": order.symbol,
            "latency_ms": round(latency_ms, 2),
            "slippage_pips": round(slippage, 2),
            "executed_at": now.isoformat(),
            "broker_name": confirm_in.broker_name or "MT5/OANDA",
        })

        logger.info(f"Order {order_id} executed. Latency: {latency_ms:.1f}ms, Slippage: {slippage:.1f} pips")

        # Update existing reservation or record into Falcon Trade Journal
        try:
            from app.schemas.trade_journal import TradeJournalUpdate
            existing_trades = trade_journal_repository.list_trades()
            existing_res = None
            if order.signal_id is not None:
                existing_res = next(
                    (
                        t for t in existing_trades
                        if t.signalId == order.signal_id
                        and (t.status or "").upper() in ("PENDING", "OPEN", "FILLED")
                        and t.closeDate is None
                    ),
                    None
                )
            if existing_res is None:
                existing_res = next(
                    (
                        t for t in existing_trades
                        if t.symbol.upper() == order.symbol.upper()
                        and t.direction.upper() == order.action.value.upper()
                        and (t.status or "").upper() == "PENDING"
                        and t.closeDate is None
                    ),
                    None
                )

            if existing_res is not None:
                ticket_note = f"Auto-executed via MT5 Bridge. Ticket #{confirm_in.ticket_number}"
                merged_notes = f"{existing_res.notes} | {ticket_note}" if existing_res.notes else ticket_note
                update_payload = TradeJournalUpdate(
                    status="OPEN",
                    result="OPEN",
                    fillPrice=confirm_in.fill_price,
                    fillTime=now,
                    peakPrice=confirm_in.fill_price,
                    troughPrice=confirm_in.fill_price,
                    initialMonetaryRisk=existing_res.initialMonetaryRisk,
                    notes=merged_notes,
                )
                trade_journal_repository.update_trade(existing_res.id, update_payload)
                logger.info(f"Updated reservation #{existing_res.id} to OPEN for order {order_id}")
            else:
                journal_entry = TradeJournalCreate(
                    signalId=order.signal_id,
                    strategyId=order.strategy_name,
                    symbol=order.symbol,
                    direction=order.action.value,
                    entryPrice=confirm_in.fill_price,
                    exitPrice=None,
                    stopLoss=order.stop_loss,
                    takeProfit=order.take_profit,
                    timeframe="M15",
                    marketSession="Live MT5",
                    tradeDate=now,
                    closeDate=None,
                    status="OPEN",
                    result="OPEN",
                    profitLoss=0.0,
                    riskReward=0.0,
                    confidence=order.confidence,
                    reasonForEntry=f"Auto-executed via MT5 Bridge. Ticket #{confirm_in.ticket_number}",
                    notes=f"Auto-executed via MT5 Bridge. Ticket #{confirm_in.ticket_number}",
                    fillPrice=confirm_in.fill_price,
                    fillTime=now,
                    peakPrice=confirm_in.fill_price,
                    troughPrice=confirm_in.fill_price,
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
            f"⚡ <b>Slippage:</b> {(confirm_in.slippage_pips or 0.0):.1f} pips\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <i>Logged to Falcon Trade Journal</i>"
        )
        if hasattr(telegram_alert_service, "dispatch_raw_message"):
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

        try:
            from app.schemas.trade_journal import TradeJournalUpdate
            existing_trades = trade_journal_repository.list_trades()
            matching_pending = None
            if order.signal_id is not None:
                matching_pending = next(
                    (
                        t for t in existing_trades
                        if t.signalId == order.signal_id
                        and (t.status or "").upper() == "PENDING"
                        and t.closeDate is None
                    ),
                    None,
                )
            if matching_pending is None:
                matching_pending = next(
                    (
                        t for t in existing_trades
                        if t.symbol.upper() == order.symbol.upper()
                        and t.direction.upper() == order.action.value.upper()
                        and (t.status or "").upper() == "PENDING"
                        and t.closeDate is None
                    ),
                    None,
                )
            if matching_pending is not None:
                fail_note = f"Order {order_id} failed: {reason}"
                merged_notes = f"{matching_pending.notes} | {fail_note}" if matching_pending.notes else fail_note
                trade_journal_repository.update_trade(
                    matching_pending.id,
                    TradeJournalUpdate(
                        status="INVALIDATED",
                        result="INVALIDATED",
                        closeDate=datetime.now(timezone.utc),
                        notes=merged_notes,
                    ),
                )
        except Exception as e:
            logger.warning(f"Could not update journal entry on failed order {order_id}: {e}")

        msg = (
            f"❌ <b>MT5 ORDER FAILED</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Asset:</b> <code>{order.symbol}</code>\n"
            f"⚠️ <b>Reason:</b> {reason}\n"
            f"🕒 <i>Check MT5 terminal logs</i>"
        )
        if hasattr(telegram_alert_service, "dispatch_raw_message"):
            telegram_alert_service.dispatch_raw_message(msg)

        return order

    def get_execution_latency_metrics(self) -> Dict[str, Any]:
        """Aggregate execution latency and slippage analytics."""
        if not self._execution_metrics:
            return {
                "total_orders": 0,
                "avg_latency_ms": 0.0,
                "max_latency_ms": 0.0,
                "avg_slippage_pips": 0.0,
                "broker_status": "EXCELLENT",
                "recent_metrics": [],
            }
        latencies = [m["latency_ms"] for m in self._execution_metrics]
        slippages = [m["slippage_pips"] for m in self._execution_metrics]
        avg_lat = sum(latencies) / len(latencies)
        avg_slip = sum(slippages) / len(slippages)
        return {
            "total_orders": len(self._execution_metrics),
            "avg_latency_ms": round(avg_lat, 2),
            "max_latency_ms": round(max(latencies), 2),
            "avg_slippage_pips": round(avg_slip, 2),
            "broker_status": "EXCELLENT" if avg_lat < 250 else "NORMAL" if avg_lat < 1000 else "DEGRADED",
            "recent_metrics": self._execution_metrics[-10:],
        }


order_execution_service = OrderExecutionService()
