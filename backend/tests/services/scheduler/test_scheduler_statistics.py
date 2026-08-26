"""
Unit tests for SchedulerStatistics.
"""
import pytest
import time
from datetime import datetime, timezone, timedelta
from app.services.scheduler.scheduler_statistics import SchedulerStatistics


@pytest.fixture
def scheduler_statistics():
    """Create a SchedulerStatistics instance for testing."""
    return SchedulerStatistics()


def test_scheduler_statistics_initialization(scheduler_statistics):
    """Test that SchedulerStatistics initializes correctly."""
    assert scheduler_statistics.total_scans == 0
    assert scheduler_statistics.successful_scans == 0
    assert scheduler_statistics.failed_scans == 0
    assert scheduler_statistics.last_scan_time is None
    assert scheduler_statistics.consecutive_failures == 0
    assert scheduler_statistics.signals_generated == 0
    assert scheduler_statistics.signals_approved == 0
    assert scheduler_statistics.signals_rejected == 0
    assert scheduler_statistics.duplicates_prevented == 0
    assert scheduler_statistics.signals_expired == 0


def test_record_scan_start(scheduler_statistics):
    """Test recording scan start time."""
    start_ms = scheduler_statistics.record_scan_start()
    assert start_ms > 0
    assert isinstance(start_ms, float)


def test_record_scan_end_success(scheduler_statistics):
    """Test recording successful scan end."""
    start_ms = scheduler_statistics.record_scan_start()
    time.sleep(0.01)  # Small delay
    scheduler_statistics.record_scan_end(start_ms, success=True)
    
    assert scheduler_statistics.total_scans == 1
    assert scheduler_statistics.successful_scans == 1
    assert scheduler_statistics.failed_scans == 0
    assert scheduler_statistics.consecutive_failures == 0
    assert scheduler_statistics.last_scan_time is not None
    assert scheduler_statistics.last_successful_scan_time is not None
    assert scheduler_statistics.total_scan_time_ms > 0


def test_record_scan_end_failure(scheduler_statistics):
    """Test recording failed scan end."""
    start_ms = scheduler_statistics.record_scan_start()
    scheduler_statistics.record_scan_end(start_ms, success=False)
    
    assert scheduler_statistics.total_scans == 1
    assert scheduler_statistics.successful_scans == 0
    assert scheduler_statistics.failed_scans == 1
    assert scheduler_statistics.consecutive_failures == 1
    assert scheduler_statistics.last_scan_time is not None
    assert scheduler_statistics.last_failed_scan_time is not None


def test_consecutive_failures_tracking(scheduler_statistics):
    """Test consecutive failures tracking."""
    start_ms = scheduler_statistics.record_scan_start()
    
    for _ in range(3):
        scheduler_statistics.record_scan_end(start_ms, success=False)
    
    assert scheduler_statistics.consecutive_failures == 3
    assert scheduler_statistics.max_consecutive_failures == 3


def test_consecutive_failures_reset_on_success(scheduler_statistics):
    """Test that consecutive failures reset on success."""
    start_ms = scheduler_statistics.record_scan_start()
    
    scheduler_statistics.record_scan_end(start_ms, success=False)
    scheduler_statistics.record_scan_end(start_ms, success=False)
    scheduler_statistics.record_scan_end(start_ms, success=True)
    
    assert scheduler_statistics.consecutive_failures == 0


def test_record_signal_generated(scheduler_statistics):
    """Test recording signal generation."""
    generation_time_ms = 100.5
    scheduler_statistics.record_signal_generated("XAUUSD", "H1", generation_time_ms)
    
    assert scheduler_statistics.signals_generated == 1
    assert scheduler_statistics.total_generation_time_ms == generation_time_ms
    assert scheduler_statistics.min_generation_time_ms == generation_time_ms
    assert scheduler_statistics.max_generation_time_ms == generation_time_ms


def test_record_signal_approved(scheduler_statistics):
    """Test recording signal approval."""
    scheduler_statistics.record_signal_approved("XAUUSD", "H1")
    
    assert scheduler_statistics.signals_approved == 1


def test_record_signal_rejected(scheduler_statistics):
    """Test recording signal rejection."""
    scheduler_statistics.record_signal_rejected("XAUUSD", "H1", "Low confidence")
    
    assert scheduler_statistics.signals_rejected == 1


def test_record_duplicate_prevented(scheduler_statistics):
    """Test recording duplicate prevention."""
    scheduler_statistics.record_duplicate_prevented()
    
    assert scheduler_statistics.duplicates_prevented == 1


def test_record_signal_expired(scheduler_statistics):
    """Test recording signal expiration."""
    scheduler_statistics.record_signal_expired()
    
    assert scheduler_statistics.signals_expired == 1


def test_record_cache_hit(scheduler_statistics):
    """Test recording cache hit."""
    scheduler_statistics.record_cache_hit()
    
    assert scheduler_statistics.cache_hits == 1


def test_record_cache_miss(scheduler_statistics):
    """Test recording cache miss."""
    scheduler_statistics.record_cache_miss()
    
    assert scheduler_statistics.cache_misses == 1


def test_get_summary(scheduler_statistics):
    """Test getting statistics summary."""
    start_ms = scheduler_statistics.record_scan_start()
    scheduler_statistics.record_scan_end(start_ms, success=True)
    scheduler_statistics.record_signal_generated("XAUUSD", "H1", 100.0)
    scheduler_statistics.record_signal_approved("XAUUSD", "H1")
    scheduler_statistics.record_cache_hit()
    scheduler_statistics.record_cache_hit()
    scheduler_statistics.record_cache_miss()
    
    summary = scheduler_statistics.get_summary()
    
    assert summary["total_scans"] == 1
    assert summary["successful_scans"] == 1
    assert summary["signals_generated"] == 1
    assert summary["signals_approved"] == 1
    assert summary["approval_rate"] == 1.0
    assert summary["cache_hit_rate"] == 0.6666666666666666
    assert summary["uptime_seconds"] > 0
    assert "symbol_stats" in summary
    assert "timeframe_stats" in summary


def test_reset_statistics(scheduler_statistics):
    """Test resetting all statistics."""
    start_ms = scheduler_statistics.record_scan_start()
    scheduler_statistics.record_scan_end(start_ms, success=True)
    scheduler_statistics.record_signal_generated("XAUUSD", "H1", 100.0)
    scheduler_statistics.record_signal_approved("XAUUSD", "H1")
    
    scheduler_statistics.reset()
    
    assert scheduler_statistics.total_scans == 0
    assert scheduler_statistics.successful_scans == 0
    assert scheduler_statistics.signals_generated == 0
    assert scheduler_statistics.signals_approved == 0
    assert scheduler_statistics.last_scan_time is None
    assert scheduler_statistics.start_time is not None


def test_per_symbol_statistics(scheduler_statistics):
    """Test per-symbol statistics tracking."""
    scheduler_statistics.record_signal_generated("XAUUSD", "H1", 100.0)
    scheduler_statistics.record_signal_approved("XAUUSD", "H1")
    scheduler_statistics.record_signal_generated("GBPUSD", "H1", 100.0)
    scheduler_statistics.record_signal_rejected("GBPUSD", "H1", "Low confidence")
    
    summary = scheduler_statistics.get_summary()
    
    assert summary["symbol_stats"]["XAUUSD"]["generated"] == 1
    assert summary["symbol_stats"]["XAUUSD"]["approved"] == 1
    assert summary["symbol_stats"]["GBPUSD"]["generated"] == 1
    assert summary["symbol_stats"]["GBPUSD"]["rejected"] == 1


def test_per_timeframe_statistics(scheduler_statistics):
    """Test per-timeframe statistics tracking."""
    scheduler_statistics.record_signal_generated("XAUUSD", "H1", 100.0)
    scheduler_statistics.record_signal_approved("XAUUSD", "H1")
    scheduler_statistics.record_signal_generated("XAUUSD", "H4", 100.0)
    scheduler_statistics.record_signal_rejected("XAUUSD", "H4", "Low confidence")
    
    summary = scheduler_statistics.get_summary()
    
    assert summary["timeframe_stats"]["H1"]["generated"] == 1
    assert summary["timeframe_stats"]["H1"]["approved"] == 1
    assert summary["timeframe_stats"]["H4"]["generated"] == 1
    assert summary["timeframe_stats"]["H4"]["rejected"] == 1


def test_avg_scan_time_calculation(scheduler_statistics):
    """Test average scan time calculation."""
    start_ms = scheduler_statistics.record_scan_start()
    time.sleep(0.01)
    scheduler_statistics.record_scan_end(start_ms, success=True)
    
    start_ms = scheduler_statistics.record_scan_start()
    time.sleep(0.02)
    scheduler_statistics.record_scan_end(start_ms, success=True)
    
    summary = scheduler_statistics.get_summary()
    
    assert summary["avg_scan_time_ms"] > 0
    assert summary["min_scan_time_ms"] > 0
    assert summary["max_scan_time_ms"] > 0


def test_approval_rate_calculation(scheduler_statistics):
    """Test approval rate calculation."""
    scheduler_statistics.record_signal_generated("XAUUSD", "H1", 100.0)
    scheduler_statistics.record_signal_approved("XAUUSD", "H1")
    scheduler_statistics.record_signal_generated("XAUUSD", "H1", 100.0)
    scheduler_statistics.record_signal_rejected("XAUUSD", "H1", "Low confidence")
    
    summary = scheduler_statistics.get_summary()
    
    assert summary["approval_rate"] == 0.5


def test_cache_hit_rate_calculation(scheduler_statistics):
    """Test cache hit rate calculation."""
    scheduler_statistics.record_cache_hit()
    scheduler_statistics.record_cache_hit()
    scheduler_statistics.record_cache_hit()
    scheduler_statistics.record_cache_miss()
    
    summary = scheduler_statistics.get_summary()
    
    assert summary["cache_hit_rate"] == 0.75
