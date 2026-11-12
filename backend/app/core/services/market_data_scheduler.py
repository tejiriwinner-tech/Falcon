"""
Falcon Market Data Scheduler

Background scheduler for automatic market data ingestion into price_history.

Responsibilities:
- Periodically fetch market data from providers via MarketHistoryService
- Populate/update price_history table
- Handle provider failures gracefully
- Support clean startup/shutdown

The scheduler does NOT perform signal generation - that is handled by MarketScheduler.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

from app.core.config import settings
from app.core.services.market_history_service import market_history_service
from app.core.services.session_budget_manager import session_budget_manager

logger = logging.getLogger(__name__)


class MarketDataScheduler:
    """Background scheduler for market data ingestion into price_history."""

    def __init__(self):
        """Initialize the market data scheduler."""
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._watchlist: List[str] = []
        self._timeframe: Optional[str] = None
        self._ingestion_interval: int = settings.MARKET_DATA_INGESTION_INTERVAL_SECONDS
        self._initial_delay: int = settings.INITIAL_BACKFILL_DELAY_SECONDS
        self._stats = {
            "total_cycles": 0,
            "successful_cycles": 0,
            "failed_cycles": 0,
            "total_bars_stored": 0,
            "last_cycle_time": None,
            "last_error": None,
        }

    def _parse_watchlist(self, watchlist_str: str) -> List[str]:
        """
        Parse comma-separated watchlist configuration.

        Args:
            watchlist_str: Comma-separated symbol string

        Returns:
            List of normalized symbols (uppercase, stripped, non-empty)
        """
        if not watchlist_str:
            return []
        
        symbols = []
        for symbol in watchlist_str.split(","):
            normalized = symbol.strip().upper()
            if normalized:  # Skip empty strings
                symbols.append(normalized)
        
        return symbols

    async def _ingestion_cycle(self) -> dict:
        """
        Execute a single market data ingestion cycle.

        Fetches data for all configured symbols from the watchlist
        using the existing MarketHistoryService provider routing.

        Returns:
            Dictionary with cycle results
        """
        if not session_budget_manager.is_active():
            logger.info(
                "Session budget manager: STANDBY mode (outside 07:00-19:00 UTC or weekend). "
                "Skipping market data ingestion to conserve free API quota."
            )
            return {
                "symbols_processed": 0,
                "bars_stored": 0,
                "errors": [],
                "standby": True,
            }

        cycle_start = time.time()
        cycle_result = {
            "symbols_processed": 0,
            "bars_stored": 0,
            "errors": [],
            "standby": False,
        }

        logger.info(f"Starting market data ingestion cycle for {len(self._watchlist)} symbols")

        for symbol in self._watchlist:
            try:
                # Use existing MarketHistoryService which handles provider routing
                # Twelve Data → Alpha Vantage fallback (XAUUSD)
                # Twelve Data → FMP → Alpha Vantage (GBPUSD, EURUSD, etc.)
                bars_stored = await asyncio.to_thread(
                    market_history_service.refresh_symbol,
                    symbol=symbol,
                    timeframe=self._timeframe,
                    force=True
                )
                
                cycle_result["symbols_processed"] += 1
                cycle_result["bars_stored"] += bars_stored
                
                if bars_stored > 0:
                    logger.info(f"Ingested {bars_stored} bars for {symbol}")
                else:
                    logger.warning(f"No bars stored for {symbol} (provider may have no data)")

            except Exception as e:
                error_msg = f"Error ingesting data for {symbol}: {e}"
                logger.error(error_msg)
                cycle_result["errors"].append(error_msg)
                # Continue processing other symbols even if one fails
            await asyncio.sleep(0.5)

        cycle_duration = time.time() - cycle_start
        logger.info(
            f"Ingestion cycle completed: {cycle_result['symbols_processed']} symbols, "
            f"{cycle_result['bars_stored']} bars stored, "
            f"{len(cycle_result['errors'])} errors, "
            f"{cycle_duration:.2f}s duration"
        )

        return cycle_result

    async def _scheduler_loop(self):
        """
        Main scheduler loop that runs periodic ingestion cycles.

        This method:
        1. Waits for initial delay
        2. Performs initial refresh
        3. Runs periodic ingestion at configured interval
        4. Handles shutdown gracefully
        """
        try:
            # Initial delay before first ingestion
            logger.info(f"Market data scheduler waiting {self._initial_delay}s before initial refresh")
            await asyncio.sleep(self._initial_delay)

            # Initial refresh
            logger.info("Performing initial market data refresh")
            try:
                initial_result = await self._ingestion_cycle()
                self._stats["total_cycles"] += 1
                self._stats["successful_cycles"] += 1
                self._stats["total_bars_stored"] += initial_result["bars_stored"]
                self._stats["last_cycle_time"] = datetime.now(timezone.utc)
                
                if initial_result["errors"]:
                    self._stats["last_error"] = "; ".join(initial_result["errors"])
                else:
                    self._stats["last_error"] = None
            except Exception as e:
                logger.error(f"Initial refresh failed: {e}")
                self._stats["total_cycles"] += 1
                self._stats["failed_cycles"] += 1
                self._stats["last_error"] = str(e)

            # Periodic ingestion loop
            while self.is_running:
                try:
                    # Wait for next interval
                    await asyncio.sleep(self._ingestion_interval)

                    if not self.is_running:
                        break

                    # Perform ingestion cycle
                    logger.info("Starting periodic market data ingestion cycle")
                    result = await self._ingestion_cycle()

                    # Update statistics
                    self._stats["total_cycles"] += 1
                    self._stats["total_bars_stored"] += result["bars_stored"]
                    self._stats["last_cycle_time"] = datetime.now(timezone.utc)

                    if result["errors"]:
                        self._stats["failed_cycles"] += 1
                        self._stats["last_error"] = "; ".join(result["errors"])
                    else:
                        self._stats["successful_cycles"] += 1
                        self._stats["last_error"] = None

                except Exception as e:
                    logger.error(f"Ingestion cycle failed: {e}")
                    self._stats["total_cycles"] += 1
                    self._stats["failed_cycles"] += 1
                    self._stats["last_error"] = str(e)
                    # Continue running even if a cycle fails

        except asyncio.CancelledError:
            logger.info("Market data scheduler cancelled")
            raise
        except Exception as e:
            logger.error(f"Market data scheduler loop error: {e}")
            raise

    async def start(self, watchlist: Optional[str] = None, timeframe: Optional[str] = None):
        """
        Start the market data scheduler.

        Args:
            watchlist: Comma-separated symbols to ingest (defaults to MARKET_DATA_WATCHLIST)
            timeframe: Timeframe for bars (defaults to HISTORY_TIMEFRAME)
        """
        if self.is_running:
            logger.warning("Market data scheduler is already running")
            return

        # Parse configuration
        watchlist_str = watchlist or settings.MARKET_DATA_WATCHLIST
        self._watchlist = self._parse_watchlist(watchlist_str)
        self._timeframe = timeframe or settings.HISTORY_TIMEFRAME

        if not self._watchlist:
            logger.warning("No symbols in watchlist, scheduler will not start")
            return

        self.is_running = True
        logger.info(
            f"Starting market data scheduler: {len(self._watchlist)} symbols, "
            f"timeframe={self._timeframe}, interval={self._ingestion_interval}s"
        )

        # Create and start background task
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("Market data scheduler started successfully")

    async def stop(self):
        """Stop the market data scheduler gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping market data scheduler")
        self.is_running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Market data scheduler stopped")

    def get_status(self) -> dict:
        """
        Get the current status of the market data scheduler.

        Returns:
            Dictionary with scheduler status and statistics
        """
        return {
            "is_running": self.is_running,
            "session": session_budget_manager.get_status(),
            "watchlist": self._watchlist,
            "timeframe": self._timeframe,
            "ingestion_interval_seconds": self._ingestion_interval,
            "statistics": self._stats.copy(),
        }


# Singleton instance
market_data_scheduler = MarketDataScheduler()
