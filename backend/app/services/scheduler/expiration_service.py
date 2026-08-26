"""
Falcon Signal Expiration Service

Automatically expires old signals based on their expiration time.
Runs periodically to update signal status from ACTIVE to EXPIRED.
"""
from datetime import datetime, timezone, timedelta
from typing import List
from app.core.scheduler_config import scheduler_config
from app.schemas.signal_models import TradeSetup


class ExpirationService:
    """Manages automatic expiration of trading signals."""
    
    def __init__(self):
        """Initialize the expiration service with configuration."""
        self.auto_expire = scheduler_config.AUTO_EXPIRE
        self.expiration_hours = scheduler_config.SIGNAL_EXPIRATION_HOURS
    
    def should_expire(self, signal: TradeSetup) -> bool:
        """
        Check if a signal should be expired based on its expiration time.
        
        Args:
            signal: The signal to check
            
        Returns:
            True if the signal should be expired
        """
        if not self.auto_expire:
            return False
        
        # Check if signal has an explicit expiration time
        if signal.expiresAt:
            return signal.expiresAt < datetime.now(timezone.utc)
        
        # Otherwise, use configured expiration hours from generation time
        expiration_time = signal.generatedAt + timedelta(hours=self.expiration_hours)
        return expiration_time < datetime.now(timezone.utc)
    
    def expire_signal(self, signal: TradeSetup) -> TradeSetup:
        """
        Mark a signal as expired.
        
        Args:
            signal: The signal to expire
            
        Returns:
            The expired signal with updated status
        """
        # Create a copy with expired status
        expired_signal = TradeSetup(
            signalId=signal.signalId,
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            signalType=signal.signalType,
            entryPrice=signal.entryPrice,
            stopLoss=signal.stopLoss,
            takeProfit1=signal.takeProfit1,
            takeProfit2=signal.takeProfit2,
            takeProfit3=signal.takeProfit3,
            riskRewardRatio=signal.riskRewardRatio,
            confidence=signal.confidence,
            quality=signal.quality,
            expectedHoldTime=signal.expectedHoldTime,
            status="EXPIRED",
            decision=signal.decision,
            reasoning=signal.reasoning,
            warnings=signal.warnings,
            tradeManagement=signal.tradeManagement,
            generatedAt=signal.generatedAt,
            expiresAt=datetime.now(timezone.utc),
        )
        return expired_signal
    
    def find_expirable_signals(self, signals: List[TradeSetup]) -> List[TradeSetup]:
        """
        Find all signals that should be expired.
        
        Args:
            signals: List of signals to check
            
        Returns:
            List of signals that should be expired
        """
        if not self.auto_expire:
            return []
        
        expirable = []
        for signal in signals:
            if signal.status == "ACTIVE" and self.should_expire(signal):
                expirable.append(signal)
        return expirable
    
    def expire_signals(self, signals: List[TradeSetup]) -> List[TradeSetup]:
        """
        Expire all signals that should be expired.
        
        Args:
            signals: List of all signals
            
        Returns:
            Updated list of signals with expired ones marked
        """
        if not self.auto_expire:
            return signals
        
        expirable = self.find_expirable_signals(signals)
        if not expirable:
            return signals
        
        # Create updated list with expired signals
        updated_signals = []
        signal_ids_to_expire = {s.signalId for s in expirable}
        
        for signal in signals:
            if signal.signalId in signal_ids_to_expire:
                updated_signals.append(self.expire_signal(signal))
            else:
                updated_signals.append(signal)
        
        return updated_signals
    
    def get_expiration_stats(self, signals: List[TradeSetup]) -> dict:
        """
        Get statistics about signal expiration.
        
        Args:
            signals: List of signals to analyze
            
        Returns:
            Dictionary with expiration statistics
        """
        now = datetime.now(timezone.utc)
        
        active_count = sum(1 for s in signals if s.status == "ACTIVE" and not self.should_expire(s))
        expired_count = sum(1 for s in signals if s.status == "EXPIRED")
        
        expiring_soon = []
        for signal in signals:
            if signal.status == "ACTIVE":
                if signal.expiresAt:
                    time_until_expiry = (signal.expiresAt - now).total_seconds()
                    if time_until_expiry < 3600:  # Less than 1 hour
                        expiring_soon.append(signal)
                else:
                    expiration_time = signal.generatedAt + timedelta(hours=self.expiration_hours)
                    time_until_expiry = (expiration_time - now).total_seconds()
                    if time_until_expiry < 3600:
                        expiring_soon.append(signal)
        
        return {
            "active_signals": active_count,
            "expired_signals": expired_count,
            "expiring_soon_count": len(expiring_soon),
            "auto_expire_enabled": self.auto_expire,
            "expiration_hours": self.expiration_hours,
        }
