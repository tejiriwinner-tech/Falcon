"""
Unit tests for SignalDispatcher.
"""
import pytest
from app.services.scheduler.signal_dispatcher import SignalDispatcher
from app.schemas.signal_models import TradeSetup
from datetime import datetime, timezone


@pytest.fixture
def signal_dispatcher():
    """Create a SignalDispatcher instance for testing."""
    return SignalDispatcher()


@pytest.fixture
def sample_signal():
    """Create a sample TradeSetup for testing."""
    return TradeSetup(
        signalId="test-1",
        symbol="XAUUSD",
        timeframe="H1",
        signalType="BUY",
        entryPrice=2350.50,
        stopLoss=2300.00,
        takeProfit1=2400.00,
        riskRewardRatio=1.5,
        confidence=88.0,
        quality="HIGH",
        expectedHoldTime="2-4 hours",
        status="ACTIVE",
        decision="STRONG BUY",
        reasoning=["Strong momentum"],
        warnings=["High volatility"],
        generatedAt=datetime.now(timezone.utc),
    )


def test_signal_dispatcher_initialization(signal_dispatcher):
    """Test that SignalDispatcher initializes correctly."""
    assert signal_dispatcher.dispatched_count == 0
    assert signal_dispatcher.failed_count == 0
    assert signal_dispatcher.last_dispatch_time is None


def test_dispatch_signal(signal_dispatcher, sample_signal):
    """Test dispatching a single signal."""
    result = signal_dispatcher.dispatch(sample_signal)
    assert result is True
    assert signal_dispatcher.dispatched_count == 1
    assert signal_dispatcher.failed_count == 0
    assert signal_dispatcher.last_dispatch_time is not None


def test_dispatch_batch(signal_dispatcher, sample_signal):
    """Test dispatching multiple signals in batch."""
    signals = [sample_signal] * 3
    result = signal_dispatcher.dispatch_batch(signals)
    
    assert result["total"] == 3
    assert result["success"] == 3
    assert result["failed"] == 0
    assert signal_dispatcher.dispatched_count == 3


def test_dispatch_batch_empty(signal_dispatcher):
    """Test dispatching empty batch."""
    result = signal_dispatcher.dispatch_batch([])
    assert result["total"] == 0
    assert result["success"] == 0
    assert result["failed"] == 0


def test_get_statistics(signal_dispatcher, sample_signal):
    """Test getting dispatcher statistics."""
    signal_dispatcher.dispatch(sample_signal)
    stats = signal_dispatcher.get_statistics()
    
    assert stats["total_dispatched"] == 1
    assert stats["total_failed"] == 0
    assert stats["last_dispatch_time"] is not None


def test_reset_statistics(signal_dispatcher, sample_signal):
    """Test resetting dispatcher statistics."""
    signal_dispatcher.dispatch(sample_signal)
    signal_dispatcher.reset_statistics()
    
    assert signal_dispatcher.dispatched_count == 0
    assert signal_dispatcher.failed_count == 0
    assert signal_dispatcher.last_dispatch_time is None


def test_get_statistics_before_dispatch(signal_dispatcher):
    """Test getting statistics before any dispatch."""
    stats = signal_dispatcher.get_statistics()
    
    assert stats["total_dispatched"] == 0
    assert stats["total_failed"] == 0
    assert stats["last_dispatch_time"] is None
