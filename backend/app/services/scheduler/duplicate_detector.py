"""
Falcon Duplicate Detector

Prevents duplicate signals from being generated and stored.
Checks for existing signals with the same symbol, timeframe, direction,
and entry price within a configurable tolerance.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from app.core.scheduler_config import scheduler_config
from app.schemas.signal_models import TradeSetup


class DuplicateDetector:
    """Detects and prevents duplicate trading signals."""
    
    def __init__(self):
        """Initialize the duplicate detector with configuration."""
        self.entry_tolerance_pips = scheduler_config.DUPLICATE_ENTRY_TOLERANCE_PIPS
        self.time_window_minutes = scheduler_config.DUPLICATE_TIME_WINDOW_MINUTES
        self.allow_duplicates = scheduler_config.ALLOW_DUPLICATES
    
    def is_duplicate(
        self,
        new_signal: TradeSetup,
        existing_signals: List[TradeSetup]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if a new signal is a duplicate of any existing active signal.
        
        Args:
            new_signal: The new signal to check
            existing_signals: List of existing active signals to compare against
            
        Returns:
            Tuple of (is_duplicate, reason)
        """
        # If duplicates are allowed, always return False
        if self.allow_duplicates:
            return False, None
        
        # Check each existing signal
        for existing in existing_signals:
            if existing.status != "ACTIVE":
                continue
            
            # Check symbol match
            if existing.symbol != new_signal.symbol:
                continue
            
            # Check timeframe match
            if existing.timeframe != new_signal.timeframe:
                continue
            
            # Check direction match (BUY/SELL)
            if existing.signalType.upper() != new_signal.signalType.upper():
                continue
            
            # Check entry price tolerance
            if not self._is_entry_within_tolerance(new_signal.entryPrice, existing.entryPrice, new_signal.symbol):
                continue
            
            # Check time window
            if not self._is_within_time_window(new_signal.generatedAt, existing.generatedAt):
                continue
            
            # All checks passed - this is a duplicate
            reason = (
                f"Duplicate signal: {new_signal.symbol} {new_signal.timeframe} "
                f"{new_signal.signalType} at {new_signal.entryPrice} "
                f"(existing: {existing.signalId})"
            )
            return True, reason
        
        return False, None
    
    def _is_entry_within_tolerance(self, new_entry: float, existing_entry: float, symbol: str = "") -> bool:
        """
        Check if entry prices are within the configured tolerance.
        
        Args:
            new_entry: Entry price of new signal
            existing_entry: Entry price of existing signal
            symbol: Trading symbol for pip size calculation
            
        Returns:
            True if prices are within tolerance
        """
        sym = (symbol or "").upper()
        pip_size = 0.01 if "JPY" in sym else (0.10 if ("XAU" in sym or "GOLD" in sym) else 0.0001)
        price_diff = abs(new_entry - existing_entry)
        return price_diff <= self.entry_tolerance_pips * pip_size
    
    def _is_within_time_window(self, new_time: datetime, existing_time: datetime) -> bool:
        """
        Check if the new signal was generated within the configured time window
        of the existing signal.
        
        Args:
            new_time: Generation time of new signal
            existing_time: Generation time of existing signal
            
        Returns:
            True if within time window
        """
        time_diff = abs((new_time - existing_time).total_seconds())
        return time_diff <= (self.time_window_minutes * 60)
    
    def get_duplicate_count(
        self,
        symbol: str,
        timeframe: str,
        signal_type: str,
        existing_signals: List[TradeSetup]
    ) -> int:
        """
        Count how many similar signals already exist for a symbol/timeframe/type.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            signal_type: Signal type (BUY/SELL)
            existing_signals: List of existing signals
            
        Returns:
            Count of similar active signals
        """
        count = 0
        for signal in existing_signals:
            if signal.status != "ACTIVE":
                continue
            if signal.symbol == symbol and signal.timeframe == timeframe:
                if signal.signalType.upper() == signal_type.upper():
                    count += 1
        return count
    
    def would_exceed_limits(
        self,
        symbol: str,
        existing_signals: List[TradeSetup]
    ) -> tuple[bool, Optional[str]]:
        """
        Check if adding a new signal would exceed configured limits.
        
        Args:
            symbol: Trading symbol
            existing_signals: List of existing signals
            
        Returns:
            Tuple of (would_exceed, reason)
        """
        # Check per-symbol limit
        symbol_signals = [
            s for s in existing_signals 
            if s.symbol == symbol and s.status == "ACTIVE"
        ]
        
        if len(symbol_signals) >= scheduler_config.MAX_SIGNALS_PER_SYMBOL:
            reason = (
                f"Would exceed MAX_SIGNALS_PER_SYMBOL ({scheduler_config.MAX_SIGNALS_PER_SYMBOL}) "
                f"for {symbol} (currently {len(symbol_signals)})"
            )
            return True, reason
        
        # Check total active signals limit
        active_signals = [s for s in existing_signals if s.status == "ACTIVE"]
        
        if len(active_signals) >= scheduler_config.MAX_TOTAL_ACTIVE_SIGNALS:
            reason = (
                f"Would exceed MAX_TOTAL_ACTIVE_SIGNALS ({scheduler_config.MAX_TOTAL_ACTIVE_SIGNALS}) "
                f"(currently {len(active_signals)})"
            )
            return True, reason
        
        return False, None
