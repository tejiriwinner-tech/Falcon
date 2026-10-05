"""Persistence for trade journal entries.

Mirrors the mission repository: Postgres (Supabase) when ``DATABASE_URL`` is
configured, process-local memory otherwise.
"""

import copy
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from sqlalchemy import func, select

from app.core.database.models import TradeJournalRecord
from app.core.database.session import database_enabled, get_session
from app.core.execution.execution_mode_guard import (
    inject_mode_token,
    parse_execution_mode,
)
from app.schemas.trade_journal import (
    TradeJournalCreate,
    TradeJournalItem,
    TradeJournalUpdate,
)

# Trades in these states are still live and must survive a history clear.
ACTIVE_TRADE_STATUSES = ("OPEN", "PENDING", "FILLED", "ACTIVE")

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
    # V10 Performance & Validation Mappings
    "fillTime": "fill_time",
    "fillPrice": "fill_price",
    "realizedRMultiple": "realized_r_multiple",
    "peakPrice": "peak_price",
    "troughPrice": "trough_price",
    "mfeR": "mfe_r",
    "maeR": "mae_r",
    "strategyVersion": "strategy_version",
    "adaptiveRuleVersion": "adaptive_rule_version",
    "adaptiveStopMultiplier": "adaptive_stop_multiplier",
    "spreadAtEntry": "spread_at_entry",
    "atrAtEntry": "atr_at_entry",
    "initialMonetaryRisk": "initial_monetary_risk",
}


def _to_item(record: TradeJournalRecord) -> TradeJournalItem:
    values = {field: getattr(record, column) for field, column in _COLUMNS.items()}
    parsed_mode = parse_execution_mode(getattr(record, "notes", None))
    values["executionMode"] = parsed_mode
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

    def list_trades(self, session: Optional[object] = None) -> List[TradeJournalItem]:
        return [
            copy.deepcopy(trade)
            for trade in sorted(
                self._trades.values(), key=lambda t: (t.tradeDate, t.id), reverse=True
            )
        ]

    def list_closed_trades_as_of(
        self,
        strategy_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> List[TradeJournalItem]:
        as_of_utc = (
            as_of.astimezone(timezone.utc)
            if (as_of and as_of.tzinfo)
            else (as_of.replace(tzinfo=timezone.utc) if as_of else None)
        )
        eligible: List[TradeJournalItem] = []
        for t in self._trades.values():
            if (t.status or "").upper() != "CLOSED":
                continue
            if t.closeDate is None:
                continue
            c_date = t.closeDate if t.closeDate.tzinfo else t.closeDate.replace(tzinfo=timezone.utc)
            if as_of_utc is not None and c_date > as_of_utc:
                continue
            if strategy_id is not None and t.strategyId != strategy_id:
                continue
            eligible.append(copy.deepcopy(t))

        def _sort_key(item: TradeJournalItem):
            t_date = item.tradeDate if item.tradeDate.tzinfo else item.tradeDate.replace(tzinfo=timezone.utc)
            return (t_date, item.id)

        return sorted(eligible, key=_sort_key, reverse=True)

    def get_trade(self, trade_id: int, session: Optional[object] = None) -> Optional[TradeJournalItem]:
        trade = self._trades.get(trade_id)
        return copy.deepcopy(trade) if trade else None

    def create_trade(self, payload: TradeJournalCreate, session: Optional[object] = None) -> TradeJournalItem:
        now = datetime.now(timezone.utc)
        with self._lock:
            trade_id = self._next_id
            self._next_id += 1
            dump = payload.model_dump()
            if payload.executionMode:
                dump["notes"] = inject_mode_token(dump.get("notes"), payload.executionMode)
                dump["executionMode"] = parse_execution_mode(dump["notes"]) or payload.executionMode
            else:
                dump["executionMode"] = parse_execution_mode(dump.get("notes"))
            item = TradeJournalItem(
                id=trade_id, createdAt=now, updatedAt=now, **dump
            )
            self._trades[trade_id] = item
        return copy.deepcopy(item)

    def update_trade(
        self, trade_id: int, payload: TradeJournalUpdate, session: Optional[object] = None
    ) -> Optional[TradeJournalItem]:
        with self._lock:
            trade = self._trades.get(trade_id)
            if trade is None:
                return None
            dump = payload.model_dump(exclude_unset=True)
            if "executionMode" in dump:
                current_notes = dump.get("notes", trade.notes)
                dump["notes"] = inject_mode_token(current_notes, dump["executionMode"])
                dump["executionMode"] = parse_execution_mode(dump["notes"]) or dump["executionMode"]
            elif "notes" in dump:
                dump["executionMode"] = parse_execution_mode(dump["notes"])
            updated = trade.model_copy(
                update={
                    **dump,
                    "updatedAt": datetime.now(timezone.utc),
                }
            )
            self._trades[trade_id] = updated
        return copy.deepcopy(updated)

    def delete_trade(self, trade_id: int, session: Optional[object] = None) -> bool:
        with self._lock:
            return self._trades.pop(trade_id, None) is not None

    def clear_history(self) -> int:
        """Delete finished trades only; active (OPEN/PENDING/FILLED) trades are kept."""
        with self._lock:
            to_del = [
                tid for tid, t in self._trades.items()
                if (t.status or "").upper() not in ACTIVE_TRADE_STATUSES
            ]
            for tid in to_del:
                del self._trades[tid]
            return len(to_del)

    def purge_invalid_trades(self) -> int:
        with self._lock:
            to_del = [
                tid for tid, t in self._trades.items()
                if t.direction.upper() not in ("BUY", "SELL") or t.entryPrice <= 0 or t.stopLoss <= 0 or t.takeProfit <= 0
            ]
            for tid in to_del:
                del self._trades[tid]
            return len(to_del)

    def cleanup_stale_open_trades(self, max_age_hours: int = 6) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        with self._lock:
            for tid, t in list(self._trades.items()):
                t_date = t.tradeDate if t.tradeDate.tzinfo else t.tradeDate.replace(tzinfo=timezone.utc)
                age_seconds = (now - t_date).total_seconds()
                if t.status.upper() in ("OPEN", "PENDING") and age_seconds > max_age_hours * 3600:
                    updated = t.model_copy(
                        update={
                            "status": "EXPIRED",
                            "result": "EXPIRED",
                            "closeDate": t.tradeDate,
                            "reasonForExit": f"Signal expired: untriggered after {round(age_seconds / 3600, 1)}h.",
                            "lessonLearned": "Patience preserved capital: order expired without reaching entry.",
                        }
                    )
                    self._trades[tid] = updated
                    count += 1
        return count


class DatabaseTradeJournalStorage:
    """Postgres-backed storage."""

    def clear(self) -> None:
        with get_session() as session:
            session.query(TradeJournalRecord).delete()
            session.commit()

    def list_trades(self, session: Optional[object] = None) -> List[TradeJournalItem]:
        if session is not None:
            records = session.scalars(
                select(TradeJournalRecord).order_by(
                    TradeJournalRecord.trade_date.desc(), TradeJournalRecord.id.desc()
                )
            ).all()
            return [_to_item(record) for record in records]
        with get_session() as session:
            records = session.scalars(
                select(TradeJournalRecord).order_by(
                    TradeJournalRecord.trade_date.desc(), TradeJournalRecord.id.desc()
                )
            ).all()
            return [_to_item(record) for record in records]

    def list_closed_trades_as_of(
        self,
        strategy_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> List[TradeJournalItem]:
        as_of_utc = (
            as_of.astimezone(timezone.utc)
            if (as_of and as_of.tzinfo)
            else (as_of.replace(tzinfo=timezone.utc) if as_of else None)
        )
        query = select(TradeJournalRecord).filter(
            TradeJournalRecord.status.in_(["CLOSED", "closed"]),
            TradeJournalRecord.close_date.isnot(None),
        )
        if strategy_id is not None:
            query = query.filter(TradeJournalRecord.strategy_id == strategy_id)
        if as_of_utc is not None:
            query = query.filter(TradeJournalRecord.close_date <= as_of_utc)

        query = query.order_by(
            TradeJournalRecord.trade_date.desc(), TradeJournalRecord.id.desc()
        )

        if session is not None:
            records = session.scalars(query).all()
            return [_to_item(record) for record in records]
        with get_session() as session:
            records = session.scalars(query).all()
            return [_to_item(record) for record in records]

    def get_trade(self, trade_id: int, session: Optional[object] = None) -> Optional[TradeJournalItem]:
        if session is not None:
            record = session.get(TradeJournalRecord, trade_id)
            return _to_item(record) if record else None
        with get_session() as session:
            record = session.get(TradeJournalRecord, trade_id)
            return _to_item(record) if record else None

    def create_trade(self, payload: TradeJournalCreate, session: Optional[object] = None) -> TradeJournalItem:
        now = datetime.now(timezone.utc)
        values = {
            column: getattr(payload, field) for field, column in _COLUMNS.items()
        }
        if payload.executionMode:
            values["notes"] = inject_mode_token(values.get("notes"), payload.executionMode)
        if session is not None:
            record = TradeJournalRecord(created_at=now, updated_at=now, **values)
            session.add(record)
            session.flush()
            session.refresh(record)
            return _to_item(record)
        with get_session() as session:
            record = TradeJournalRecord(created_at=now, updated_at=now, **values)
            session.add(record)
            session.commit()
            session.refresh(record)
            return _to_item(record)

    def update_trade(
        self, trade_id: int, payload: TradeJournalUpdate, session: Optional[object] = None
    ) -> Optional[TradeJournalItem]:
        if session is not None:
            record = session.get(TradeJournalRecord, trade_id)
            if record is None:
                return None
            dump = payload.model_dump(exclude_unset=True)
            mode_val = dump.pop("executionMode", None)
            if mode_val is not None:
                current_notes = dump.get("notes", getattr(record, "notes", None))
                dump["notes"] = inject_mode_token(current_notes, mode_val)
            for field, value in dump.items():
                if field in _COLUMNS:
                    setattr(record, _COLUMNS[field], value)
            record.updated_at = datetime.now(timezone.utc)
            session.flush()
            session.refresh(record)
            return _to_item(record)
        with get_session() as session:
            record = session.get(TradeJournalRecord, trade_id)
            if record is None:
                return None
            dump = payload.model_dump(exclude_unset=True)
            mode_val = dump.pop("executionMode", None)
            if mode_val is not None:
                current_notes = dump.get("notes", getattr(record, "notes", None))
                dump["notes"] = inject_mode_token(current_notes, mode_val)
            for field, value in dump.items():
                if field in _COLUMNS:
                    setattr(record, _COLUMNS[field], value)
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(record)
            return _to_item(record)


    def delete_trade(self, trade_id: int, session: Optional[object] = None) -> bool:
        if session is not None:
            record = session.get(TradeJournalRecord, trade_id)
            if record is None:
                return False
            session.delete(record)
            session.flush()
            return True
        with get_session() as session:
            record = session.get(TradeJournalRecord, trade_id)
            if record is None:
                return False
            session.delete(record)
            session.commit()
            return True

    def clear_history(self) -> int:
        """Delete finished trades only; active (OPEN/PENDING/FILLED) trades are kept."""
        with get_session() as session:
            count = (
                session.query(TradeJournalRecord)
                .filter(func.upper(TradeJournalRecord.status).notin_(ACTIVE_TRADE_STATUSES))
                .delete(synchronize_session=False)
            )
            session.commit()
            return count

    def purge_invalid_trades(self) -> int:
        with get_session() as session:
            count = session.query(TradeJournalRecord).filter(
                (TradeJournalRecord.direction.notin_(["BUY", "SELL"]))
                | (TradeJournalRecord.entry_price <= 0)
                | (TradeJournalRecord.stop_loss <= 0)
                | (TradeJournalRecord.take_profit <= 0)
            ).delete(synchronize_session=False)
            session.commit()
            return count

    def cleanup_stale_open_trades(self, max_age_hours: int = 6) -> int:
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        cutoff = now - timedelta(hours=max_age_hours)
        with get_session() as session:
            stale_records = session.query(TradeJournalRecord).filter(
                TradeJournalRecord.status.in_(["OPEN", "PENDING", "open", "pending"]),
                TradeJournalRecord.trade_date < cutoff
            ).all()
            count = len(stale_records)
            for rec in stale_records:
                rec.status = "EXPIRED"
                rec.result = "EXPIRED"
                rec.close_date = rec.trade_date + timedelta(minutes=45)
                rec.reason_for_exit = f"Signal expired: entry price was never triggered during active {round(max_age_hours, 1)}h window."
                rec.lesson_learned = "Patience preserved capital: untriggered order expired cleanly without chasing market."
                rec.updated_at = now
            session.commit()
            return count


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

    def __init__(self) -> None:
        self._cached_trades: Optional[List[TradeJournalItem]] = None
        self._cached_trades_at: float = 0.0
        self._cache_lock = threading.Lock()

    def _invalidate_cache(self) -> None:
        with self._cache_lock:
            self._cached_trades = None
            self._cached_trades_at = 0.0

    @property
    def persistent(self) -> bool:
        return isinstance(self._storage, DatabaseTradeJournalStorage)

    def list_trades(self, session: Optional[object] = None) -> List[TradeJournalItem]:
        import time as _t
        now_m = _t.monotonic()
        if session is None:
            with self._cache_lock:
                if self._cached_trades is not None and (now_m - self._cached_trades_at) < 15.0:
                    return [copy.deepcopy(t) for t in self._cached_trades]
        trades = self._storage.list_trades(session=session)
        if session is None:
            with self._cache_lock:
                self._cached_trades = trades
                self._cached_trades_at = _t.monotonic()
        return trades

    def list_closed_trades_as_of(
        self,
        strategy_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> List[TradeJournalItem]:
        return self._storage.list_closed_trades_as_of(
            strategy_id=strategy_id, as_of=as_of, session=session
        )

    def get_trade(self, trade_id: int, session: Optional[object] = None) -> Optional[TradeJournalItem]:
        return self._storage.get_trade(trade_id, session=session)

    def create_trade(self, payload: TradeJournalCreate, session: Optional[object] = None) -> TradeJournalItem:
        self._invalidate_cache()
        return self._storage.create_trade(payload, session=session)

    def update_trade(
        self, trade_id: int, payload: TradeJournalUpdate, session: Optional[object] = None
    ) -> Optional[TradeJournalItem]:
        self._invalidate_cache()
        return self._storage.update_trade(trade_id, payload, session=session)

    def delete_trade(self, trade_id: int, session: Optional[object] = None) -> bool:
        self._invalidate_cache()
        return self._storage.delete_trade(trade_id, session=session)

    def purge_invalid_trades(self) -> int:
        self._invalidate_cache()
        return self._storage.purge_invalid_trades()

    def cleanup_stale_open_trades(self, max_age_hours: int = 6) -> int:
        self._invalidate_cache()
        return self._storage.cleanup_stale_open_trades(max_age_hours)

    def clear_history(self) -> int:
        """Delete finished trades (WIN/LOSS/BREAKEVEN/EXPIRED...), keep active ones."""
        self._invalidate_cache()
        return self._storage.clear_history()

    def clear(self) -> None:
        """Clear all stored entries (for testing purposes only)."""
        self._invalidate_cache()
        self._storage.clear()


trade_journal_repository = TradeJournalRepository()
