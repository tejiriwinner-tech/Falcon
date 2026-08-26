"""
Falcon Scheduler Service

Main service for managing the background market scheduler.
Provides a clean interface for starting, stopping, and monitoring the scheduler.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.core.config.database import SessionLocal
from app.services.scheduler.market_scheduler import MarketScheduler
from app.services.scheduler.signal_repository import SignalRepository
from app.services.scheduler.scheduler_statistics import SchedulerStatistics
import logging

logger = logging.getLogger(__name__)


class SchedulerService:
    """Main service for managing the background scheduler."""
    
    def __init__(self):
        """Initialize the scheduler service."""
        self.market_scheduler = MarketScheduler()
        self.repository = SignalRepository()
        self.statistics = self.market_scheduler.statistics
    
    async def start(self):
        """Start the background scheduler."""
        try:
            await self.market_scheduler.start(SessionLocal)
            logger.info("Scheduler service started successfully")
        except Exception as e:
            logger.error(f"Failed to start scheduler service: {e}")
            raise
    
    async def stop(self):
        """Stop the background scheduler."""
        try:
            await self.market_scheduler.stop()
            logger.info("Scheduler service stopped successfully")
        except Exception as e:
            logger.error(f"Failed to stop scheduler service: {e}")
            raise
    
    def get_status(self) -> dict:
        """
        Get the current status of the scheduler.
        
        Returns:
            Dictionary with scheduler status
        """
        return self.market_scheduler.get_status()
    
    def get_statistics(self) -> dict:
        """
        Get scheduler statistics.
        
        Returns:
            Dictionary with scheduler statistics
        """
        return self.statistics.get_summary()
    
    def get_repository_stats(self) -> dict:
        """
        Get repository statistics.
        
        Returns:
            Dictionary with repository statistics
        """
        return self.repository.get_statistics()
    
    def reset_statistics(self):
        """Reset all scheduler statistics."""
        self.statistics.reset()
        logger.info("Scheduler statistics reset")


# Global scheduler service instance
scheduler_service = SchedulerService()
