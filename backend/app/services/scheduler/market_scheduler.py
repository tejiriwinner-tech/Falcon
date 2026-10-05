"""
Falcon Market Scheduler

Runs the complete Falcon pipeline for each configured market and timeframe.
Generates signals, evaluates them through all engines, and saves approved signals.
"""
import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.scheduler_config import scheduler_config
from app.core.services.session_budget_manager import session_budget_manager
from app.services.scheduler.duplicate_detector import DuplicateDetector
from app.services.scheduler.expiration_service import ExpirationService
from app.services.scheduler.signal_dispatcher import SignalDispatcher
from app.services.scheduler.signal_repository import SignalRepository
from app.services.scheduler.scheduler_statistics import SchedulerStatistics
from app.services.signals.signal_generator import SignalGenerator
from app.services.risk.risk_management_engine import RiskManagementEngine
from app.services.trend.trend_service import TrendService
from app.services.market_structure.structure_service import StructureService
from app.services.indicators.indicator_service import IndicatorService
from app.services.signals.signal_scoring_engine import SignalScoringEngine
from app.services.decision.decision_engine import AIDecisionEngine
from app.schemas.signal_models import TradeSetup
from app.schemas.signal_settings import SignalSettings
from app.models.market_candle import Timeframe
import logging

logger = logging.getLogger(__name__)


class MarketScheduler:
    """Runs the Falcon pipeline for all configured markets and timeframes."""
    
    def __init__(self):
        """Initialize the market scheduler with all required services."""
        self.duplicate_detector = DuplicateDetector()
        self.expiration_service = ExpirationService()
        self.dispatcher = SignalDispatcher()
        self.repository = SignalRepository()
        self.statistics = SchedulerStatistics()
        self.signal_generator = SignalGenerator()
        self.risk_engine = RiskManagementEngine()
        
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        # threading.Lock (not asyncio.Lock): the scan body runs in a worker thread
        self._scan_lock = threading.Lock()  # Prevent overlapping scans

    @staticmethod
    def _skipped_result() -> dict:
        return {
            "signals_generated": 0,
            "signals_approved": 0,
            "signals_rejected": 0,
            "duplicates_prevented": 0,
            "errors": ["Scan skipped: previous scan still in progress"],
        }

    async def scan_cycle(self, db: Session) -> dict:
        """
        Run a complete scan cycle for all configured markets and timeframes.

        The heavy work (synchronous SQLAlchemy/Supabase queries and indicator
        computation) is offloaded to a worker thread so the asyncio event loop
        keeps serving HTTP requests while a scan is in progress.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with scan results
        """
        # Check if a scan is already in progress
        if self._scan_lock.locked():
            logger.warning("Scan cycle skipped: previous scan still in progress")
            return self._skipped_result()
        return await asyncio.to_thread(self._scan_cycle_sync, db)

    def _scan_cycle_sync(self, db: Session) -> dict:
        """Synchronous scan cycle body. Must be run off the event loop."""
        if not self._scan_lock.acquire(blocking=False):
            logger.warning("Scan cycle skipped: previous scan still in progress")
            return self._skipped_result()
        try:
            return self._scan_cycle_locked(db)
        finally:
            self._scan_lock.release()

    def _scan_cycle_locked(self, db: Session) -> dict:
        if True:  # preserves original block indentation
            scan_start_ms = self.statistics.record_scan_start()
            results = {
                "signals_generated": 0,
                "signals_approved": 0,
                "signals_rejected": 0,
                "duplicates_prevented": 0,
                "errors": [],
            }
            
            try:
                # Check active trading session window
                if not session_budget_manager.is_active():
                    # Clean up expired signals during STANDBY
                    if scheduler_config.AUTO_EXPIRE:
                        existing_signals = self.repository.get_live_signals()
                        expirable = self.expiration_service.find_expirable_signals(existing_signals)
                        for signal in expirable:
                            self.repository.expire_signal(signal.signalId)
                            self.statistics.record_signal_expired()
                        if expirable:
                            logger.info(f"Expired {len(expirable)} signals during STANDBY")

                    logger.info(
                        "Session budget manager: STANDBY mode (outside 07:00-19:00 UTC or weekend). "
                        "Skipping market scanning to preserve free API quota."
                    )
                    self.statistics.record_scan_end(scan_start_ms, success=True)
                    results["standby"] = True
                    return results

                # Get existing active signals for duplicate detection
                existing_signals = self.repository.get_live_signals()
                
                # Check limits before scanning
                would_exceed, limit_reason = self.duplicate_detector.would_exceed_limits(
                    "ANY", existing_signals
                )
                if would_exceed:
                    logger.warning(f"Skipping scan: {limit_reason}")
                    results["errors"].append(limit_reason)
                    self.statistics.record_scan_end(scan_start_ms, success=False)
                    return results
                
                # Run expiration check
                if scheduler_config.AUTO_EXPIRE:
                    expirable = self.expiration_service.find_expirable_signals(existing_signals)
                    for signal in expirable:
                        self.repository.expire_signal(signal.signalId)
                        self.statistics.record_signal_expired()
                    logger.info(f"Expired {len(expirable)} signals")
                
                # Scan each market/timeframe combination
                from app.core.providers import provider_manager
                for symbol in scheduler_config.MARKETS:
                    # Fetch live quote once per symbol for this scan cycle (cached for all timeframes)
                    symbol_live_price = None
                    try:
                        quote_resp = provider_manager.get_market_quote(symbol)
                        if quote_resp and quote_resp.quote:
                            symbol_live_price = quote_resp.quote.lastPrice or quote_resp.quote.bidAsk.bid or quote_resp.quote.bidAsk.ask
                    except Exception as q_err:
                        logger.debug(f"Failed to fetch market quote for {symbol}: {q_err}")

                    for timeframe in scheduler_config.TIMEFRAMES:
                        try:
                            signal_result = self._scan_market_timeframe(
                                symbol, timeframe, db, existing_signals, live_price=symbol_live_price
                            )
                            
                            results["signals_generated"] += signal_result["generated"]
                            results["signals_approved"] += signal_result["approved"]
                            results["signals_rejected"] += signal_result["rejected"]
                            results["duplicates_prevented"] += signal_result["duplicates"]
                            
                        except Exception as e:
                            error_msg = f"Error scanning {symbol} {timeframe}: {e}"
                            logger.error(error_msg)
                # Track and resolve signal outcomes against live prices
                try:
                    from app.core.services.signal_outcome_resolver import signal_outcome_resolver
                    signal_outcome_resolver.resolve_signals()
                except Exception as ex:
                    logger.debug(f"Signal outcome resolution during scan cycle: {ex}")

                self.statistics.record_scan_end(scan_start_ms, success=True)
                logger.info(f"Scan cycle completed: {results}")
                
            except Exception as e:
                logger.error(f"Scan cycle failed: {e}")
                results["errors"].append(str(e))
                self.statistics.record_scan_end(scan_start_ms, success=False)
            
            return results
    
    def _scan_market_timeframe(
        self,
        symbol: str,
        timeframe: str,
        db: Session,
        existing_signals: List[TradeSetup],
        live_price: Optional[float] = None
    ) -> dict:
        """
        Scan a single market/timeframe combination.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            db: Database session
            existing_signals: List of existing signals for duplicate detection
            live_price: Optional pre-fetched live price for this symbol
            
        Returns:
            Dictionary with scan results for this combination
        """
        result = {
            "generated": 0,
            "approved": 0,
            "rejected": 0,
            "duplicates": 0,
        }
        
        generation_start_ms = time.time() * 1000
        
        try:
            # Initialize services for this scan
            trend_service = TrendService(db)
            structure_service = StructureService(db)
            indicator_service = IndicatorService(db)
            signal_scoring_engine = SignalScoringEngine()
            ai_decision_engine = AIDecisionEngine()
            
            # Validate timeframe
            try:
                tf = Timeframe(timeframe)
            except ValueError:
                logger.warning(f"Invalid timeframe: {timeframe}")
                return result
            
            from app.services.history.history_service import HistoryService
            from app.core.providers import provider_manager

            history_service = HistoryService(db)
            candles = history_service.get_candles(symbol, tf, limit=200)

            # Fallback to provider if live_price was not supplied
            if live_price is None:
                try:
                    quote_resp = provider_manager.get_market_quote(symbol)
                    if quote_resp and quote_resp.quote:
                        live_price = quote_resp.quote.lastPrice
                except Exception:
                    pass

            # Run Falcon pipeline
            trend_result = trend_service.calculate_trend(symbol, tf, limit=200)
            structure_result = structure_service.analyze_structure(symbol, tf, limit=200)
            indicator_result = indicator_service.calculate_indicators(symbol, tf, limit=200)
            
            if not live_price and indicator_result:
                live_price = indicator_result.bb_middle
            
            signal_score_result = signal_scoring_engine.calculate_signal_score(
                symbol=symbol,
                timeframe=timeframe,
                trend_result=trend_result,
                structure_result=structure_result,
                indicator_result=indicator_result,
                current_price=live_price
            )
            
            ai_decision = ai_decision_engine.make_decision(
                symbol=symbol,
                timeframe=timeframe,
                trend_result=trend_result,
                structure_result=structure_result,
                indicator_result=indicator_result,
                signal_score_result=signal_score_result
            )
            
            # Generate signal using the intelligent signal generator with real live price & pattern recognition
            trade_setup = self.signal_generator.generate_signal(
                symbol=symbol,
                timeframe=timeframe,
                ai_decision=ai_decision,
                trend_result=trend_result,
                structure_result=structure_result,
                indicator_result=indicator_result,
                signal_score_result=signal_score_result,
                current_price=live_price,
                candles=candles
            )
            
            generation_time_ms = time.time() * 1000 - generation_start_ms
            self.statistics.record_signal_generated(symbol, timeframe, generation_time_ms)
            
            if not trade_setup:
                logger.debug(f"No signal generated for {symbol} {timeframe}")
                return result
            
            result["generated"] = 1
            
            # Check for duplicates
            is_duplicate, duplicate_reason = self.duplicate_detector.is_duplicate(
                trade_setup, existing_signals
            )
            
            if is_duplicate:
                logger.info(f"Duplicate prevented: {duplicate_reason}")
                self.statistics.record_duplicate_prevented()
                result["duplicates"] = 1
                return result
            
            # Evaluate through risk engine
            risk_assessment = self.risk_engine.evaluate(trade_setup)
            
            # Check if signal is approved by risk engine
            # APPROVED and APPROVED_WITH_WARNING are both acceptable
            if risk_assessment.decision not in ["APPROVED", "APPROVED_WITH_WARNING"]:
                logger.info(
                    f"Signal rejected by risk engine: {symbol} {timeframe} "
                    f"(decision: {risk_assessment.decision})"
                )
                self.statistics.record_signal_rejected(symbol, timeframe, str(risk_assessment.decision))
                result["rejected"] = 1
                return result
            
            # Signal is approved - save to repository
            trade_setup.status = "ACTIVE"
            saved = self.repository.save_signal(trade_setup)
            
            if saved:
                logger.info(
                    f"Signal approved and saved: {symbol} {timeframe} "
                    f"{trade_setup.signalType} @ {trade_setup.entryPrice}"
                )
                self.statistics.record_signal_approved(symbol, timeframe)
                self.dispatcher.dispatch(trade_setup)
                result["approved"] = 1
            else:
                logger.error(f"Failed to save signal for {symbol} {timeframe}")
                result["rejected"] = 1
            
        except Exception as e:
            logger.error(f"Error scanning {symbol} {timeframe}: {e}")
            raise
        
        return result
    
    async def start(self, db_factory):
        """
        Start the background scheduler.
        
        Args:
            db_factory: Database session factory
        """
        if self.is_running:
            logger.warning("Scheduler is already running")
            return
        
        self.is_running = True
        logger.info("Starting market scheduler")
        
        async def scheduler_loop():
            while self.is_running:
                try:
                    db = db_factory()
                    try:
                        await self.scan_cycle(db)
                    finally:
                        db.close()
                except Exception as e:
                    logger.error(f"Error in scheduler loop: {e}")
                
                # Wait for next scan interval
                await asyncio.sleep(scheduler_config.SCAN_INTERVAL_SECONDS)
        
        self._task = asyncio.create_task(scheduler_loop())
        logger.info(f"Market scheduler started (interval: {scheduler_config.SCAN_INTERVAL_SECONDS}s)")
    
    async def stop(self):
        """Stop the background scheduler."""
        if not self.is_running:
            return
        
        logger.info("Stopping market scheduler")
        self.is_running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("Market scheduler stopped")
    
    def get_status(self) -> dict:
        """
        Get the current status of the scheduler.
        
        Returns:
            Dictionary with scheduler status
        """
        return {
            "is_running": self.is_running,
            "scan_interval_seconds": scheduler_config.SCAN_INTERVAL_SECONDS,
            "markets_monitored": scheduler_config.MARKETS,
            "timeframes_monitored": scheduler_config.TIMEFRAMES,
            "total_combinations": scheduler_config.get_total_combinations(),
            "last_scan_time": self.statistics.last_scan_time.isoformat() if self.statistics.last_scan_time else None,
            "consecutive_failures": self.statistics.consecutive_failures,
            "max_consecutive_failures": scheduler_config.MAX_CONSECUTIVE_FAILURES,
        }
