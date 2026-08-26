"""
Unit tests for DuplicateDetector.
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.services.scheduler.duplicate_detector import DuplicateDetector
from app.schemas.signal_models import TradeSetup, TradeManagement


@pytest.fixture
def duplicate_detector():
    """Create a DuplicateDetector instance for testing."""
    return DuplicateDetector()


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
        reasoning=["Strong momentum", "Breakout"],
        warnings=["High volatility"],
        generatedAt=datetime.now(timezone.utc),
    )


def test_duplicate_detector_initialization(duplicate_detector):
    """Test that DuplicateDetector initializes correctly."""
    assert duplicate_detector.entry_tolerance_pips == 5.0
    assert duplicate_detector.time_window_minutes == 30
    assert duplicate_detector.allow_duplicates is False


def test_is_duplicate_identical_signal(duplicate_detector, sample_signal):
    """Test duplicate detection for identical signals."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
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
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is True
    assert "Duplicate signal" in reason


def test_is_duplicate_different_symbol(duplicate_detector, sample_signal):
    """Test that different symbols are not duplicates."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
        symbol="GBPUSD",
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
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is False
    assert reason is None


def test_is_duplicate_different_timeframe(duplicate_detector, sample_signal):
    """Test that different timeframes are not duplicates."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
        symbol="XAUUSD",
        timeframe="H4",
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
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is False
    assert reason is None


def test_is_duplicate_different_direction(duplicate_detector, sample_signal):
    """Test that different directions are not duplicates."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
        symbol="XAUUSD",
        timeframe="H1",
        signalType="SELL",
        entryPrice=2350.50,
        stopLoss=2400.00,
        takeProfit1=2300.00,
        riskRewardRatio=1.5,
        confidence=88.0,
        quality="HIGH",
        expectedHoldTime="2-4 hours",
        status="ACTIVE",
        decision="STRONG SELL",
        reasoning=["Strong momentum"],
        warnings=["High volatility"],
        generatedAt=datetime.now(timezone.utc),
    )
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is False
    assert reason is None


def test_is_duplicate_entry_tolerance(duplicate_detector, sample_signal):
    """Test that signals within entry tolerance are duplicates."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
        symbol="XAUUSD",
        timeframe="H1",
        signalType="BUY",
        entryPrice=2354.50,  # Within 5 pips tolerance
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
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is True


def test_is_duplicate_entry_outside_tolerance(duplicate_detector, sample_signal):
    """Test that signals outside entry tolerance are not duplicates."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
        symbol="XAUUSD",
        timeframe="H1",
        signalType="BUY",
        entryPrice=2360.00,  # Outside 5 pips tolerance
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
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is False


def test_is_duplicate_time_window(duplicate_detector, sample_signal):
    """Test that signals within time window are duplicates."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
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
        generatedAt=datetime.now(timezone.utc) + timedelta(minutes=15),  # Within 30 min window
    )
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is True


def test_is_duplicate_outside_time_window(duplicate_detector, sample_signal):
    """Test that signals outside time window are not duplicates."""
    existing_signals = [sample_signal]
    new_signal = TradeSetup(
        signalId="test-2",
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
        generatedAt=datetime.now(timezone.utc) + timedelta(minutes=45),  # Outside 30 min window
    )
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is False


def test_is_duplicate_inactive_signal(duplicate_detector, sample_signal):
    """Test that inactive signals are not considered for duplicates."""
    inactive_signal = TradeSetup(
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
        status="EXPIRED",  # Inactive
        decision="STRONG BUY",
        reasoning=["Strong momentum"],
        warnings=["High volatility"],
        generatedAt=datetime.now(timezone.utc),
    )
    
    existing_signals = [inactive_signal]
    new_signal = TradeSetup(
        signalId="test-2",
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
    
    is_duplicate, reason = duplicate_detector.is_duplicate(new_signal, existing_signals)
    assert is_duplicate is False


def test_allow_duplicates_true(duplicate_detector):
    """Test that when duplicates are allowed, always return False."""
    duplicate_detector.allow_duplicates = True
    
    signal = TradeSetup(
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
    
    is_duplicate, reason = duplicate_detector.is_duplicate(signal, [signal])
    assert is_duplicate is False
    assert reason is None


def test_get_duplicate_count(duplicate_detector):
    """Test counting duplicate signals."""
    signals = [
        TradeSetup(
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
        ),
        TradeSetup(
            signalId="test-2",
            symbol="XAUUSD",
            timeframe="H1",
            signalType="BUY",
            entryPrice=2351.00,
            stopLoss=2300.00,
            takeProfit1=2400.00,
            riskRewardRatio=1.5,
            confidence=85.0,
            quality="HIGH",
            expectedHoldTime="2-4 hours",
            status="ACTIVE",
            decision="BUY",
            reasoning=["Momentum"],
            warnings=["Volatility"],
            generatedAt=datetime.now(timezone.utc),
        ),
        TradeSetup(
            signalId="test-3",
            symbol="XAUUSD",
            timeframe="H1",
            signalType="SELL",
            entryPrice=2350.50,
            stopLoss=2400.00,
            takeProfit1=2300.00,
            riskRewardRatio=1.5,
            confidence=88.0,
            quality="HIGH",
            expectedHoldTime="2-4 hours",
            status="ACTIVE",
            decision="STRONG SELL",
            reasoning=["Strong momentum"],
            warnings=["High volatility"],
            generatedAt=datetime.now(timezone.utc),
        ),
    ]
    
    count = duplicate_detector.get_duplicate_count("XAUUSD", "H1", "BUY", signals)
    assert count == 2


def test_would_exceed_per_symbol_limit(duplicate_detector):
    """Test per-symbol limit checking."""
    signals = [
        TradeSetup(
            signalId=f"test-{i}",
            symbol="XAUUSD",
            timeframe="H1",
            signalType="BUY",
            entryPrice=2350.50 + i,
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
        for i in range(3)  # MAX_SIGNALS_PER_SYMBOL = 3
    ]
    
    would_exceed, reason = duplicate_detector.would_exceed_limits("XAUUSD", signals)
    assert would_exceed is True
    assert "MAX_SIGNALS_PER_SYMBOL" in reason


def test_would_not_exceed_per_symbol_limit(duplicate_detector):
    """Test that signals below limit are allowed."""
    signals = [
        TradeSetup(
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
    ]
    
    would_exceed, reason = duplicate_detector.would_exceed_limits("XAUUSD", signals)
    assert would_exceed is False
    assert reason is None
