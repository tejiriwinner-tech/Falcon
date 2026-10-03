"""
Unit tests for Session Budget Manager 24/5 Operation and Weekend Curfew.
"""
from datetime import datetime, timezone
from unittest.mock import patch
import pytest

from app.core.config import settings
from app.core.services.session_budget_manager import SessionBudgetManager, SessionState


def test_session_budget_weekday_asian_session_active():
    """Verify that during weekdays in Asian hours (02:00 UTC), Falcon is ACTIVE when 24/5 is enabled."""
    manager = SessionBudgetManager()
    # Tuesday at 02:30 UTC (Asian/Tokyo trading session)
    tuesday_asian = datetime(2026, 10, 6, 2, 30, tzinfo=timezone.utc)
    assert tuesday_asian.weekday() == 1  # Tuesday

    with patch.object(settings, "FALCON_24_5_TRADING", True), \
         patch.object(settings, "OANDA_API_KEY", "test_oanda_key"):
        state = manager.get_session_state(tuesday_asian)
        assert state == SessionState.ACTIVE
        assert manager.is_active(tuesday_asian) is True


def test_session_budget_weekend_standby():
    """Verify that during Saturday and Sunday before 21:00 UTC, Falcon is strictly in STANDBY."""
    manager = SessionBudgetManager()

    # Saturday at 14:00 UTC
    saturday = datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc)
    assert saturday.weekday() == 5  # Saturday

    # Sunday at 10:00 UTC (before market open)
    sunday_morning = datetime(2026, 10, 4, 10, 0, tzinfo=timezone.utc)
    assert sunday_morning.weekday() == 6  # Sunday

    with patch.object(settings, "FALCON_24_5_TRADING", True), \
         patch.object(settings, "OANDA_API_KEY", "test_oanda_key"):
        assert manager.get_session_state(saturday) == SessionState.STANDBY
        assert manager.is_active(saturday) is False

        assert manager.get_session_state(sunday_morning) == SessionState.STANDBY
        assert manager.is_active(sunday_morning) is False


def test_session_budget_sunday_market_open():
    """Verify that Sunday at 22:00 UTC (Sydney/Asian open), Falcon switches to ACTIVE."""
    manager = SessionBudgetManager()
    sunday_open = datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc)

    with patch.object(settings, "FALCON_24_5_TRADING", True), \
         patch.object(settings, "OANDA_API_KEY", "test_oanda_key"):
        assert manager.get_session_state(sunday_open) == SessionState.ACTIVE
        assert manager.is_active(sunday_open) is True


def test_oanda_call_bypasses_twelvedata_quotas():
    """Verify that OANDA calls do not count against TwelveData hourly/daily quotas."""
    manager = SessionBudgetManager(max_hourly_calls=10, max_daily_calls=20)
    now = datetime(2026, 10, 6, 10, 0, tzinfo=timezone.utc)

    with patch.object(settings, "FALCON_24_5_TRADING", True), \
         patch.object(settings, "OANDA_API_KEY", "test_oanda_key"):
        # Record 10 OANDA calls
        for _ in range(10):
            manager.record_call(provider_id="oanda", dt=now)

        # Telemetry should still show 0 used for TwelveData
        telemetry = manager.get_budget_telemetry(now)
        assert telemetry["hourlyCallsUsed"] == 0

        # can_consume_call should return True for OANDA
        assert manager.can_consume_call(provider_id="oanda", dt=now) is True
