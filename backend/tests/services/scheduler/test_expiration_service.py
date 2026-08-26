"""
Unit tests for ExpirationService.
"""
import pytest
from datetime import datetime, timezone, timedelta
from app.services.scheduler.expiration_service import ExpirationService
from app.schemas.signal_models import TradeSetup


@pytest.fixture
def expiration_service():
    """Create an ExpirationService instance for testing."""
    return ExpirationService()


@pytest.fixture
def active_signal():
    """Create an active signal for testing."""
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


@pytest.fixture
def expired_signal():
    """Create an expired signal for testing."""
    return TradeSetup(
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
        generatedAt=datetime.now(timezone.utc) - timedelta(hours=25),  # Old signal
    )


@pytest.fixture
def signal_with_expiration():
    """Create a signal with explicit expiration time."""
    return TradeSetup(
        signalId="test-3",
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
        expiresAt=datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
    )


def test_expiration_service_initialization(expiration_service):
    """Test that ExpirationService initializes correctly."""
    assert expiration_service.auto_expire is True
    assert expiration_service.expiration_hours == 24


def test_should_expire_with_explicit_expiration(expiration_service, signal_with_expiration):
    """Test expiration with explicit expiration time."""
    assert expiration_service.should_expire(signal_with_expiration) is True


def test_should_expire_without_explicit_expiration(expiration_service, expired_signal):
    """Test expiration based on generation time."""
    assert expiration_service.should_expire(expired_signal) is True


def test_should_not_expire_active_signal(expiration_service, active_signal):
    """Test that active signals should not expire."""
    assert expiration_service.should_expire(active_signal) is False


def test_should_expire_when_auto_expire_disabled(expiration_service, signal_with_expiration):
    """Test that signals don't expire when auto_expire is disabled."""
    expiration_service.auto_expire = False
    assert expiration_service.should_expire(signal_with_expiration) is False


def test_expire_signal(expiration_service, active_signal):
    """Test expiring a signal."""
    expired = expiration_service.expire_signal(active_signal)
    assert expired.status == "EXPIRED"
    assert expired.expiresAt is not None
    assert expired.signalId == active_signal.signalId


def test_find_expirable_signals(expiration_service, active_signal, expired_signal, signal_with_expiration):
    """Test finding expirable signals."""
    signals = [active_signal, expired_signal, signal_with_expiration]
    expirable = expiration_service.find_expirable_signals(signals)
    assert len(expirable) == 2
    assert expired_signal in expirable
    assert signal_with_expiration in expirable
    assert active_signal not in expirable


def test_find_expirable_signals_empty(expiration_service):
    """Test finding expirable signals with empty list."""
    expirable = expiration_service.find_expirable_signals([])
    assert len(expirable) == 0


def test_find_expirable_signals_when_disabled(expiration_service, active_signal):
    """Test that no signals are expirable when auto_expire is disabled."""
    expiration_service.auto_expire = False
    expirable = expiration_service.find_expirable_signals([active_signal])
    assert len(expirable) == 0


def test_expire_signals(expiration_service, active_signal, expired_signal):
    """Test expiring multiple signals."""
    signals = [active_signal, expired_signal]
    updated = expiration_service.expire_signals(signals)
    
    assert len(updated) == 2
    assert updated[0].status == "ACTIVE"
    assert updated[1].status == "EXPIRED"


def test_expire_signals_no_expirable(expiration_service, active_signal):
    """Test expiring signals when none should expire."""
    signals = [active_signal]
    updated = expiration_service.expire_signals(signals)
    
    assert len(updated) == 1
    assert updated[0].status == "ACTIVE"


def test_get_expiration_stats(expiration_service, active_signal, expired_signal, signal_with_expiration):
    """Test getting expiration statistics."""
    signals = [active_signal, expired_signal, signal_with_expiration]
    stats = expiration_service.get_expiration_stats(signals)
    
    assert stats["active_signals"] == 1
    assert stats["expired_signals"] == 0  # Before expiration
    assert stats["auto_expire_enabled"] is True
    assert stats["expiration_hours"] == 24


def test_get_expiration_stats_expiring_soon(expiration_service):
    """Test detection of signals expiring soon."""
    soon_to_expire = TradeSetup(
        signalId="test-soon",
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
        generatedAt=datetime.now(timezone.utc) - timedelta(hours=23, minutes=30),
    )
    
    stats = expiration_service.get_expiration_stats([soon_to_expire])
    assert stats["expiring_soon_count"] == 1
