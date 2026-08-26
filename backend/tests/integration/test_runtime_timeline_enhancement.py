"""
Integration Tests for Runtime Timeline Event Enhancement (Task 10)

Tests:
- RuntimeTimelineEvent with optional instrument context fields
- canonicalSymbol and instrumentType population
- Fields remain optional/nullable when metadata unavailable
"""
from datetime import datetime, timezone
from typing import Optional

from app.schemas.runtime import RuntimeTimelineEvent


class TestRuntimeTimelineEventEnhancement:
    """Integration tests for timeline event instrument context."""

    def test_timeline_event_with_instrument_context(self):
        """Test RuntimeTimelineEvent with optional instrument fields."""
        now_str = datetime.now(timezone.utc).isoformat()
        
        event = RuntimeTimelineEvent(
            eventType="PROVIDER_QUOTE",
            providerId="twelve_data",
            providerName="Twelve Data",
            symbol="XAUUSD",
            canonicalSymbol="XAUUSD",
            instrumentType="SPOT",
            detail="Quote fetched successfully",
            timestamp=now_str,
            timeLabel="Now",
        )
        
        assert event.canonicalSymbol == "XAUUSD"
        assert event.instrumentType == "SPOT"
        print("OK: Timeline event with instrument context works")

    def test_timeline_event_without_instrument_context(self):
        """Test RuntimeTimelineEvent with instrument fields as None."""
        now_str = datetime.now(timezone.utc).isoformat()
        
        event = RuntimeTimelineEvent(
            eventType="PROVIDER_FAILURE",
            providerId="yahoo_finance",
            providerName="Yahoo Finance",
            symbol="UNKNOWN_SYMBOL",
            canonicalSymbol=None,  # Unknown
            instrumentType=None,   # Unknown
            detail="Provider failed to return quote",
            timestamp=now_str,
            timeLabel="2 seconds ago",
        )
        
        assert event.canonicalSymbol is None
        assert event.instrumentType is None
        assert event.symbol == "UNKNOWN_SYMBOL"
        print("OK: Timeline event with null instrument context works")

    def test_timeline_event_optional_symbol(self):
        """Test RuntimeTimelineEvent symbol field is optional."""
        now_str = datetime.now(timezone.utc).isoformat()
        
        # Event without symbol (system-level event)
        event = RuntimeTimelineEvent(
            eventType="CIRCUIT_BREAKER_OPEN",
            providerId="twelve_data",
            providerName="Twelve Data",
            symbol=None,  # Optional
            detail="Circuit breaker opened",
            timestamp=now_str,
            timeLabel="1 minute ago",
        )
        
        assert event.symbol is None
        print("OK: Timeline event with optional symbol works")

    def test_timeline_event_all_combinations(self):
        """Test various combinations of timeline event fields."""
        now_str = datetime.now(timezone.utc).isoformat()
        
        combinations = [
            {
                "eventType": "PROVIDER_QUOTE",
                "providerId": "twelve_data",
                "providerName": "Twelve Data",
                "symbol": "XAUUSD",
                "canonicalSymbol": "XAUUSD",
                "instrumentType": "SPOT",
                "detail": "Quote received",
                "timestamp": now_str,
                "timeLabel": "Now",
                "desc": "Full instrument context"
            },
            {
                "eventType": "FAILOVER",
                "providerId": "yahoo_finance",
                "providerName": "Yahoo Finance",
                "symbol": "XAUUSD",
                "canonicalSymbol": "XAUUSD",
                "instrumentType": None,  # Metadata unavailable
                "detail": "Failover event",
                "timestamp": now_str,
                "timeLabel": "5 seconds ago",
                "desc": "Canonical only"
            },
            {
                "eventType": "CIRCUIT_BREAKER",
                "providerId": "mock_price",
                "providerName": "Mock Price",
                "symbol": None,
                "canonicalSymbol": None,
                "instrumentType": None,
                "detail": "Circuit opened",
                "timestamp": now_str,
                "timeLabel": "10 seconds ago",
                "desc": "System-level event"
            },
        ]
        
        for combo in combinations:
            desc = combo.pop("desc")
            event = RuntimeTimelineEvent(**combo)
            assert event.eventType == combo["eventType"]
            print(f"OK: {desc}")

    def test_timeline_event_model_validation(self):
        """Test that timeline event model properly validates required fields."""
        now_str = datetime.now(timezone.utc).isoformat()
        
        # All required fields present
        event = RuntimeTimelineEvent(
            eventType="TEST_EVENT",
            providerId="test_provider",
            providerName="Test Provider",
            detail="Test detail",
            timestamp=now_str,
            timeLabel="Test label",
        )
        
        assert event.eventType == "TEST_EVENT"
        assert event.providerId == "test_provider"
        assert event.symbol is None  # Optional
        assert event.canonicalSymbol is None  # Optional
        assert event.instrumentType is None  # Optional
        print("OK: Timeline event validation works correctly")


if __name__ == "__main__":
    test = TestRuntimeTimelineEventEnhancement()
    test.test_timeline_event_with_instrument_context()
    test.test_timeline_event_without_instrument_context()
    test.test_timeline_event_optional_symbol()
    test.test_timeline_event_all_combinations()
    test.test_timeline_event_model_validation()
    print("\nAll runtime timeline event enhancement tests passed!")
