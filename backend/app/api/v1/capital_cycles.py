"""
Falcon Capital Cycle Read-Only API Endpoints (V10 Phase 2)
Provides visibility into active cycle, cycle history, and protected profit summary.
"""

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Query

from app.core.services.capital_cycle_service import capital_cycle_service
from app.schemas.capital_cycle import (
    CapitalCycleItem,
    CapitalCycleListResponse,
    CapitalCycleSummary,
)

router = APIRouter()


@router.get("/capital-cycles/active", response_model=Optional[CapitalCycleItem])
def get_active_capital_cycle():
    """Returns the currently active capital cycle, or null if no cycle is active."""
    return capital_cycle_service.get_active_cycle()


@router.post("/capital-cycles/set-capital", response_model=CapitalCycleItem, tags=["capital-cycles"])
def set_active_capital(
    amount: float = Query(..., gt=0.0, description="Set active trading capital to any amount (e.g. $100, $500, $1000)")
):
    """
    Sets active trading capital for the active cycle to any user-defined amount.
    Unlocks asset capacity (e.g. Gold, indices) without rigid micro-cycle restrictions.
    """
    return capital_cycle_service.update_active_capital(Decimal(str(round(amount, 2))))


@router.get("/capital-cycles/history", response_model=CapitalCycleListResponse)
def get_capital_cycles_history():
    """Returns all capital cycles in chronological order."""
    cycles = capital_cycle_service.get_cycle_history()
    return CapitalCycleListResponse(
        cycles=cycles,
        totalCount=len(cycles),
    )


@router.get("/capital-cycles/summary", response_model=CapitalCycleSummary)
def get_capital_cycles_summary():
    """Returns cumulative protected profit, active cycle status, and completed cycles count."""
    return capital_cycle_service.get_summary()
