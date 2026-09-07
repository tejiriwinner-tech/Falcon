"""
Falcon Trading Session & Free-Tier API Budget Manager
Controls provider polling frequency and ensures TwelveData / Alpha Vantage
free tier quotas are preserved by focusing exclusively on active daytime hours (8am - 8pm local / 07:00 - 19:00 UTC).
"""
import os
import logging
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("falcon.session_budget")

# Active Trading Session Hours in UTC
# User's local time: UTC+1 (08:00 to 20:00 local time = 07:00 to 19:00 UTC)
# Covers London Session (07:00-16:00 UTC) + New York Session (12:00-19:00 UTC overlap)
DEFAULT_START_HOUR_UTC = int(os.getenv("FALCON_ACTIVE_START_HOUR_UTC", "7"))   # 07:00 UTC = 8:00 AM Local (UTC+1)
DEFAULT_END_HOUR_UTC = int(os.getenv("FALCON_ACTIVE_END_HOUR_UTC", "19"))      # 19:00 UTC = 8:00 PM Local (UTC+1)


class SessionState(str, Enum):
    ACTIVE = "ACTIVE"
    STANDBY = "STANDBY"


class SessionBudgetManager:
    """Manages active trading windows to conserve free tier API credits."""

    def __init__(
        self,
        start_hour_utc: int = DEFAULT_START_HOUR_UTC,
        end_hour_utc: int = DEFAULT_END_HOUR_UTC,
    ):
        self.start_hour_utc = start_hour_utc
        self.end_hour_utc = end_hour_utc

    def get_session_state(self, dt: Optional[datetime] = None) -> SessionState:
        """
        Evaluate whether Falcon is in ACTIVE or STANDBY mode.

        Rules:
          Monday-Friday:
            07:00-19:00 UTC -> ACTIVE
            19:00-07:00 UTC -> STANDBY
          Saturday-Sunday:
            STANDBY (forex & metals markets closed / dead spreads)
        """
        now = dt or datetime.now(timezone.utc)
        weekday = now.weekday()  # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
        hour = now.hour

        # Weekends are strictly STANDBY
        if weekday in (5, 6):
            return SessionState.STANDBY

        # Monday-Friday: check hour range [07:00, 19:00) UTC
        if self.start_hour_utc <= hour < self.end_hour_utc:
            return SessionState.ACTIVE

        return SessionState.STANDBY

    def is_active(self, dt: Optional[datetime] = None) -> bool:
        """Convenience method returning True if currently in ACTIVE session."""
        return self.get_session_state(dt) == SessionState.ACTIVE

    def is_active_trading_session(self, dt: Optional[datetime] = None) -> bool:
        """Alias for is_active for backward compatibility."""
        return self.is_active(dt)

    def get_status(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Return a structured diagnostic dictionary of current session state."""
        now = dt or datetime.now(timezone.utc)
        state = self.get_session_state(now)
        local_hour = (now.hour + 1) % 24  # UTC+1
        is_active = (state == SessionState.ACTIVE)
        return {
            "state": state.value,
            "isActive": is_active,
            "mode": "ACTIVE_SCANNING" if is_active else "MARKET_DATA_STANDBY",
            "currentTimeUtc": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "currentLocalTime": f"{local_hour:02d}:{now.minute:02d} (UTC+1)",
            "activeWindowLocal": "08:00 - 20:00 (8:00 AM - 8:00 PM)",
            "activeWindowUtc": f"{self.start_hour_utc:02d}:00 - {self.end_hour_utc:02d}:00 UTC",
            "message": (
                "Active prime market session (London/NY). Market data ingestion and signal generation enabled."
                if is_active else
                "STANDBY mode. Zero external market-price provider calls permitted to preserve TwelveData free quota."
            ),
        }


# Global singleton instance
session_budget_manager = SessionBudgetManager()
