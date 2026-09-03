"""
Falcon Embedded Learning Scheduler Service
Runs the 15-minute autonomous learning cycle continuously within the backend process.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("falcon.learning_scheduler")


class LearningSchedulerService:
    """Embedded background runner for continuous Falcon learning cycles."""

    def __init__(self, interval_seconds: int = 900):  # 15 minutes optimal institutional learning interval
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self._total_cycles = 0

    async def start(self) -> None:
        """Start the background learning loop."""
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"LearningSchedulerService started (interval: {self.interval_seconds}s)")

    async def stop(self) -> None:
        """Stop the background learning loop."""
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("LearningSchedulerService stopped")

    async def _run_loop(self) -> None:
        """Main loop that executes learning cycles periodically."""
        # Initial wait of 15 seconds to allow market data scheduler & cache to warm up
        await asyncio.sleep(15)

        while self.is_running:
            try:
                await self._execute_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in learning cycle: {e}", exc_info=True)

            # Sleep for the configured interval
            try:
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                break

    async def _execute_cycle(self) -> None:
        """Execute a complete 4-stage learning cycle asynchronously."""
        from app.core.orchestrator.pipeline_orchestrator import pipeline_orchestrator
        from app.core.engines.learning_insight_engine import LearningInsightEngine
        from app.core.analytics.strategy_intelligence_engine import StrategyIntelligenceEngine
        from app.core.analytics.adaptive_strategy_optimizer import AdaptiveStrategyOptimizer
        from app.core.repository.mission_repository import mission_repository

        self._total_cycles += 1
        start_time = datetime.now(timezone.utc)
        logger.info(f"--- Starting Autonomous Learning Cycle #{self._total_cycles} at {start_time.isoformat()} ---")

        # Stage 1: Pipeline Orchestrator
        try:
            mission_report = await asyncio.to_thread(pipeline_orchestrator.run_pipeline)
            logger.info(f"[Stage 1] Pipeline mission {mission_report.id} completed ({mission_report.status})")
        except Exception as e:
            logger.warning(f"[Stage 1] Pipeline execution failed: {e}")

        # Stage 2: Learning Insights
        try:
            insights_engine = LearningInsightEngine()
            insights = await asyncio.to_thread(insights_engine.generate_learning_insights, mission_repository)
            logger.info(f"[Stage 2] Generated {len(insights)} learning insights")
        except Exception as e:
            logger.warning(f"[Stage 2] Learning insights failed: {e}")

        # Stage 3: Strategy Intelligence
        try:
            intel_engine = StrategyIntelligenceEngine()
            reports = await asyncio.to_thread(intel_engine.generate_reports, mission_repository)
            logger.info(f"[Stage 3] Generated {len(reports)} strategy intelligence reports")
        except Exception as e:
            logger.warning(f"[Stage 3] Strategy intelligence failed: {e}")

        # Stage 4: Strategy Optimizer
        try:
            optimizer = AdaptiveStrategyOptimizer()
            opt_reports = await asyncio.to_thread(
                optimizer.generate_optimization_reports,
                repository=mission_repository,
            )
            logger.info(f"[Stage 4] Generated {len(opt_reports)} strategy optimization reports")
        except Exception as e:
            logger.warning(f"[Stage 4] Strategy optimizer failed: {e}")

        logger.info(f"--- Learning Cycle #{self._total_cycles} finished ---")


learning_scheduler_service = LearningSchedulerService()
