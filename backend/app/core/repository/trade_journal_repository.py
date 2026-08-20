"""Persistence for trade journal entries.

Mirrors the mission repository: Postgres (Supabase) when ``DATABASE_URL`` is
configured, process-local memory otherwise.
"""

import copy
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from sqlalchemy import select

from app.core.database.models import TradeJournalRecord
from app.core.database.session import database_enabled, get_session
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalItem,
    TradeJournalUpdate,
)

_COLUMNS: Dict[str, str] = {
    "signalId": "signal_id",
    "strategyId": "strategy_id",
    "symbol": "symbol",
    "direction": "direction",
    "entryPrice": "entry_price",
    "exitPrice": "exit_price",
    "stopLoss": "stop_loss",
    "takeProfit": "take_profit",
    "timeframe": "timeframe",
    "marketSession": "market_session",
    "tradeDate": "trade_date",
    "closeDate": "close_date",
    "status": "status",
    "result": "result",
    "profitLoss": "profit_loss",
    "riskReward": "risk_reward",
    "confidence": "confidence",
    "reasonForEntry": "reason_for_entry",
    "reasonForExit": "reason_for_exit",
    "lessonLearned": "lesson_learned",
    "notes": "notes",
}


def _to_item(record: TradeJournalRecord) -> TradeJournalItem:
    values = {field: getattr(record, column) for field, column in _COLUMNS.items()}
    return TradeJournalItem(
        id=record.id,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        **values,
    )


class InMemoryTradeJournalStorage:
    """Process-local storage. Entries are lost when the process restarts."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.clear()

    def clear(self) -> None:
        self._trades: Dict[int, TradeJournalItem] = {}
        self._next_id = 1

    def list_trades(self) -> List[TradeJournalItem]:
        return [
            copy.deepcopy(trade)
            for trade in sorted(
                self._trades.values(), key=lambda t: (t.tradeDate, t.id), reverse=True
            )
        ]

    def get_trade(self, trade_id: int) -> Optional[TradeJournalItem]:
        trade = self._trades.get(trade_id)
        return copy.deepcopy(trade) if trade else None

    def create_trade(self, payload: TradeJournalCreate) -> TradeJournalItem:
        now = datetime.now(timezone.utc)
        with self._lock:
            trade_id = self._next_id
            self._next_id += 1
            item = TradeJournalItem(
                id=trade_id, createdAt=now, updatedAt=now, **payload.model_dump()
            )
            self._trades[trade_id] = item
        return copy.deepcopy(item)

    def update_trade(
        self, trade_id: int, payload: TradeJournalUpdate
    ) -> Optional[TradeJournalItem]:
        with self._lock:
            trade = self._trades.get(trade_id)
            if trade is None:
                return None
            updated = trade.model_copy(
                update={
                    **payload.model_dump(exclude_unset=True),
                    "updatedAt": datetime.now(timezone.utc),
                }
            )
            self._trades[trade_id] = updated
        return copy.deepcopy(updated)

    def delete_trade(self, trade_id: int) -> bool:
        with self._lock:
            return self._trades.pop(trade_id, None) is not None


class DatabaseTradeJournalStorage:
    """Postgres-backed storage."""

    def clear(self) -> None:
        with get_session() as session:
            session.query(TradeJournalRecord).delete()
            session.commit()

    def list_trades(self) -> List[TradeJournalItem]:
        with get_session() as session:
            records = session.scalars(
                select(TradeJournalRecord).order_by(
                    TradeJournalRecord.trade_date.desc(), TradeJournalRecord.id.desc()
                )
            ).all()
            return [_to_item(record) for record in records]

    def get_trade(self, trade_id: int) -> Optional[TradeJournalItem]:
        with get_session() as session:
            record = session.get(TradeJournalRecord, trade_id)
            return _to_item(record) if record else None

    def create_trade(self, payload: TradeJournalCreate) -> TradeJournalItem:
        now = datetime.now(timezone.utc)
        values = {
            column: getattr(payload, field) for field, column in _COLUMNS.items()
        }
        with get_session() as session:
            record = TradeJournalRecord(created_at=now, updated_at=now, **values)
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_item(record)

    def update_trade(
        self, trade_id: int, payload: TradeJournalUpdate
    ) -> Optional[TradeJournalItem]:
        with get_session() as session:
            record = session.get(TradeJournalRecord, trade_id)
            if record is None:
                return None
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(record, _COLUMNS[field], value)
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return _to_item(record)

    def delete_trade(self, trade_id: int) -> bool:
        with get_session() as session:
            record = session.get(TradeJournalRecord, trade_id)
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True


Storage = Union[InMemoryTradeJournalStorage, DatabaseTradeJournalStorage]


class TradeJournalRepository:
    """Singleton facade over the configured trade journal storage backend."""

    _instance: Optional["TradeJournalRepository"] = None

    def __new__(cls) -> "TradeJournalRepository":
        if cls._instance is None:
            cls._instance = super(TradeJournalRepository, cls).__new__(cls)
            cls._instance._init_storage()
        return cls._instance

    def _init_storage(self) -> None:
        self._storage: Storage = (
            DatabaseTradeJournalStorage()
            if database_enabled()
            else InMemoryTradeJournalStorage()
        )

    @property
    def persistent(self) -> bool:
        return isinstance(self._storage, DatabaseTradeJournalStorage)

    def list_trades(self) -> List[TradeJournalItem]:
        return self._storage.list_trades()

    def get_trade(self, trade_id: int) -> Optional[TradeJournalItem]:
        return self._storage.get_trade(trade_id)

    def create_trade(self, payload: TradeJournalCreate) -> TradeJournalItem:
        return self._storage.create_trade(payload)

    def update_trade(
        self, trade_id: int, payload: TradeJournalUpdate
    ) -> Optional[TradeJournalItem]:
        return self._storage.update_trade(trade_id, payload)

    def delete_trade(self, trade_id: int) -> bool:
        return self._storage.delete_trade(trade_id)

    def clear(self) -> None:
        """Clear all stored entries (for testing purposes only)."""
        self._storage.clear()


trade_journal_repository = TradeJournalRepository()
