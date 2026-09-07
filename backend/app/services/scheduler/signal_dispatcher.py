"""
Falcon Signal Dispatcher

Responsible for distributing approved signals to various channels.
Currently saves to repository. Future: WebSocket, Push Notifications, Telegram, Discord, Email.
"""
from typing import List, Optional
from datetime import datetime, timezone
from app.schemas.signal_models import TradeSetup
import logging

logger = logging.getLogger(__name__)


class SignalDispatcher:
    """Dispatches approved signals to various distribution channels."""
    
    def __init__(self):
        """Initialize the signal dispatcher."""
        self.dispatched_count = 0
        self.failed_count = 0
        self.last_dispatch_time: Optional[datetime] = None
    
    def dispatch(self, signal: TradeSetup) -> bool:
        """
        Dispatch a single approved signal.
        
        Args:
            signal: The approved signal to dispatch
            
        Returns:
            True if dispatch was successful
        """
        try:
            # For now, just log the signal (repository save happens elsewhere)
            logger.info(
                f"Dispatching signal: {signal.symbol} {signal.timeframe} "
                f"{signal.signalType} @ {signal.entryPrice} "
                f"(ID: {signal.signalId})"
            )
            
            # Dispatch to Telegram if configured
            type_str = str(getattr(signal, "signalType", "")).upper()
            if "BUY" in type_str or "SELL" in type_str:
                try:
                    from app.services.alerts.telegram_alert_service import telegram_alert_service
                    if telegram_alert_service.is_configured:
                        action_emoji = "🟢" if "BUY" in type_str else "🔴"
                        sym = str(signal.symbol).upper()
                        if "XAU" in sym:
                            fmt = ".2f"
                        elif "JPY" in sym:
                            fmt = ".3f"
                        else:
                            fmt = ".5f"
                        
                        entry_str = f"{signal.entryPrice:{fmt}}"
                        sl_str = f"{signal.stopLoss:{fmt}}"
                        risk = abs(signal.entryPrice - signal.stopLoss)
                        is_buy = "BUY" in type_str

                        # TP1 and TP2 derived from actual calculations
                        tp1_val = signal.takeProfit1 or (signal.entryPrice + 1.5 * risk if is_buy else signal.entryPrice - 1.5 * risk)
                        tp2_val = signal.takeProfit2 or (signal.entryPrice + 2.5 * risk if is_buy else signal.entryPrice - 2.5 * risk)
                        tp1_str = f"{tp1_val:{fmt}}"
                        tp2_str = f"{tp2_val:{fmt}}"

                        # Expiration formatting
                        valid_until_str = "Next bar close"
                        if hasattr(signal, "expiresAt") and signal.expiresAt:
                            if isinstance(signal.expiresAt, datetime):
                                valid_until_str = signal.expiresAt.strftime("%H:%M UTC")
                            else:
                                valid_until_str = str(signal.expiresAt)

                        reason_line = ""
                        if hasattr(signal, "reasoning") and signal.reasoning:
                            reason_line = f"🧠 <b>Trigger:</b> {signal.reasoning}\n"

                        msg = (
                            f"🦅 <b>FALCON TRADE SIGNAL ALERT</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📊 <b>Instrument:</b> <code>{signal.symbol}</code> ({signal.timeframe})\n"
                            f"{action_emoji} <b>Action:</b> <b>{type_str.replace('SIGNALTYPE.', '')} SETUP</b>\n"
                            f"🎯 <b>Confidence:</b> <b>{signal.confidence:.0f}%</b>\n"
                            f"{reason_line}"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💵 <b>Entry Price:</b> <code>{entry_str}</code>\n"
                            f"🛑 <b>Stop Loss:</b> <code>{sl_str}</code>\n"
                            f"🎯 <b>Take Profit 1:</b> <code>{tp1_str}</code> (Close 50% → Move SL to BE)\n"
                            f"🎯 <b>Take Profit 2:</b> <code>{tp2_str}</code> (Final Target)\n"
                            f"⚖️ <b>Risk/Reward:</b> 1:{signal.riskRewardRatio:.2f}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⏳ <b>Valid Until:</b> {valid_until_str}\n"
                            f"🌅 <b>Session Expiry:</b> 20:00 UTC+1 (19:00 UTC)\n"
                            f"🟢 <b>Status:</b> <b>ACTIVE</b>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"📱 <b>Tap-to-Copy for MT5 Mobile:</b>\n"
                            f"• SL: <code>{sl_str}</code>\n"
                            f"• TP1: <code>{tp1_str}</code>\n"
                            f"• TP2: <code>{tp2_str}</code>\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 <i>Tip: Tap any code block above to copy directly to MT5!</i>"
                        )
                        telegram_alert_service.dispatch_raw_message(msg)
                except Exception as ex:
                    logger.warning(f"Telegram dispatch failed for {signal.signalId}: {ex}")

            self.dispatched_count += 1
            self.last_dispatch_time = datetime.now(timezone.utc)
            return True
            
        except Exception as e:
            logger.error(f"Failed to dispatch signal {signal.signalId}: {e}")
            self.failed_count += 1
            return False
    
    def dispatch_batch(self, signals: List[TradeSetup]) -> dict:
        """
        Dispatch multiple signals in batch.
        
        Args:
            signals: List of signals to dispatch
            
        Returns:
            Dictionary with dispatch statistics
        """
        success_count = 0
        failure_count = 0
        
        for signal in signals:
            if self.dispatch(signal):
                success_count += 1
            else:
                failure_count += 1
        
        return {
            "total": len(signals),
            "success": success_count,
            "failed": failure_count,
        }
    
    def get_statistics(self) -> dict:
        """
        Get dispatcher statistics.
        
        Returns:
            Dictionary with dispatcher statistics
        """
        return {
            "total_dispatched": self.dispatched_count,
            "total_failed": self.failed_count,
            "last_dispatch_time": self.last_dispatch_time.isoformat() if self.last_dispatch_time else None,
        }
    
    def reset_statistics(self):
        """Reset dispatcher statistics."""
        self.dispatched_count = 0
        self.failed_count = 0
        self.last_dispatch_time = None
