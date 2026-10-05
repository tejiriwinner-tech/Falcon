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

# Calibrated Free-Tier Rate Limits (TwelveData 800 free credits daily allowance)
# 65 calls/hour x 12 hours = 780 calls/day (reserving a 20-call safety buffer)
DEFAULT_MAX_HOURLY_CALLS = int(os.getenv("FALCON_MAX_HOURLY_CALLS", "65"))
DEFAULT_MAX_DAILY_CALLS = int(os.getenv("FALCON_MAX_DAILY_CALLS", "780"))

import threading


class SessionState(str, Enum):
    ACTIVE = "ACTIVE"
    STANDBY = "STANDBY"


class SessionBudgetManager:
    """Manages active trading windows and paces API call budgets to conserve free-tier credits."""

    def __init__(
        self,
        start_hour_utc: int = DEFAULT_START_HOUR_UTC,
        end_hour_utc: int = DEFAULT_END_HOUR_UTC,
        max_hourly_calls: int = DEFAULT_MAX_HOURLY_CALLS,
        max_daily_calls: int = DEFAULT_MAX_DAILY_CALLS,
        enable_24_5: Optional[bool] = None,
    ):
        self.start_hour_utc = start_hour_utc
        self.end_hour_utc = end_hour_utc
        self.max_hourly_calls = max_hourly_calls
        self.max_daily_calls = max_daily_calls
        self.enable_24_5 = enable_24_5

        self._lock = threading.Lock()
        self._current_hour_key: str = ""
        self._hourly_calls_count: int = 0
        self._current_day_key: str = ""
        self._daily_calls_count: int = 0

    def _is_24_5(self) -> bool:
        if self.enable_24_5 is not None:
            return self.enable_24_5
        from app.core.config import settings
        return getattr(settings, "FALCON_24_5_TRADING", False) or bool(getattr(settings, "OANDA_API_KEY", None))

    def _sync_buckets(self, now: datetime) -> None:
        """Reset hourly and daily counters when time bucket rolls over."""
        hour_key = now.strftime("%Y-%m-%d-%H")
        day_key = now.strftime("%Y-%m-%d")

        if hour_key != self._current_hour_key:
            self._current_hour_key = hour_key
            self._hourly_calls_count = 0

        if day_key != self._current_day_key:
            self._current_day_key = day_key
            self._daily_calls_count = 0

    def can_consume_call(self, provider_id: str = "unknown", dt: Optional[datetime] = None) -> bool:
        """
        Check if an external API call is permitted under session and budget constraints.
        Returns False if in STANDBY or if the hourly (65) or daily (780) quota ceiling is reached.
        If provider is OANDA, call limits are bypassed because OANDA enforces no request quotas.
        """
        now = dt or datetime.now(timezone.utc)
        if not self.is_active(now):
            return False

        # OANDA has no request caps or rate limits
        from app.core.config import settings
        if provider_id.lower() == "oanda" or (provider_id == "unknown" and getattr(settings, "OANDA_API_KEY", None)):
            return True

        with self._lock:
            self._sync_buckets(now)
            if self._hourly_calls_count >= self.max_hourly_calls:
                logger.warning(
                    f"Hourly API quota reached ({self._hourly_calls_count}/{self.max_hourly_calls}). "
                    "Throttling external call to protect the rest of the trading day."
                )
                return False
            if self._daily_calls_count >= self.max_daily_calls:
                logger.warning(
                    f"Daily API quota reached ({self._daily_calls_count}/{self.max_daily_calls}). "
                    "Throttling external call until 00:00 UTC daily quota reset."
                )
                return False
            return True

    def record_call(self, provider_id: str = "unknown", dt: Optional[datetime] = None) -> None:
        """Record an outbound live API call towards the hourly and daily budget."""
        if provider_id.lower() == "oanda":
            # OANDA has zero quota counting; do not deplete TwelveData allowance
            return
        now = dt or datetime.now(timezone.utc)
        with self._lock:
            self._sync_buckets(now)
            self._hourly_calls_count += 1
            self._daily_calls_count += 1
            logger.debug(
                f"API call recorded for [{provider_id}] — "
                f"Hour: {self._hourly_calls_count}/{self.max_hourly_calls}, "
                f"Day: {self._daily_calls_count}/{self.max_daily_calls}"
            )

    def get_budget_telemetry(self, dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Return real-time usage statistics for the current hour and day."""
        now = dt or datetime.now(timezone.utc)
        with self._lock:
            self._sync_buckets(now)
            return {
                "hourlyCallsUsed": self._hourly_calls_count,
                "hourlyCallsLimit": self.max_hourly_calls,
                "hourlyCallsRemaining": max(0, self.max_hourly_calls - self._hourly_calls_count),
                "dailyCallsUsed": self._daily_calls_count,
                "dailyCallsLimit": self.max_daily_calls,
                "dailyCallsRemaining": max(0, self.max_daily_calls - self._daily_calls_count),
            }

    def get_session_state(self, dt: Optional[datetime] = None) -> SessionState:
        """
        Evaluate whether Falcon is in ACTIVE or STANDBY mode.

        Rules:
          When OANDA is configured or FALCON_24_5_TRADING is True:
            Monday 00:00 UTC through Friday 22:00 UTC -> ACTIVE 24/5
            Friday 22:00 UTC through Sunday 21:00 UTC -> STANDBY (markets closed)
          Legacy Fallback (free TwelveData tier only):
            Monday-Friday 07:00-19:00 UTC -> ACTIVE
            Outside hours or weekends -> STANDBY
        """
        now = dt or datetime.now(timezone.utc)
        weekday = now.weekday()  # 0 = Monday, 4 = Friday, 5 = Saturday, 6 = Sunday
        hour = now.hour

        is_24_5 = self._is_24_5()

        # Weekend closure evaluation (Forex & Gold markets closed)
        if weekday == 5:  # Saturday
            return SessionState.STANDBY
        if weekday == 6 and hour < 21:  # Sunday before 21:00 UTC market open
            return SessionState.STANDBY
        if weekday == 4 and hour >= 22:  # Friday after 22:00 UTC market close
            return SessionState.STANDBY

        if is_24_5:
            # Active 24 hours Monday through Friday
            return SessionState.ACTIVE

        # Legacy behavior: check hour range [07:00, 19:00) UTC
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
        """Return a structured diagnostic dictionary of current session state and quota consumption."""
        now = dt or datetime.now(timezone.utc)
        state = self.get_session_state(now)
        local_hour = (now.hour + 1) % 24  # UTC+1
        is_active = (state == SessionState.ACTIVE)
        telemetry = self.get_budget_telemetry(now)

        is_24_5 = self._is_24_5()

        return {
            "state": state.value,
            "isActive": is_active,
            "mode": "ACTIVE_SCANNING" if is_active else "MARKET_DATA_STANDBY",
            "currentTimeUtc": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "currentLocalTime": f"{local_hour:02d}:{now.minute:02d} (UTC+1)",
            "activeWindowLocal": "24/5 Continuous (08:00 - 20:00 Core)" if is_24_5 else "08:00 - 20:00 (8:00 AM - 8:00 PM)",
            "activeWindowUtc": "24/5 (Mon 00:00 - Fri 22:00 UTC)" if is_24_5 else f"{self.start_hour_utc:02d}:00 - {self.end_hour_utc:02d}:00 UTC",
            "budgetPacing": telemetry,
            "message": (
                ("Active 24/5 institutional market session powered by OANDA broker feed." if is_24_5 else f"Active prime market session. Paced at max {self.max_hourly_calls} calls/hour.")
                if is_active else
                "STANDBY mode (weekend market close / dead spreads)."
            ),
        }


# Global singleton instance
session_budget_manager = SessionBudgetManager()
