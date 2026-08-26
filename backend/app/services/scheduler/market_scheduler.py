"""
Falcon Market Scheduler

Runs the complete Falcon pipeline for each configured market and timeframe.
Generates signals, evaluates them through all engines, and saves approved signals.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.scheduler_config import scheduler_config
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
        self._scan_lock = asyncio.Lock()  # Prevent overlapping scans
    
    async def scan_cycle(self, db: Session) -> dict:
        """
        Run a complete scan cycle for all configured markets and timeframes.
        
        Args:
            db: Database session
            
        Returns:
            Dictionary with scan results
        """
        # Check if a scan is already in progress
        if self._scan_lock.locked():
            logger.warning("Scan cycle skipped: previous scan still in progress")
            return {
                "signals_generated": 0,
                "signals_approved": 0,
                "signals_rejected": 0,
                "duplicates_prevented": 0,
                "errors": ["Scan skipped: previous scan still in progress"],
            }
        
        # Acquire lock to prevent overlapping scans
        async with self._scan_lock:
            scan_start_ms = self.statistics.record_scan_start()
            results = {
                "signals_generated": 0,
                "signals_approved": 0,
                "signals_rejected": 0,
                "duplicates_prevented": 0,
                "errors": [],
            }
            
            try:
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
                for symbol in scheduler_config.MARKETS:
                    for timeframe in scheduler_config.TIMEFRAMES:
                        try:
                            signal_result = await self._scan_market_timeframe(
                                symbol, timeframe, db, existing_signals
                            )
                            
                            results["signals_generated"] += signal_result["generated"]
                            results["signals_approved"] += signal_result["approved"]
                            results["signals_rejected"] += signal_result["rejected"]
                            results["duplicates_prevented"] += signal_result["duplicates"]
                            
                        except Exception as e:
                            error_msg = f"Error scanning {symbol} {timeframe}: {e}"
                            logger.error(error_msg)
                            results["errors"].append(error_msg)
                
                self.statistics.record_scan_end(scan_start_ms, success=True)
                logger.info(f"Scan cycle completed: {results}")
                
            except Exception as e:
                logger.error(f"Scan cycle failed: {e}")
                results["errors"].append(str(e))
                self.statistics.record_scan_end(scan_start_ms, success=False)
            
            return results
    
    async def _scan_market_timeframe(
        self,
        symbol: str,
        timeframe: str,
        db: Session,
        existing_signals: List[TradeSetup]
    ) -> dict:
        """
        Scan a single market/timeframe combination.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            db: Database session
            existing_signals: List of existing signals for duplicate detection
            
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
            
            # Run Falcon pipeline
            trend_result = trend_service.calculate_trend(symbol, tf, limit=200)
            structure_result = structure_service.analyze_structure(symbol, tf, limit=200)
            indicator_result = indicator_service.calculate_indicators(symbol, tf, limit=200)
            
            signal_score_result = signal_scoring_engine.calculate_signal_score(
                symbol=symbol,
                timeframe=timeframe,
                trend_result=trend_result,
                structure_result=structure_result,
                indicator_result=indicator_result,
                current_price=indicator_result.bb_middle if indicator_result else None
            )
            
            ai_decision = ai_decision_engine.make_decision(
                symbol=symbol,
                timeframe=timeframe,
                trend_result=trend_result,
                structure_result=structure_result,
                indicator_result=indicator_result,
                signal_score_result=signal_score_result
            )
            
            # Generate signal using the intelligent signal generator
            trade_setup = self.signal_generator.generate_signal(
                symbol=symbol,
                timeframe=timeframe,
                ai_decision=ai_decision,
                trend_result=trend_result,
                structure_result=structure_result,
                indicator_result=indicator_result,
                signal_score_result=signal_score_result,
                current_price=indicator_result.bb_middle if indicator_result else None
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
