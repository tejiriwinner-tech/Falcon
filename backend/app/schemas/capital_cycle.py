"""
Falcon Capital Cycle Schemas (V10 Phase 2)
Pydantic models for capital cycles, status, allocations, and summaries.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CapitalCycleStatus(str, Enum):
    """Lifecycle status for a capital cycle."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    HALTED = "HALTED"


class CapitalCycleBase(BaseModel):
    """Core attributes defining a capital cycle."""
    model_config = ConfigDict(from_attributes=True)

    cycleId: str = Field(..., description="Unique cycle identifier, e.g. cycle-1")
    cycleNumber: int = Field(..., ge=1, description="Sequential cycle number (1, 2, 3...)")
    startingCapital: Decimal = Field(..., description="Starting capital allocated for cycle (e.g. 20.00)")
    targetCapital: Decimal = Field(..., description="Target capital to complete cycle (e.g. 500.00)")
    activeTradingCapital: Decimal = Field(..., description="Current active capital available for trading in this cycle")
    protectedProfit: Decimal = Field(default=Decimal("0.00"), description="Protected banked profit retained from this cycle")
    status: CapitalCycleStatus = Field(default=CapitalCycleStatus.ACTIVE, description="Cycle status (ACTIVE, COMPLETED, HALTED)")
    startedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when cycle started")
    completedAt: Optional[datetime] = Field(default=None, description="Timestamp when cycle reached target")
    completedCapital: Optional[Decimal] = Field(default=None, description="Final capital amount at completion (>= 500.00)")
    realizedProfit: Optional[Decimal] = Field(default=None, description="Realized profit earned in cycle (completed - starting)")
    nextCycleAllocation: Optional[Decimal] = Field(default=None, description="Allocation deducted from realized profit for next cycle (20.00)")


class CapitalCycleCreate(BaseModel):
    """Payload to create a new capital cycle."""
    cycleId: str
    cycleNumber: int
    startingCapital: Decimal
    targetCapital: Decimal
    activeTradingCapital: Decimal
    protectedProfit: Decimal = Decimal("0.00")
    status: CapitalCycleStatus = CapitalCycleStatus.ACTIVE
    startedAt: Optional[datetime] = None


class CapitalCycleUpdate(BaseModel):
    """Partial update payload for a capital cycle."""
    activeTradingCapital: Optional[Decimal] = None
    protectedProfit: Optional[Decimal] = None
    status: Optional[CapitalCycleStatus] = None
    completedAt: Optional[datetime] = None
    completedCapital: Optional[Decimal] = None
    realizedProfit: Optional[Decimal] = None
    nextCycleAllocation: Optional[Decimal] = None


class CapitalCycleItem(CapitalCycleBase):
    """Complete capital cycle record including primary key and timestamps."""
    id: int
    createdAt: datetime
    updatedAt: datetime


class CapitalCycleSummary(BaseModel):
    """Executive summary of the capital cycle state."""
    activeCycle: Optional[CapitalCycleItem] = None
    totalProtectedProfit: Decimal = Decimal("0.00")
    completedCyclesCount: int = 0
    currentActiveCapital: Decimal = Decimal("0.00")


class CapitalCycleListResponse(BaseModel):
    """Response containing list of capital cycles."""
    cycles: List[CapitalCycleItem]
    totalCount: int
