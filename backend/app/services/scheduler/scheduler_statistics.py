"""
Falcon Scheduler Statistics

Tracks and reports statistics about scheduler performance and signal generation.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from collections import defaultdict
import time


class SchedulerStatistics:
    """Tracks scheduler performance metrics."""
    
    def __init__(self):
        """Initialize scheduler statistics tracking."""
        # Scan statistics
        self.total_scans = 0
        self.successful_scans = 0
        self.failed_scans = 0
        self.last_scan_time: Optional[datetime] = None
        self.last_successful_scan_time: Optional[datetime] = None
        self.last_failed_scan_time: Optional[datetime] = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 0
        
        # Signal generation statistics
        self.signals_generated = 0
        self.signals_approved = 0
        self.signals_rejected = 0
        self.duplicates_prevented = 0
        self.signals_expired = 0
        
        # Performance statistics
        self.total_scan_time_ms = 0
        self.total_generation_time_ms = 0
        self.min_scan_time_ms: Optional[float] = None
        self.max_scan_time_ms: Optional[float] = None
        self.min_generation_time_ms: Optional[float] = None
        self.max_generation_time_ms: Optional[float] = None
        
        # Per-symbol statistics
        self.symbol_stats = defaultdict(lambda: {
            "scans": 0,
            "generated": 0,
            "approved": 0,
            "rejected": 0,
        })
        
        # Per-timeframe statistics
        self.timeframe_stats = defaultdict(lambda: {
            "scans": 0,
            "generated": 0,
            "approved": 0,
            "rejected": 0,
        })
        
        # Cache statistics
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Start time
        self.start_time = datetime.now(timezone.utc)
    
    def record_scan_start(self) -> float:
        """Record the start of a scan cycle. Returns start timestamp."""
        return time.time() * 1000  # milliseconds
    
    def record_scan_end(self, start_time_ms: float, success: bool):
        """
        Record the end of a scan cycle.
        
        Args:
            start_time_ms: Start timestamp in milliseconds
            success: Whether the scan was successful
        """
        end_time_ms = time.time() * 1000
        scan_duration_ms = end_time_ms - start_time_ms
        
        self.total_scans += 1
        self.last_scan_time = datetime.now(timezone.utc)
        
        if success:
            self.successful_scans += 1
            self.last_successful_scan_time = datetime.now(timezone.utc)
            self.consecutive_failures = 0
            
            # Update scan time statistics
            self.total_scan_time_ms += scan_duration_ms
            if self.min_scan_time_ms is None or scan_duration_ms < self.min_scan_time_ms:
                self.min_scan_time_ms = scan_duration_ms
            if self.max_scan_time_ms is None or scan_duration_ms > self.max_scan_time_ms:
                self.max_scan_time_ms = scan_duration_ms
        else:
            self.failed_scans += 1
            self.last_failed_scan_time = datetime.now(timezone.utc)
            self.consecutive_failures += 1
            if self.consecutive_failures > self.max_consecutive_failures:
                self.max_consecutive_failures = self.consecutive_failures
    
    def record_signal_generated(self, symbol: str, timeframe: str, generation_time_ms: float):
        """
        Record a signal generation event.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            generation_time_ms: Time taken to generate signal in milliseconds
        """
        self.signals_generated += 1
        self.total_generation_time_ms += generation_time_ms
        
        if self.min_generation_time_ms is None or generation_time_ms < self.min_generation_time_ms:
            self.min_generation_time_ms = generation_time_ms
        if self.max_generation_time_ms is None or generation_time_ms > self.max_generation_time_ms:
            self.max_generation_time_ms = generation_time_ms
        
        # Update per-symbol stats
        self.symbol_stats[symbol]["generated"] += 1
        
        # Update per-timeframe stats
        self.timeframe_stats[timeframe]["generated"] += 1
    
    def record_signal_approved(self, symbol: str, timeframe: str):
        """
        Record a signal approval event.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
        """
        self.signals_approved += 1
        self.symbol_stats[symbol]["approved"] += 1
        self.timeframe_stats[timeframe]["approved"] += 1
    
    def record_signal_rejected(self, symbol: str, timeframe: str, reason: str):
        """
        Record a signal rejection event.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            reason: Rejection reason
        """
        self.signals_rejected += 1
        self.symbol_stats[symbol]["rejected"] += 1
        self.timeframe_stats[timeframe]["rejected"] += 1
    
    def record_duplicate_prevented(self):
        """Record a duplicate signal prevention."""
        self.duplicates_prevented += 1
    
    def record_signal_expired(self):
        """Record a signal expiration."""
        self.signals_expired += 1
    
    def record_cache_hit(self):
        """Record a cache hit."""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record a cache miss."""
        self.cache_misses += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all scheduler statistics.
        
        Returns:
            Dictionary with all statistics
        """
        uptime_seconds = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        avg_scan_time_ms = self.total_scan_time_ms / self.successful_scans if self.successful_scans > 0 else 0
        avg_generation_time_ms = self.total_generation_time_ms / self.signals_generated if self.signals_generated > 0 else 0
        cache_hit_rate = self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0
        
        return {
            # Scan statistics
            "total_scans": self.total_scans,
            "successful_scans": self.successful_scans,
            "failed_scans": self.failed_scans,
            "consecutive_failures": self.consecutive_failures,
            "max_consecutive_failures": self.max_consecutive_failures,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "last_successful_scan_time": self.last_successful_scan_time.isoformat() if self.last_successful_scan_time else None,
            "last_failed_scan_time": self.last_failed_scan_time.isoformat() if self.last_failed_scan_time else None,
            
            # Signal statistics
            "signals_generated": self.signals_generated,
            "signals_approved": self.signals_approved,
            "signals_rejected": self.signals_rejected,
            "duplicates_prevented": self.duplicates_prevented,
            "signals_expired": self.signals_expired,
            "approval_rate": self.signals_approved / self.signals_generated if self.signals_generated > 0 else 0,
            
            # Performance statistics
            "avg_scan_time_ms": avg_scan_time_ms,
            "min_scan_time_ms": self.min_scan_time_ms,
            "max_scan_time_ms": self.max_scan_time_ms,
            "avg_generation_time_ms": avg_generation_time_ms,
            "min_generation_time_ms": self.min_generation_time_ms,
            "max_generation_time_ms": self.max_generation_time_ms,
            
            # Cache statistics
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": cache_hit_rate,
            
            # Uptime
            "uptime_seconds": uptime_seconds,
            "start_time": self.start_time.isoformat(),
            
            # Per-symbol statistics
            "symbol_stats": dict(self.symbol_stats),
            
            # Per-timeframe statistics
            "timeframe_stats": dict(self.timeframe_stats),
        }
    
    def reset(self):
        """Reset all statistics."""
        self.total_scans = 0
        self.successful_scans = 0
        self.failed_scans = 0
        self.last_scan_time = None
        self.last_successful_scan_time = None
        self.last_failed_scan_time = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 0
        
        self.signals_generated = 0
        self.signals_approved = 0
        self.signals_rejected = 0
        self.duplicates_prevented = 0
        self.signals_expired = 0
        
        self.total_scan_time_ms = 0
        self.total_generation_time_ms = 0
        self.min_scan_time_ms = None
        self.max_scan_time_ms = None
        self.min_generation_time_ms = None
        self.max_generation_time_ms = None
        
        self.symbol_stats.clear()
        self.timeframe_stats.clear()
        
        self.cache_hits = 0
        self.cache_misses = 0
        
        self.start_time = datetime.now(timezone.utc)
