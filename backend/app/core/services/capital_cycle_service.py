"""
Falcon Capital Cycle Service (V10 Phase 2)
Core business logic and invariants for capital cycles, status progression, and Decimal accounting.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from app.core.config.settings import settings
from app.core.repository.capital_cycle_repository import (
    CapitalCycleRepository,
    capital_cycle_repository,
)
from app.schemas.capital_cycle import (
    CapitalCycleCreate,
    CapitalCycleItem,
    CapitalCycleStatus,
    CapitalCycleSummary,
    CapitalCycleUpdate,
)


class CapitalCycleService:
    """Manages the capital cycle state machine, Decimal accounting, and strict safety invariants."""

    def __init__(self, repository: Optional[CapitalCycleRepository] = None) -> None:
        self._repo = repository or capital_cycle_repository

    def get_active_cycle(self, session: Optional[object] = None) -> Optional[CapitalCycleItem]:
        """Return the currently active capital cycle, or None if no cycle is active."""
        return self._repo.get_active_cycle(session=session)

    def get_cycle_history(self) -> List[CapitalCycleItem]:
        """Return all capital cycles in chronological order by cycle number."""
        return self._repo.list_cycles()

    def get_protected_profit_total(self) -> Decimal:
        """
        Calculate total cumulative protected profit banked from all COMPLETED cycles.
        
        Active trading capital (e.g. $20) is strictly EXCLUDED from protected profit.
        """
        cycles = self._repo.list_cycles()
        total = Decimal("0.00")
        for c in cycles:
            if c.status == CapitalCycleStatus.COMPLETED or c.status == "COMPLETED":
                total += c.protectedProfit
        return total

    def get_summary(self) -> CapitalCycleSummary:
        """Return high-level summary of capital cycle progress and protected reserves."""
        active = self.get_active_cycle()
        cycles = self._repo.list_cycles()
        completed_count = sum(
            1 for c in cycles if c.status in (CapitalCycleStatus.COMPLETED, "COMPLETED")
        )
        total_protected = self.get_protected_profit_total()
        active_cap = active.activeTradingCapital if active else Decimal("0.00")

        return CapitalCycleSummary(
            activeCycle=active,
            totalProtectedProfit=total_protected,
            completedCyclesCount=completed_count,
            currentActiveCapital=active_cap,
        )

    def create_initial_cycle(self) -> CapitalCycleItem:
        """
        Initialize Cycle 1 with starting capital ($20.00) and target capital ($500.00).
        
        Enforces:
        - No active cycle may currently exist.
        - Cannot create initial cycle if historical cycles already exist.
        """
        active = self.get_active_cycle()
        if active:
            raise ValueError(f"Cannot create initial cycle: active cycle '{active.cycleId}' already exists")

        cycles = self._repo.list_cycles()
        if cycles:
            raise ValueError(
                "Cannot create initial cycle: historical cycles already exist. Use create_next_cycle() instead."
            )

        start_cap = settings.CAPITAL_CYCLE_STARTING_CAPITAL
        target_cap = settings.CAPITAL_CYCLE_TARGET

        payload = CapitalCycleCreate(
            cycleId="cycle-1",
            cycleNumber=1,
            startingCapital=start_cap,
            targetCapital=target_cap,
            activeTradingCapital=start_cap,
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=datetime.now(timezone.utc),
        )
        return self._repo.create_cycle(payload)

    def complete_cycle(
        self, cycle_id: str, completed_capital: Decimal
    ) -> CapitalCycleItem:
        """
        Complete an active capital cycle upon reaching or exceeding target capital ($500.00).
        
        Calculates:
        - realized_profit = completed_capital - starting_capital
        - next_cycle_allocation = $20.00
        - protected_profit = realized_profit - next_cycle_allocation
        
        Strictly validates:
        - Cycle exists
        - Cycle status is ACTIVE (rejects COMPLETED, HALTED)
        - completed_capital >= target_capital
        - protected_profit >= 0.00
        """
        if not isinstance(completed_capital, Decimal):
            completed_capital = Decimal(str(completed_capital))

        cycle = self._repo.get_cycle_by_cycle_id(cycle_id)
        if not cycle:
            raise ValueError(f"Cycle '{cycle_id}' not found")

        if cycle.status in (CapitalCycleStatus.COMPLETED, "COMPLETED"):
            raise ValueError(f"Cannot complete cycle '{cycle_id}': cycle is already COMPLETED")

        if cycle.status in (CapitalCycleStatus.HALTED, "HALTED"):
            raise ValueError(f"Cannot complete cycle '{cycle_id}': cycle is HALTED")

        if cycle.status not in (CapitalCycleStatus.ACTIVE, "ACTIVE"):
            raise ValueError(f"Cannot complete cycle '{cycle_id}': invalid status '{cycle.status}'")

        if completed_capital < cycle.targetCapital:
            raise ValueError(
                f"Cannot complete cycle below target: completed_capital ({completed_capital}) < target_capital ({cycle.targetCapital})"
            )

        realized_profit = completed_capital - cycle.startingCapital
        next_allocation = min(settings.CAPITAL_CYCLE_NEXT_ALLOCATION, cycle.startingCapital)
        protected_profit = realized_profit - next_allocation

        if protected_profit < Decimal("0.00"):
            raise ValueError(
                f"Invalid accounting: protected profit cannot be negative ({protected_profit})"
            )

        now = datetime.now(timezone.utc)
        update_payload = CapitalCycleUpdate(
            status=CapitalCycleStatus.COMPLETED,
            completedCapital=completed_capital,
            realizedProfit=realized_profit,
            nextCycleAllocation=next_allocation,
            protectedProfit=protected_profit,
            completedAt=now,
        )

        updated = self._repo.update_cycle(cycle_id, update_payload)
        if not updated:
            raise RuntimeError(f"Failed to update cycle '{cycle_id}' to COMPLETED")
        return updated

    def create_next_cycle(self) -> CapitalCycleItem:
        """
        Allocate and activate the next capital cycle (Cycle N+1).
        
        Enforces:
        - No active cycle currently exists.
        - Previous cycle exists and has status COMPLETED.
        - HALTED cycles cannot be advanced automatically.
        - Fresh $20 active capital is allocated independently.
        """
        active = self.get_active_cycle()
        if active:
            raise ValueError(f"Cannot create next cycle: active cycle '{active.cycleId}' already exists")

        latest = self._repo.get_latest_cycle()
        if not latest:
            raise ValueError("No existing cycle found. Use create_initial_cycle() to start Cycle 1.")

        if latest.status in (CapitalCycleStatus.HALTED, "HALTED"):
            raise ValueError(
                f"Cannot advance cycle: predecessor cycle '{latest.cycleId}' is HALTED and cannot automatically continue."
            )

        if latest.status not in (CapitalCycleStatus.COMPLETED, "COMPLETED"):
            raise ValueError(
                f"Cannot advance cycle: predecessor cycle '{latest.cycleId}' is not COMPLETED (status: {latest.status})"
            )

        next_number = latest.cycleNumber + 1
        next_id = f"cycle-{next_number}"
        alloc_cap = latest.nextCycleAllocation or min(settings.CAPITAL_CYCLE_NEXT_ALLOCATION, latest.startingCapital)
        target_cap = latest.targetCapital or settings.CAPITAL_CYCLE_TARGET

        payload = CapitalCycleCreate(
            cycleId=next_id,
            cycleNumber=next_number,
            startingCapital=alloc_cap,
            targetCapital=target_cap,
            activeTradingCapital=alloc_cap,
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=datetime.now(timezone.utc),
        )
        return self._repo.create_cycle(payload)

    def complete_and_advance_cycle(
        self, cycle_id: str, completed_capital: Decimal
    ) -> Tuple[CapitalCycleItem, CapitalCycleItem]:
        """
        Atomically complete cycle N and activate cycle N+1 inside a single database transaction.
        
        Guarantees that active capital is never duplicated and protected profit is never lost.
        """
        if not isinstance(completed_capital, Decimal):
            completed_capital = Decimal(str(completed_capital))

        cycle = self._repo.get_cycle_by_cycle_id(cycle_id)
        if not cycle:
            raise ValueError(f"Cycle '{cycle_id}' not found")

        if cycle.status not in (CapitalCycleStatus.ACTIVE, "ACTIVE"):
            raise ValueError(
                f"Cannot complete and advance cycle '{cycle_id}': status is '{cycle.status}', expected ACTIVE"
            )

        if completed_capital < cycle.targetCapital:
            raise ValueError(
                f"Cannot complete cycle below target: completed_capital ({completed_capital}) < target_capital ({cycle.targetCapital})"
            )

        realized_profit = completed_capital - cycle.startingCapital
        next_allocation = settings.CAPITAL_CYCLE_NEXT_ALLOCATION
        protected_profit = realized_profit - next_allocation

        if protected_profit < Decimal("0.00"):
            raise ValueError(
                f"Invalid accounting: protected profit cannot be negative ({protected_profit})"
            )

        now = datetime.now(timezone.utc)
        next_number = cycle.cycleNumber + 1
        next_id = f"cycle-{next_number}"

        next_payload = CapitalCycleCreate(
            cycleId=next_id,
            cycleNumber=next_number,
            startingCapital=next_allocation,
            targetCapital=settings.CAPITAL_CYCLE_TARGET,
            activeTradingCapital=next_allocation,
            protectedProfit=Decimal("0.00"),
            status=CapitalCycleStatus.ACTIVE,
            startedAt=now,
        )

        return self._repo.complete_and_advance_cycle(
            cycle_id=cycle_id,
            completed_capital=completed_capital,
            realized_profit=realized_profit,
            next_cycle_allocation=next_allocation,
            protected_profit=protected_profit,
            completed_at=now,
            next_cycle_payload=next_payload,
        )

    def halt_cycle(self, cycle_id: str, reason: str = "Halted by operator") -> CapitalCycleItem:
        """
        Halt an active cycle. A halted cycle cannot automatically continue or be advanced.
        """
        cycle = self._repo.get_cycle_by_cycle_id(cycle_id)
        if not cycle:
            raise ValueError(f"Cycle '{cycle_id}' not found")

        if cycle.status in (CapitalCycleStatus.COMPLETED, "COMPLETED"):
            raise ValueError(f"Cannot halt cycle '{cycle_id}': cycle is already COMPLETED")

        update_payload = CapitalCycleUpdate(status=CapitalCycleStatus.HALTED)
        updated = self._repo.update_cycle(cycle_id, update_payload)
        if not updated:
            raise RuntimeError(f"Failed to halt cycle '{cycle_id}'")
        return updated

    def update_active_capital(self, amount: Decimal) -> CapitalCycleItem:
        """
        Updates the active trading capital for the current active cycle to any user-defined amount
        (e.g. $50, $100, $500, $1000). If no active cycle exists, an initial cycle with this capital
        is created.
        """
        if amount <= Decimal("0.00"):
            raise ValueError("Active trading capital must be strictly positive")

        active = self.get_active_cycle()
        if not active:
            cycles = self._repo.list_cycles()
            next_num = len(cycles) + 1 if cycles else 1
            next_id = f"cycle-{next_num}"
            payload = CapitalCycleCreate(
                cycleId=next_id,
                cycleNumber=next_num,
                startingCapital=amount,
                targetCapital=max(amount * Decimal("5"), Decimal("500.00")),
                activeTradingCapital=amount,
                protectedProfit=Decimal("0.00"),
                status=CapitalCycleStatus.ACTIVE,
                startedAt=datetime.now(timezone.utc),
            )
            return self._repo.create_cycle(payload)

        update_payload = CapitalCycleUpdate(activeTradingCapital=amount)
        updated = self._repo.update_cycle(active.cycleId, update_payload)
        if not updated:
            raise RuntimeError(f"Failed to update active capital for cycle '{active.cycleId}'")
        return updated


capital_cycle_service = CapitalCycleService()
