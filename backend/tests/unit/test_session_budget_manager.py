"""
Unit tests for Falcon Session & Free-Tier API Budget Manager
Verifies that market-data calls are strictly confined to 07:00-19:00 UTC (8am-8pm UTC+1) on weekdays,
and that night hours and weekends enter STANDBY mode with ZERO outbound provider calls.
Compatible with standard unittest and pytest.
"""
import sys
from pathlib import Path
backend_dir = Path(__file__).resolve().parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.core.services.session_budget_manager import (
    SessionBudgetManager,
    SessionState,
    session_budget_manager,
)
from app.core.config import settings
from app.core.engines.market_state_engine import FALCON_WATCHLIST
from app.core.scheduler_config import scheduler_config


class TestSessionBudgetManager(unittest.TestCase):
    """Test suite for SessionBudgetManager logic and boundaries."""

    def test_active_trading_hours_weekday(self):
        """07:00 to 19:00 UTC on a Wednesday (weekday) must be ACTIVE."""
        manager = SessionBudgetManager(start_hour_utc=7, end_hour_utc=19)

        # 07:00 UTC Wednesday (2026-09-02) -> ACTIVE
        dt_start = datetime(2026, 9, 2, 7, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_start), SessionState.ACTIVE)
        self.assertTrue(manager.is_active(dt_start))

        # 12:00 UTC Wednesday -> ACTIVE
        dt_mid = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_mid), SessionState.ACTIVE)
        self.assertTrue(manager.is_active(dt_mid))

        # 18:59 UTC Wednesday -> ACTIVE
        dt_end = datetime(2026, 9, 2, 18, 59, 59, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_end), SessionState.ACTIVE)
        self.assertTrue(manager.is_active(dt_end))

    def test_standby_hours_weekday_morning_and_night(self):
        """Hours outside 07:00-19:00 UTC on a weekday must be STANDBY."""
        manager = SessionBudgetManager(start_hour_utc=7, end_hour_utc=19, enable_24_5=False)

        # 06:59:59 UTC Wednesday -> STANDBY
        dt_early = datetime(2026, 9, 2, 6, 59, 59, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_early), SessionState.STANDBY)
        self.assertFalse(manager.is_active(dt_early))

        # 19:00:00 UTC Wednesday (8:00 PM local) -> STANDBY
        dt_night = datetime(2026, 9, 2, 19, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_night), SessionState.STANDBY)
        self.assertFalse(manager.is_active(dt_night))

        # 02:30:00 UTC Wednesday (deep night) -> STANDBY
        dt_deep_night = datetime(2026, 9, 2, 2, 30, 0, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_deep_night), SessionState.STANDBY)
        self.assertFalse(manager.is_active(dt_deep_night))

    def test_standby_all_weekend(self):
        """Weekends (Saturday & Sunday) must be STANDBY 24/7."""
        manager = SessionBudgetManager(start_hour_utc=7, end_hour_utc=19)

        # Saturday noon (2026-09-05) -> STANDBY
        dt_sat = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_sat), SessionState.STANDBY)
        self.assertFalse(manager.is_active(dt_sat))

        # Sunday 14:00 UTC (2026-09-06) -> STANDBY
        dt_sun = datetime(2026, 9, 6, 14, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(manager.get_session_state(dt_sun), SessionState.STANDBY)
        self.assertFalse(manager.is_active(dt_sun))

    def test_status_diagnostics(self):
        """Diagnostics dictionary must expose required telemetry fields."""
        dt_active = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
        status_active = session_budget_manager.get_status(dt_active)
        self.assertEqual(status_active["state"], "ACTIVE")
        self.assertTrue(status_active["isActive"])
        self.assertEqual(status_active["mode"], "ACTIVE_SCANNING")
        self.assertIn("08:00 - 20:00", status_active["activeWindowLocal"])

        dt_standby = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)
        status_standby = session_budget_manager.get_status(dt_standby)
        self.assertEqual(status_standby["state"], "STANDBY")
        self.assertFalse(status_standby["isActive"])
        self.assertEqual(status_standby["mode"], "MARKET_DATA_STANDBY")


class TestConfigurationAndWatchlist(unittest.TestCase):
    """Verify system-wide settings for free-tier operation."""

    def test_active_watchlist_symbols(self):
        """Active watchlist must contain core assets XAUUSD, GBPUSD, EURUSD."""
        self.assertIn("XAUUSD", settings.MARKET_DATA_WATCHLIST)
        self.assertIn("GBPUSD", settings.MARKET_DATA_WATCHLIST)
        self.assertIn("EURUSD", settings.MARKET_DATA_WATCHLIST)
        symbols = [s.strip() for s in settings.MARKET_DATA_WATCHLIST.split(",")]
        self.assertTrue(len(symbols) >= 3)
        self.assertTrue({"XAUUSD", "GBPUSD", "EURUSD"}.issubset(set(symbols)))

        # Market state engine watchlist
        self.assertTrue({"XAUUSD", "GBPUSD", "EURUSD"}.issubset(set(FALCON_WATCHLIST)))

        # Scheduler config markets
        self.assertTrue({"XAUUSD", "GBPUSD", "EURUSD"}.issubset(set(scheduler_config.MARKETS)))

    def test_ingestion_interval_quota_safe(self):
        """Ingestion interval must be at least 480 seconds (8 minutes) for free quota."""
        self.assertGreaterEqual(settings.MARKET_DATA_INGESTION_INTERVAL_SECONDS, 480)


class TestSchedulerStandbyProtection(unittest.IsolatedAsyncioTestCase):
    """Verify that background schedulers halt external calls in STANDBY mode."""

    async def test_market_data_scheduler_skips_in_standby(self):
        """MarketDataScheduler._ingestion_cycle must return standby=True and 0 calls in STANDBY."""
        from app.core.services.market_data_scheduler import MarketDataScheduler

        scheduler = MarketDataScheduler()
        scheduler._watchlist = ["XAUUSD", "GBPUSD", "EURUSD"]

        with patch.object(session_budget_manager, "is_active", return_value=False):
            with patch("app.core.services.market_history_service.market_history_service.refresh_symbol") as mock_refresh:
                result = await scheduler._ingestion_cycle()

                self.assertTrue(result["standby"])
                self.assertEqual(result["bars_stored"], 0)
                self.assertEqual(result["symbols_processed"], 0)
                mock_refresh.assert_not_called()

    async def test_market_scheduler_skips_in_standby(self):
        """MarketScheduler.scan_cycle must return standby=True and 0 signals in STANDBY."""
        from app.services.scheduler.market_scheduler import MarketScheduler

        scheduler = MarketScheduler()
        scheduler.repository = MagicMock()
        scheduler.repository.get_live_signals.return_value = []
        mock_db = MagicMock()

        with patch.object(session_budget_manager, "is_active", return_value=False):
            with patch.object(scheduler, "_scan_market_timeframe") as mock_scan:
                result = await scheduler.scan_cycle(mock_db)

                self.assertTrue(result.get("standby"))
                self.assertEqual(result["signals_generated"], 0)
                mock_scan.assert_not_called()

    def test_twelve_data_provider_blocks_fetch_in_standby(self):
        """TwelveDataProvider.fetch must return None without HTTP call when in STANDBY."""
        from app.core.providers.twelve_data_provider import TwelveDataProvider

        provider = TwelveDataProvider(api_key="test_dummy_key")
        provider._connected = True

        with patch.object(session_budget_manager, "is_active", return_value=False):
            with patch("requests.get") as mock_http_get:
                result = provider.fetch("XAUUSD")
                self.assertIsNone(result)
                mock_http_get.assert_not_called()

    def test_fmp_provider_blocks_fetch_in_standby(self):
        """FmpProvider.fetch must return None without HTTP call when in STANDBY."""
        from app.core.providers.fmp_provider import FmpProvider

        provider = FmpProvider(api_key="test_dummy_key")
        provider._connected = True

        with patch.object(session_budget_manager, "is_active", return_value=False):
            with patch.object(provider._session, "get") as mock_session_get:
                result = provider.fetch("EURUSD")
                self.assertIsNone(result)
                mock_session_get.assert_not_called()

    def test_alpha_vantage_provider_blocks_fetch_in_standby(self):
        """AlphaVantageProvider.fetch must return None without HTTP call when in STANDBY."""
        from app.core.providers.alpha_vantage_provider import AlphaVantageProvider

        provider = AlphaVantageProvider(api_key="test_dummy_key")
        provider._connected = True

        with patch.object(session_budget_manager, "is_active", return_value=False):
            with patch.object(provider._session, "get") as mock_session_get:
                result = provider.fetch("EURUSD")
                self.assertIsNone(result)
                mock_session_get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
