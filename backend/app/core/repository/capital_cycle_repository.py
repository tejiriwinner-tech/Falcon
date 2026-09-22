"""
Falcon Capital Cycle Repository (V10 Phase 2)
Persistence layer supporting PostgreSQL (Supabase) and process-local in-memory storage.
"""

import copy
import threading
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Union

from sqlalchemy import select

from app.core.database.models import CapitalCycleRecord
from app.core.database.session import database_enabled, get_session
from app.schemas.capital_cycle import (
    CapitalCycleCreate,
    CapitalCycleItem,
    CapitalCycleStatus,
    CapitalCycleUpdate,
)

_COLUMNS: Dict[str, str] = {
    "cycleId": "cycle_id",
    "cycleNumber": "cycle_number",
    "startingCapital": "starting_capital",
    "targetCapital": "target_capital",
    "activeTradingCapital": "active_trading_capital",
    "protectedProfit": "protected_profit",
    "status": "status",
    "startedAt": "started_at",
    "completedAt": "completed_at",
    "completedCapital": "completed_capital",
    "realizedProfit": "realized_profit",
    "nextCycleAllocation": "next_cycle_allocation",
}


def _to_item(record: CapitalCycleRecord) -> CapitalCycleItem:
    values = {field: getattr(record, column) for field, column in _COLUMNS.items()}
    return CapitalCycleItem(
        id=record.id,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        **values,
    )


class InMemoryCapitalCycleStorage:
    """Process-local in-memory storage for testing and non-DB local runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.clear()

    def clear(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self._cycles: Dict[str, CapitalCycleItem] = {}
            self._next_id = 1

    def list_cycles(self) -> List[CapitalCycleItem]:
        with self._lock:
            return [
                copy.deepcopy(c)
                for c in sorted(self._cycles.values(), key=lambda x: x.cycleNumber)
            ]

    def get_cycle_by_id(self, id_: int) -> Optional[CapitalCycleItem]:
        with self._lock:
            for c in self._cycles.values():
                if c.id == id_:
                    return copy.deepcopy(c)
            return None

    def get_cycle_by_cycle_id(self, cycle_id: str) -> Optional[CapitalCycleItem]:
        with self._lock:
            c = self._cycles.get(cycle_id)
            return copy.deepcopy(c) if c else None

    def get_active_cycle(self, session: Optional[object] = None) -> Optional[CapitalCycleItem]:
        with self._lock:
            for c in self._cycles.values():
                if c.status == CapitalCycleStatus.ACTIVE or c.status == "ACTIVE":
                    return copy.deepcopy(c)
            return None

    def get_latest_cycle(self) -> Optional[CapitalCycleItem]:
        with self._lock:
            if not self._cycles:
                return None
            sorted_cycles = sorted(self._cycles.values(), key=lambda x: x.cycleNumber, reverse=True)
            return copy.deepcopy(sorted_cycles[0])

    def create_cycle(self, payload: CapitalCycleCreate) -> CapitalCycleItem:
        now = datetime.now(timezone.utc)
        with self._lock:
            # Enforce single active cycle invariant
            if payload.status == CapitalCycleStatus.ACTIVE or payload.status == "ACTIVE":
                for c in self._cycles.values():
                    if c.status == CapitalCycleStatus.ACTIVE or c.status == "ACTIVE":
                        raise ValueError(f"Cannot create active cycle: cycle '{c.cycleId}' is already ACTIVE")

            if payload.cycleId in self._cycles:
                raise ValueError(f"Cycle with ID '{payload.cycleId}' already exists")

            for c in self._cycles.values():
                if c.cycleNumber == payload.cycleNumber:
                    raise ValueError(f"Cycle with number '{payload.cycleNumber}' already exists")

            cycle_id = payload.cycleId
            item = CapitalCycleItem(
                id=self._next_id,
                cycleId=cycle_id,
                cycleNumber=payload.cycleNumber,
                startingCapital=payload.startingCapital,
                targetCapital=payload.targetCapital,
                activeTradingCapital=payload.activeTradingCapital,
                protectedProfit=payload.protectedProfit,
                status=payload.status,
                startedAt=payload.startedAt or now,
                completedAt=None,
                completedCapital=None,
                realizedProfit=None,
                nextCycleAllocation=None,
                createdAt=now,
                updatedAt=now,
            )
            self._next_id += 1
            self._cycles[cycle_id] = item
            return copy.deepcopy(item)

    def update_cycle(
        self, cycle_id: str, payload: CapitalCycleUpdate
    ) -> Optional[CapitalCycleItem]:
        now = datetime.now(timezone.utc)
        with self._lock:
            current = self._cycles.get(cycle_id)
            if not current:
                return None

            update_data = payload.model_dump(exclude_unset=True)

            # Check active status conflict
            if update_data.get("status") in (CapitalCycleStatus.ACTIVE, "ACTIVE"):
                for cid, c in self._cycles.items():
                    if cid != cycle_id and c.status in (CapitalCycleStatus.ACTIVE, "ACTIVE"):
                        raise ValueError(f"Cannot set cycle '{cycle_id}' to ACTIVE: cycle '{c.cycleId}' is already ACTIVE")

            updated = current.model_copy(
                update={
                    **update_data,
                    "updatedAt": now,
                }
            )
            self._cycles[cycle_id] = updated
            return copy.deepcopy(updated)

    def complete_and_advance_cycle(
        self,
        cycle_id: str,
        completed_capital: Decimal,
        realized_profit: Decimal,
        next_cycle_allocation: Decimal,
        protected_profit: Decimal,
        completed_at: datetime,
        next_cycle_payload: CapitalCycleCreate,
    ) -> Tuple[CapitalCycleItem, CapitalCycleItem]:
        now = datetime.now(timezone.utc)
        with self._lock:
            current = self._cycles.get(cycle_id)
            if not current:
                raise ValueError(f"Cycle '{cycle_id}' not found")
            if current.status not in (CapitalCycleStatus.ACTIVE, "ACTIVE"):
                raise ValueError(f"Cycle '{cycle_id}' is not ACTIVE (status: {current.status})")

            # Complete current cycle
            completed_cycle = current.model_copy(
                update={
                    "status": CapitalCycleStatus.COMPLETED,
                    "completedCapital": completed_capital,
                    "realizedProfit": realized_profit,
                    "nextCycleAllocation": next_cycle_allocation,
                    "protectedProfit": protected_profit,
                    "completedAt": completed_at,
                    "updatedAt": now,
                }
            )
            self._cycles[cycle_id] = completed_cycle

            # Advance to next cycle
            next_item = CapitalCycleItem(
                id=self._next_id,
                cycleId=next_cycle_payload.cycleId,
                cycleNumber=next_cycle_payload.cycleNumber,
                startingCapital=next_cycle_payload.startingCapital,
                targetCapital=next_cycle_payload.targetCapital,
                activeTradingCapital=next_cycle_payload.activeTradingCapital,
                protectedProfit=next_cycle_payload.protectedProfit,
                status=next_cycle_payload.status,
                startedAt=next_cycle_payload.startedAt or now,
                completedAt=None,
                completedCapital=None,
                realizedProfit=None,
                nextCycleAllocation=None,
                createdAt=now,
                updatedAt=now,
            )
            self._next_id += 1
            self._cycles[next_cycle_payload.cycleId] = next_item
            return copy.deepcopy(completed_cycle), copy.deepcopy(next_item)


class DatabaseCapitalCycleStorage:
    """PostgreSQL/SQLAlchemy-backed storage for capital cycles."""

    def clear(self) -> None:
        with get_session() as session:
            session.query(CapitalCycleRecord).delete()
            session.commit()

    def list_cycles(self) -> List[CapitalCycleItem]:
        with get_session() as session:
            records = session.scalars(
                select(CapitalCycleRecord).order_by(CapitalCycleRecord.cycle_number.asc())
            ).all()
            return [_to_item(r) for r in records]

    def get_cycle_by_id(self, id_: int) -> Optional[CapitalCycleItem]:
        with get_session() as session:
            record = session.get(CapitalCycleRecord, id_)
            return _to_item(record) if record else None

    def get_cycle_by_cycle_id(self, cycle_id: str) -> Optional[CapitalCycleItem]:
        with get_session() as session:
            record = session.scalars(
                select(CapitalCycleRecord).where(CapitalCycleRecord.cycle_id == cycle_id)
            ).first()
            return _to_item(record) if record else None

    def get_active_cycle(self, session: Optional[object] = None) -> Optional[CapitalCycleItem]:
        if session is not None:
            record = session.scalars(
                select(CapitalCycleRecord).where(CapitalCycleRecord.status == "ACTIVE")
            ).first()
            return _to_item(record) if record else None

        with get_session() as session:
            record = session.scalars(
                select(CapitalCycleRecord).where(CapitalCycleRecord.status == "ACTIVE")
            ).first()
            return _to_item(record) if record else None

    def get_latest_cycle(self) -> Optional[CapitalCycleItem]:
        with get_session() as session:
            record = session.scalars(
                select(CapitalCycleRecord).order_by(CapitalCycleRecord.cycle_number.desc())
            ).first()
            return _to_item(record) if record else None

    def create_cycle(self, payload: CapitalCycleCreate) -> CapitalCycleItem:
        now = datetime.now(timezone.utc)
        status_val = payload.status.value if hasattr(payload.status, "value") else str(payload.status)

        with get_session() as session:
            # Check active cycle collision before insert
            if status_val == "ACTIVE":
                active_existing = session.scalars(
                    select(CapitalCycleRecord).where(CapitalCycleRecord.status == "ACTIVE")
                ).first()
                if active_existing:
                    raise ValueError(
                        f"Cannot create active cycle: cycle '{active_existing.cycle_id}' is already ACTIVE"
                    )

            record = CapitalCycleRecord(
                cycle_id=payload.cycleId,
                cycle_number=payload.cycleNumber,
                starting_capital=payload.startingCapital,
                target_capital=payload.targetCapital,
                active_trading_capital=payload.activeTradingCapital,
                protected_profit=payload.protectedProfit,
                status=status_val,
                started_at=payload.startedAt or now,
                completed_at=None,
                completed_capital=None,
                realized_profit=None,
                next_cycle_allocation=None,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_item(record)

    def update_cycle(
        self, cycle_id: str, payload: CapitalCycleUpdate
    ) -> Optional[CapitalCycleItem]:
        now = datetime.now(timezone.utc)
        with get_session() as session:
            record = session.scalars(
                select(CapitalCycleRecord).where(CapitalCycleRecord.cycle_id == cycle_id)
            ).first()
            if not record:
                return None

            update_data = payload.model_dump(exclude_unset=True)

            if update_data.get("status"):
                new_status = (
                    update_data["status"].value
                    if hasattr(update_data["status"], "value")
                    else str(update_data["status"])
                )
                if new_status == "ACTIVE":
                    active_existing = session.scalars(
                        select(CapitalCycleRecord).where(
                            CapitalCycleRecord.status == "ACTIVE",
                            CapitalCycleRecord.cycle_id != cycle_id,
                        )
                    ).first()
                    if active_existing:
                        raise ValueError(
                            f"Cannot set cycle '{cycle_id}' to ACTIVE: cycle '{active_existing.cycle_id}' is already ACTIVE"
                        )
                record.status = new_status

            if "activeTradingCapital" in update_data:
                record.active_trading_capital = update_data["activeTradingCapital"]
            if "protectedProfit" in update_data:
                record.protected_profit = update_data["protectedProfit"]
            if "completedAt" in update_data:
                record.completed_at = update_data["completedAt"]
            if "completedCapital" in update_data:
                record.completed_capital = update_data["completedCapital"]
            if "realizedProfit" in update_data:
                record.realized_profit = update_data["realizedProfit"]
            if "nextCycleAllocation" in update_data:
                record.next_cycle_allocation = update_data["nextCycleAllocation"]

            record.updated_at = now
            session.commit()
            session.refresh(record)
            return _to_item(record)

    def complete_and_advance_cycle(
        self,
        cycle_id: str,
        completed_capital: Decimal,
        realized_profit: Decimal,
        next_cycle_allocation: Decimal,
        protected_profit: Decimal,
        completed_at: datetime,
        next_cycle_payload: CapitalCycleCreate,
    ) -> Tuple[CapitalCycleItem, CapitalCycleItem]:
        now = datetime.now(timezone.utc)
        with get_session() as session:
            # Single atomic transaction
            record = session.scalars(
                select(CapitalCycleRecord).where(CapitalCycleRecord.cycle_id == cycle_id)
            ).first()
            if not record:
                raise ValueError(f"Cycle '{cycle_id}' not found")
            if record.status != "ACTIVE":
                raise ValueError(f"Cycle '{cycle_id}' is not ACTIVE (status: {record.status})")

            # 1. Update current cycle to COMPLETED
            record.status = "COMPLETED"
            record.completed_capital = completed_capital
            record.realized_profit = realized_profit
            record.next_cycle_allocation = next_cycle_allocation
            record.protected_profit = protected_profit
            record.completed_at = completed_at
            record.updated_at = now

            # 2. Insert next cycle as ACTIVE
            next_status = (
                next_cycle_payload.status.value
                if hasattr(next_cycle_payload.status, "value")
                else str(next_cycle_payload.status)
            )
            next_record = CapitalCycleRecord(
                cycle_id=next_cycle_payload.cycleId,
                cycle_number=next_cycle_payload.cycleNumber,
                starting_capital=next_cycle_payload.startingCapital,
                target_capital=next_cycle_payload.targetCapital,
                active_trading_capital=next_cycle_payload.activeTradingCapital,
                protected_profit=next_cycle_payload.protectedProfit,
                status=next_status,
                started_at=next_cycle_payload.startedAt or now,
                completed_at=None,
                completed_capital=None,
                realized_profit=None,
                next_cycle_allocation=None,
                created_at=now,
                updated_at=now,
            )
            session.add(next_record)
            session.commit()

            session.refresh(record)
            session.refresh(next_record)
            return _to_item(record), _to_item(next_record)


Storage = Union[InMemoryCapitalCycleStorage, DatabaseCapitalCycleStorage]


class CapitalCycleRepository:
    """Repository facade selecting Database or InMemory storage based on environment."""

    def __init__(self, storage: Optional[Storage] = None) -> None:
        if storage is not None:
            self._storage = storage
        elif database_enabled():
            self._storage = DatabaseCapitalCycleStorage()
        else:
            self._storage = InMemoryCapitalCycleStorage()

    def list_cycles(self) -> List[CapitalCycleItem]:
        return self._storage.list_cycles()

    def get_cycle_by_id(self, id_: int) -> Optional[CapitalCycleItem]:
        return self._storage.get_cycle_by_id(id_)

    def get_cycle_by_cycle_id(self, cycle_id: str) -> Optional[CapitalCycleItem]:
        return self._storage.get_cycle_by_cycle_id(cycle_id)

    def get_active_cycle(self, session: Optional[object] = None) -> Optional[CapitalCycleItem]:
        return self._storage.get_active_cycle(session=session)

    def get_latest_cycle(self) -> Optional[CapitalCycleItem]:
        return self._storage.get_latest_cycle()

    def create_cycle(self, payload: CapitalCycleCreate) -> CapitalCycleItem:
        return self._storage.create_cycle(payload)

    def update_cycle(
        self, cycle_id: str, payload: CapitalCycleUpdate
    ) -> Optional[CapitalCycleItem]:
        return self._storage.update_cycle(cycle_id, payload)

    def complete_and_advance_cycle(
        self,
        cycle_id: str,
        completed_capital: Decimal,
        realized_profit: Decimal,
        next_cycle_allocation: Decimal,
        protected_profit: Decimal,
        completed_at: datetime,
        next_cycle_payload: CapitalCycleCreate,
    ) -> Tuple[CapitalCycleItem, CapitalCycleItem]:
        return self._storage.complete_and_advance_cycle(
            cycle_id=cycle_id,
            completed_capital=completed_capital,
            realized_profit=realized_profit,
            next_cycle_allocation=next_cycle_allocation,
            protected_profit=protected_profit,
            completed_at=completed_at,
            next_cycle_payload=next_cycle_payload,
        )

    def clear(self) -> None:
        self._storage.clear()


capital_cycle_repository = CapitalCycleRepository()
