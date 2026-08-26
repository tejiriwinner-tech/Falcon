"""
Falcon Scheduler API

API endpoints for the background signal scheduler.
Provides access to live signals, signal history, and scheduler status.
"""
from fastapi import APIRouter, Query
from typing import Optional, List
from app.services.scheduler.scheduler_service import scheduler_service
from app.services.scheduler.signal_repository import SignalRepository
from app.schemas.signal_models import TradeSetup

router = APIRouter(prefix="/scheduler", tags=["scheduler"])
signal_repository = SignalRepository()


@router.get("/status")
async def get_scheduler_status():
    """
    Get the current status of the background scheduler.
    
    Returns:
        Scheduler status including running state, configuration, and last scan time.
    """
    return scheduler_service.get_status()


@router.get("/statistics")
async def get_scheduler_statistics():
    """
    Get scheduler performance statistics.
    
    Returns:
        Comprehensive statistics about scans, signals, and performance.
    """
    return scheduler_service.get_statistics()


@router.get("/repository-stats")
async def get_repository_statistics():
    """
    Get signal repository statistics.
    
    Returns:
        Statistics about stored signals including counts and per-symbol breakdown.
    """
    return scheduler_service.get_repository_stats()
