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
            
            # Future channels will be added here:
            # - WebSocket broadcast
            # - Push notifications
            # - Telegram bot
            # - Discord webhook
            # - Email alerts
            
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
