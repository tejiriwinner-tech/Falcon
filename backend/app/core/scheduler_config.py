"""
Falcon Scheduler Configuration

Centralized configuration for the background signal scheduler.
All values are configurable and can be overridden via environment variables.
"""
import os
from typing import List


class SchedulerConfig:
    """Configuration for the background signal scheduler."""
    
    # Scan Configuration (15-second real-time scan cycle)
    SCAN_INTERVAL_SECONDS: int = int(os.getenv("FALCON_SCAN_INTERVAL", "15"))
    
    # Signal Limits
    MAX_SIGNALS_PER_SYMBOL: int = int(os.getenv("FALCON_MAX_SIGNALS_PER_SYMBOL", "3"))
    MAX_TOTAL_ACTIVE_SIGNALS: int = int(os.getenv("FALCON_MAX_TOTAL_ACTIVE_SIGNALS", "100"))
    
    # Expiration Configuration
    AUTO_EXPIRE: bool = os.getenv("FALCON_AUTO_EXPIRE", "true").lower() == "true"
    SIGNAL_EXPIRATION_HOURS: int = int(os.getenv("FALCON_SIGNAL_EXPIRATION_HOURS", "24"))
    
    # Duplicate Detection
    ALLOW_DUPLICATES: bool = os.getenv("FALCON_ALLOW_DUPLICATES", "false").lower() == "true"
    DUPLICATE_ENTRY_TOLERANCE_PIPS: float = float(os.getenv("FALCON_DUPLICATE_ENTRY_TOLERANCE", "5.0"))
    DUPLICATE_TIME_WINDOW_MINUTES: int = int(os.getenv("FALCON_DUPLICATE_TIME_WINDOW", "30"))
    
    # Markets to Monitor (6 Core Institutional Assets)
    MARKETS: List[str] = os.getenv("FALCON_MARKETS", "XAUUSD,GBPUSD,EURUSD,GBPJPY,USDJPY,AUDUSD").split(",")
    
    # Timeframes to Monitor
    TIMEFRAMES: List[str] = os.getenv("FALCON_TIMEFRAMES", "H4,H1,M15,M5").split(",")
    
    # Performance Configuration
    MAX_SCAN_TIME_SECONDS: int = int(os.getenv("FALCON_MAX_SCAN_TIME", "5"))
    ENABLE_PARALLEL_SCANS: bool = os.getenv("FALCON_PARALLEL_SCANS", "true").lower() == "true"
    
    # Health Configuration
    MAX_CONSECUTIVE_FAILURES: int = int(os.getenv("FALCON_MAX_CONSECUTIVE_FAILURES", "5"))
    HEALTH_CHECK_INTERVAL_SECONDS: int = int(os.getenv("FALCON_HEALTH_CHECK_INTERVAL", "300"))
    
    # Repository Configuration
    SIGNAL_DB_PATH: str = os.getenv("FALCON_SIGNAL_DB_PATH", "data/signals.db")
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration values."""
        if cls.SCAN_INTERVAL_SECONDS < 10:
            raise ValueError("SCAN_INTERVAL_SECONDS must be at least 10 seconds")
        if cls.MAX_SIGNALS_PER_SYMBOL < 1:
            raise ValueError("MAX_SIGNALS_PER_SYMBOL must be at least 1")
        if cls.MAX_TOTAL_ACTIVE_SIGNALS < 1:
            raise ValueError("MAX_TOTAL_ACTIVE_SIGNALS must be at least 1")
        if cls.DUPLICATE_ENTRY_TOLERANCE_PIPS < 0:
            raise ValueError("DUPLICATE_ENTRY_TOLERANCE_PIPS must be non-negative")
        if not cls.MARKETS:
            raise ValueError("MARKETS cannot be empty")
        if not cls.TIMEFRAMES:
            raise ValueError("TIMEFRAMES cannot be empty")
        return True
    
    @classmethod
    def get_total_combinations(cls) -> int:
        """Get total number of market/timeframe combinations."""
        return len(cls.MARKETS) * len(cls.TIMEFRAMES)


# Global configuration instance
scheduler_config = SchedulerConfig()
