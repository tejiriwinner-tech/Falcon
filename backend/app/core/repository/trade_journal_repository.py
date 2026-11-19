"""Persistence for trade journal entries.

Mirrors the mission repository: Postgres (Supabase) when ``DATABASE_URL`` is
configured, process-local memory otherwise.
"""

import copy
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union

from sqlalchemy import func, select, text

logger = logging.getLogger("falcon.trade_journal_repository")

from app.core.database.models import TradeJournalRecord
from app.core.database.session import database_enabled, get_session
from app.core.execution.execution_mode_guard import (
    inject_mode_token,
    parse_execution_mode,
    resolve_record_execution_mode,
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
    "initialStopLoss": "initial_stop_loss",
    "initialMonetaryRisk": "initial_monetary_risk",
}


def _to_item(record: TradeJournalRecord) -> TradeJournalItem:
    values = {field: getattr(record, column) for field, column in _COLUMNS.items()}
    raw_mode = getattr(record, "execution_mode", None)
    notes_val = getattr(record, "notes", None)
    values["executionMode"] = resolve_record_execution_mode(raw_mode, notes_val)
    return TradeJournalItem(
        id=record.id,
        createdAt=record.created_at,
        updatedAt=record.updated_at,
        **values,
    )



import json
import os

PERSISTENCE_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "paper_trade_journal.json")
)


class InMemoryTradeJournalStorage:
    """Process-local storage with optional durable disk persistence across restarts."""

    def __init__(self, persistence_file: Optional[str] = None) -> None:
        self._lock = threading.Lock()
        self._trades: Dict[int, TradeJournalItem] = {}
        self._next_id = 1
        self._persistence_file = persistence_file
        if self._persistence_file:
            self._load_from_disk()

    def _save_to_disk(self) -> None:
        if not self._persistence_file:
            return
        try:
            os.makedirs(os.path.dirname(self._persistence_file), exist_ok=True)
            tmp_file = f"{self._persistence_file}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump([t.model_dump(mode="json") for t in self._trades.values()], f, indent=2)
            os.replace(tmp_file, self._persistence_file)
        except Exception as ex:
            logger.debug(f"Failed to persist paper journal: {ex}")

    def _load_from_disk(self) -> None:
        if not self._persistence_file:
            return
        try:
            if os.path.exists(self._persistence_file):
                with open(self._persistence_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            t = TradeJournalItem(**item)
                            self._trades[t.id] = t
                        if self._trades:
                            self._next_id = max(self._trades.keys()) + 1
        except Exception as ex:
            logger.debug(f"Failed to load persisted paper journal: {ex}")

    def clear(self) -> None:
        with self._lock:
            self._trades: Dict[int, TradeJournalItem] = {}
            self._next_id = 1
            if self._persistence_file:
                try:
                    if os.path.exists(self._persistence_file):
                        os.remove(self._persistence_file)
                except Exception:
                    pass

    def list_trades(self, session: Optional[object] = None) -> List[TradeJournalItem]:
        def _sort_key(t: TradeJournalItem):
            dt = t.tradeDate
            if dt is None:
                return (0.0, t.id or 0)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (dt.timestamp(), t.id or 0)

        with self._lock:
            snapshot = list(self._trades.values())
        return [
            copy.deepcopy(trade)
            for trade in sorted(
                snapshot, key=_sort_key, reverse=True
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
        with self._lock:
            snapshot = list(self._trades.values())
        for t in snapshot:
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
        with self._lock:
            trade = self._trades.get(trade_id)
            return copy.deepcopy(trade) if trade else None

    def create_trade(self, payload: TradeJournalCreate, session: Optional[object] = None) -> TradeJournalItem:
        now = datetime.now(timezone.utc)
        with self._lock:
            trade_id = self._next_id
            self._next_id += 1
            dump = payload.model_dump()
            if dump.get("initialStopLoss") is None and dump.get("stopLoss") is not None:
                dump["initialStopLoss"] = float(dump["stopLoss"])
            dump["executionMode"] = resolve_record_execution_mode(payload.executionMode, dump.get("notes"))
            if payload.executionMode and dump["executionMode"]:
                dump["notes"] = inject_mode_token(dump.get("notes"), dump["executionMode"])
            item = TradeJournalItem(
                id=trade_id, createdAt=now, updatedAt=now, **dump
            )
            self._trades[trade_id] = item
            self._save_to_disk()
        return copy.deepcopy(item)

    def sync_authoritative_item(self, item: TradeJournalItem) -> None:
        """Synchronize an authoritative database item into fallback storage."""
        with self._lock:
            self._trades[item.id] = copy.deepcopy(item)
            if item.id >= self._next_id:
                self._next_id = item.id + 1
            self._save_to_disk()

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
            self._save_to_disk()
        return copy.deepcopy(updated)

    def delete_trade(self, trade_id: int, session: Optional[object] = None) -> bool:
        with self._lock:
            res = self._trades.pop(trade_id, None) is not None
            if res:
                self._save_to_disk()
            return res

    def clear_history(self) -> int:
        """Delete finished trades only; active (OPEN/PENDING/FILLED) trades are kept."""
        with self._lock:
            to_del = [
                tid for tid, t in self._trades.items()
                if (t.status or "").upper() not in ACTIVE_TRADE_STATUSES
            ]
            for tid in to_del:
                del self._trades[tid]
            if to_del:
                self._save_to_disk()
            return len(to_del)

    def purge_invalid_trades(self) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        with self._lock:
            for tid, t in list(self._trades.items()):
                if (t.status or "").upper() in ("OPEN", "PENDING") and (
                    t.direction.upper() not in ("BUY", "SELL") or t.entryPrice <= 0 or t.stopLoss <= 0 or t.takeProfit <= 0
                ):
                    self._trades[tid] = t.model_copy(
                        update={
                            "status": "INVALIDATED",
                            "result": "INVALIDATED",
                            "closeDate": t.closeDate or now,
                            "updatedAt": now,
                        }
                    )
                    count += 1
            if count > 0:
                self._save_to_disk()
            return count

    def cleanup_stale_open_trades(self, max_age_hours: int = 6) -> int:
        now = datetime.now(timezone.utc)
        count = 0
        with self._lock:
            for tid, t in list(self._trades.items()):
                t_date = t.tradeDate if t.tradeDate.tzinfo else t.tradeDate.replace(tzinfo=timezone.utc)
                age_seconds = (now - t_date).total_seconds()
                is_filled_active = (t.status or "").upper() == "OPEN" and (t.fillPrice is not None and float(t.fillPrice or 0.0) > 0.0) and (t.result or "").upper() != "PENDING"
                eff_max_s = (48 * 3600) if (is_filled_active and max_age_hours > 0) else (max_age_hours * 3600)
                if t.status.upper() in ("OPEN", "PENDING") and age_seconds > eff_max_s:
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
    """Postgres-backed storage with automatic in-memory fallback for high availability."""

    def __init__(self, persistence_file: Optional[str] = PERSISTENCE_FILE) -> None:
        self._lock = threading.Lock()
        self._persistence_file = persistence_file
        self._fallback_memory = InMemoryTradeJournalStorage(persistence_file=persistence_file)
        self._outbox_pending_ids: set = set()
        self._outbox_file = (
            persistence_file.replace(".json", "_outbox.json")
            if persistence_file and persistence_file.endswith(".json")
            else (persistence_file + ".outbox" if persistence_file else None)
        )
        self._load_outbox_from_disk()

    def _save_outbox_to_disk(self) -> None:
        if not self._outbox_file:
            return
        try:
            os.makedirs(os.path.dirname(self._outbox_file), exist_ok=True)
            tmp_out = f"{self._outbox_file}.tmp"
            with open(tmp_out, "w", encoding="utf-8") as f:
                json.dump(sorted(list(self._outbox_pending_ids)), f)
            os.replace(tmp_out, self._outbox_file)
        except Exception as ex:
            logger.debug(f"Failed to persist outbox state: {ex}")

    def _load_outbox_from_disk(self) -> None:
        if not self._outbox_file or not os.path.exists(self._outbox_file):
            return
        try:
            with open(self._outbox_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._outbox_pending_ids = set(data)
        except Exception as ex:
            logger.debug(f"Failed to load persisted outbox state: {ex}")

    def _get_logical_key(self, trade: Union[TradeJournalItem, TradeJournalRecord]) -> str:
        if isinstance(trade, TradeJournalRecord):
            sig = getattr(trade, "signal_id", None) or ""
            strat = getattr(trade, "strategy_id", None) or ""
            sym = getattr(trade, "symbol", "") or ""
            d = getattr(trade, "direction", "") or ""
            ep = round(float(getattr(trade, "entry_price", 0.0) or 0.0), 5)
            dt_str = str(getattr(trade, "trade_date", "") or "")[:19]
            if sig:
                return f"{sig}:{strat}:{sym}:{d}"
            return f"{strat}:{sym}:{d}:{ep}:{dt_str}"
        else:
            sig = getattr(trade, "signalId", None) or ""
            strat = getattr(trade, "strategyId", None) or ""
            sym = getattr(trade, "symbol", "") or ""
            d = getattr(trade, "direction", "") or ""
            ep = round(float(getattr(trade, "entryPrice", 0.0) or 0.0), 5)
            dt_str = str(getattr(trade, "tradeDate", "") or "")[:19]
            if sig:
                return f"{sig}:{strat}:{sym}:{d}"
            return f"{strat}:{sym}:{d}:{ep}:{dt_str}"

    def clear(self) -> None:
        with self._lock:
            try:
                with get_session() as session:
                    session.query(TradeJournalRecord).delete()
                    session.commit()
            except Exception as ex:
                logger.warning(f"Database clear failed: {ex}")
            self._fallback_memory.clear()
            self._outbox_pending_ids.clear()
            self._save_outbox_to_disk()

    def list_trades(self, session: Optional[object] = None) -> List[TradeJournalItem]:
        db_trades: List[TradeJournalItem] = []
        db_error = False
        try:
            if session is not None:
                records = session.scalars(
                    select(TradeJournalRecord).order_by(
                        TradeJournalRecord.trade_date.desc(), TradeJournalRecord.id.desc()
                    )
                ).all()
                db_trades = [_to_item(record) for record in records]
            else:
                with get_session() as session_ctx:
                    records = session_ctx.scalars(
                        select(TradeJournalRecord).order_by(
                            TradeJournalRecord.trade_date.desc(), TradeJournalRecord.id.desc()
                        )
                    ).all()
                    db_trades = [_to_item(record) for record in records]
        except Exception as ex:
            db_error = True
            logger.warning(f"Database list_trades failed: {ex}")

        fallback_trades = self._fallback_memory.list_trades()
        if db_error or not db_trades:
            return fallback_trades
        if not fallback_trades:
            return db_trades

        db_by_key = {self._get_logical_key(item): item for item in db_trades}
        mem_by_key = {self._get_logical_key(item): item for item in fallback_trades}

        all_keys = list(db_by_key.keys()) + [k for k in mem_by_key if k not in db_by_key]
        merged = []
        for k in all_keys:
            if k in db_by_key and k in mem_by_key:
                d_item = db_by_key[k]
                m_item = mem_by_key[k]
                if (m_item.status or "").upper() in ("CLOSED", "EXPIRED", "FILLED") and (d_item.status or "").upper() in ("OPEN", "PENDING"):
                    merged.append(m_item)
                else:
                    merged.append(d_item)
            elif k in db_by_key:
                merged.append(db_by_key[k])
            else:
                merged.append(mem_by_key[k])

        def _sort_key(t: TradeJournalItem):
            dt = t.tradeDate
            if dt is None:
                return (0.0, t.id or 0)
            if getattr(dt, "tzinfo", None) is None and hasattr(dt, "replace"):
                dt = dt.replace(tzinfo=timezone.utc)
            ts = dt.timestamp() if hasattr(dt, "timestamp") else 0.0
            return (ts, t.id or 0)

        merged.sort(key=_sort_key, reverse=True)
        return merged

    def list_closed_trades_as_of(
        self,
        strategy_id: Optional[str] = None,
        as_of: Optional[datetime] = None,
        session: Optional[object] = None,
    ) -> List[TradeJournalItem]:
        db_closed: List[TradeJournalItem] = []
        db_error = False
        try:
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
                db_closed = [_to_item(record) for record in records]
            else:
                with get_session() as session_ctx:
                    records = session_ctx.scalars(query).all()
                    db_closed = [_to_item(record) for record in records]
        except Exception as ex:
            db_error = True
            logger.warning(f"Database list_closed_trades_as_of failed: {ex}")

        mem_closed = self._fallback_memory.list_closed_trades_as_of(strategy_id, as_of)
        if db_error or not db_closed:
            return mem_closed
        if not mem_closed:
            return db_closed

        seen = set()
        merged = []
        for item in db_closed:
            k = self._get_logical_key(item)
            seen.add(k)
            merged.append(item)

        for item in mem_closed:
            k = self._get_logical_key(item)
            if k not in seen:
                seen.add(k)
                merged.append(item)

        def _sort_key(t: TradeJournalItem):
            dt = t.tradeDate
            if dt is None:
                return (0.0, t.id or 0)
            if getattr(dt, "tzinfo", None) is None and hasattr(dt, "replace"):
                dt = dt.replace(tzinfo=timezone.utc)
            ts = dt.timestamp() if hasattr(dt, "timestamp") else 0.0
            return (ts, t.id or 0)

        merged.sort(key=_sort_key, reverse=True)
        return merged

    def get_trade(self, trade_id: int, session: Optional[object] = None) -> Optional[TradeJournalItem]:
        try:
            if session is not None:
                record = session.get(TradeJournalRecord, trade_id)
                if record:
                    return _to_item(record)
            else:
                with get_session() as session_ctx:
                    record = session_ctx.get(TradeJournalRecord, trade_id)
                    if record:
                        return _to_item(record)
        except Exception as ex:
            logger.warning(f"Database get_trade failed: {ex}")
        return self._fallback_memory.get_trade(trade_id)

    def create_trade(self, payload: TradeJournalCreate, session: Optional[object] = None) -> TradeJournalItem:
        with self._lock:
            mem_item = self._fallback_memory.create_trade(payload)
            now = datetime.now(timezone.utc)
            values = {
                column: getattr(payload, field) for field, column in _COLUMNS.items()
            }
            if values.get("initial_stop_loss") is None and values.get("stop_loss") is not None:
                values["initial_stop_loss"] = float(values["stop_loss"])
            if payload.executionMode:
                values["notes"] = inject_mode_token(values.get("notes"), payload.executionMode)
            try:
                if session is not None:
                    record = TradeJournalRecord(created_at=now, updated_at=now, **values)
                    session.add(record)
                    session.flush()
                    session.refresh(record)
                    db_item = _to_item(record)
                    if mem_item.id != db_item.id:
                        with self._fallback_memory._lock:
                            self._fallback_memory._trades.pop(mem_item.id, None)
                    self._fallback_memory.sync_authoritative_item(db_item)
                    self._outbox_pending_ids.discard(mem_item.id)
                    self._save_outbox_to_disk()
                    return db_item
                with get_session() as session_ctx:
                    record = TradeJournalRecord(created_at=now, updated_at=now, **values)
                    session_ctx.add(record)
                    session_ctx.commit()
                    session_ctx.refresh(record)
                    db_item = _to_item(record)
                    if mem_item.id != db_item.id:
                        with self._fallback_memory._lock:
                            self._fallback_memory._trades.pop(mem_item.id, None)
                    self._fallback_memory.sync_authoritative_item(db_item)
                    self._outbox_pending_ids.discard(mem_item.id)
                    self._save_outbox_to_disk()
                    return db_item
            except Exception as ex:
                self._outbox_pending_ids.add(mem_item.id)
                self._save_outbox_to_disk()
                logger.warning(f"[DURABILITY:OUTBOX_PENDING_SYNC] Database create_trade failed, trade {mem_item.id} queued in fallback memory outbox: {ex}")
                return mem_item

    def update_trade(
        self, trade_id: int, payload: TradeJournalUpdate, session: Optional[object] = None
    ) -> Optional[TradeJournalItem]:
        with self._lock:
            self._fallback_memory.update_trade(trade_id, payload)
            try:
                if session is not None:
                    record = session.get(TradeJournalRecord, trade_id)
                    if record is not None:
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
                        db_item = _to_item(record)
                        self._fallback_memory.sync_authoritative_item(db_item)
                        return db_item
                else:
                    with get_session() as session_ctx:
                        record = session_ctx.get(TradeJournalRecord, trade_id)
                        if record is not None:
                            dump = payload.model_dump(exclude_unset=True)
                            mode_val = dump.pop("executionMode", None)
                            if mode_val is not None:
                                current_notes = dump.get("notes", getattr(record, "notes", None))
                                dump["notes"] = inject_mode_token(current_notes, mode_val)
                            for field, value in dump.items():
                                if field in _COLUMNS:
                                    setattr(record, _COLUMNS[field], value)
                            record.updated_at = datetime.now(timezone.utc)
                            session_ctx.commit()
                            session_ctx.refresh(record)
                            db_item = _to_item(record)
                            self._fallback_memory.sync_authoritative_item(db_item)
                            return db_item
            except Exception as ex:
                self._outbox_pending_ids.add(trade_id)
                self._save_outbox_to_disk()
                logger.warning(f"[DURABILITY:OUTBOX_PENDING_SYNC] Database update_trade failed, trade {trade_id} queued in fallback memory outbox: {ex}")
            return self._fallback_memory.get_trade(trade_id)

    def delete_trade(self, trade_id: int, session: Optional[object] = None) -> bool:
        with self._lock:
            self._fallback_memory.delete_trade(trade_id)
            try:
                if session is not None:
                    record = session.get(TradeJournalRecord, trade_id)
                    if record is None:
                        return False
                    session.delete(record)
                    session.flush()
                    return True
                with get_session() as session_ctx:
                    record = session_ctx.get(TradeJournalRecord, trade_id)
                    if record is None:
                        return False
                    session_ctx.delete(record)
                    session_ctx.commit()
                    return True
            except Exception as ex:
                logger.warning(f"Database delete_trade failed: {ex}")
                return False

    def clear_history(self) -> int:
        """Delete finished trades only; active (OPEN/PENDING/FILLED) trades are kept."""
        with self._lock:
            mem_count = self._fallback_memory.clear_history()
            try:
                with get_session() as session:
                    count = (
                        session.query(TradeJournalRecord)
                        .filter(func.upper(TradeJournalRecord.status).notin_(ACTIVE_TRADE_STATUSES))
                        .delete(synchronize_session=False)
                    )
                    session.commit()
                    return count
            except Exception as ex:
                logger.warning(f"Database clear_history failed: {ex}")
                return mem_count

    def purge_invalid_trades(self) -> int:
        with self._lock:
            mem_count = self._fallback_memory.purge_invalid_trades()
            try:
                now = datetime.now(timezone.utc)
                with get_session() as session:
                    invalid_recs = session.query(TradeJournalRecord).filter(
                        TradeJournalRecord.status.in_(["OPEN", "PENDING", "open", "pending"]),
                        (
                            (TradeJournalRecord.direction.notin_(["BUY", "SELL"]))
                            | (TradeJournalRecord.entry_price <= 0)
                            | (TradeJournalRecord.stop_loss <= 0)
                            | (TradeJournalRecord.take_profit <= 0)
                        ),
                    ).all()
                    for rec in invalid_recs:
                        rec.status = "INVALIDATED"
                        rec.result = "INVALIDATED"
                        if rec.close_date is None:
                            rec.close_date = now
                        rec.updated_at = now
                    session.commit()
                    return max(len(invalid_recs), mem_count)
            except Exception as ex:
                logger.warning(f"Database purge_invalid_trades failed: {ex}")
                return mem_count

    def cleanup_stale_open_trades(self, max_age_hours: int = 6) -> int:
        with self._lock:
            now = datetime.now(timezone.utc)
            from datetime import timedelta
            cutoff = now - timedelta(hours=max_age_hours)
            mem_count = self._fallback_memory.cleanup_stale_open_trades(max_age_hours)
            try:
                with get_session() as session:
                    stale_records = session.query(TradeJournalRecord).filter(
                        TradeJournalRecord.status.in_(["OPEN", "PENDING", "open", "pending"]),
                        TradeJournalRecord.trade_date < cutoff
                    ).all()
                    count = len(stale_records)
                    for rec in stale_records:
                        is_rec_filled = (rec.status or "").upper() == "OPEN" and (rec.fill_price is not None and float(rec.fill_price or 0.0) > 0.0) and (rec.result or "").upper() != "PENDING"
                        r_date = rec.trade_date if rec.trade_date.tzinfo else rec.trade_date.replace(tzinfo=timezone.utc)
                        if is_rec_filled and max_age_hours > 0 and (now - r_date).total_seconds() <= 48 * 3600:
                            continue
                        rec.status = "EXPIRED"
                        rec.result = "EXPIRED"
                        rec.close_date = rec.trade_date + timedelta(minutes=45)
                        rec.reason_for_exit = f"Signal expired: entry price was never triggered during active {round(max_age_hours, 1)}h window."
                        rec.lesson_learned = "Patience preserved capital: untriggered order expired cleanly without chasing market."
                        rec.updated_at = now
                    session.commit()
                    return max(count, mem_count)
            except Exception as ex:
                logger.warning(f"Database cleanup_stale_open_trades failed: {ex}")
                return mem_count

    def reconcile_outbox(self, session: Optional[object] = None) -> int:
        """Reconciles trades present in fallback memory that are missing or divergent in the primary database."""
        with self._lock:
            reconciled = 0
            try:
                all_mem_trades = self._fallback_memory.list_trades()
                if not all_mem_trades:
                    return 0

                def _sync_with_session(s):
                    nonlocal reconciled
                    db_records = s.scalars(select(TradeJournalRecord)).all()
                    db_by_key = {self._get_logical_key(r): r for r in db_records}

                    for item in all_mem_trades:
                        k = self._get_logical_key(item)
                        if k not in db_by_key:
                            now = datetime.now(timezone.utc)
                            values = {
                                column: getattr(item, field, None)
                                for field, column in _COLUMNS.items()
                                if hasattr(item, field)
                            }
                            if values.get("initial_stop_loss") is None and values.get("stop_loss") is not None:
                                values["initial_stop_loss"] = float(values["stop_loss"])
                            if item.executionMode:
                                values["notes"] = inject_mode_token(values.get("notes"), item.executionMode)
                            rec = TradeJournalRecord(created_at=now, updated_at=now, **values)
                            s.add(rec)
                            db_by_key[k] = rec
                            self._outbox_pending_ids.discard(item.id)
                            reconciled += 1
                        else:
                            rec = db_by_key[k]
                            mem_status = (item.status or "").upper()
                            rec_status = (rec.status or "").upper()
                            has_divergence = mem_status in ("CLOSED", "EXPIRED", "FILLED") and rec_status in ("OPEN", "PENDING")
                            is_pending = item.id in self._outbox_pending_ids

                            # Rule 9: Older fallback record cannot overwrite newer or terminal database state
                            db_is_newer_or_terminal = (
                                rec_status in ("CLOSED", "EXPIRED") and mem_status in ("OPEN", "PENDING")
                            )
                            if not db_is_newer_or_terminal and (getattr(rec, "updated_at", None) and getattr(item, "updatedAt", None)):
                                try:
                                    db_up = rec.updated_at if rec.updated_at.tzinfo else rec.updated_at.replace(tzinfo=timezone.utc)
                                    mem_up = item.updatedAt if item.updatedAt.tzinfo else item.updatedAt.replace(tzinfo=timezone.utc)
                                    if db_up > mem_up and rec_status != mem_status:
                                        db_is_newer_or_terminal = True
                                except Exception:
                                    pass

                            if db_is_newer_or_terminal:
                                # Authoritative DB record wins; purge stale outbox sync
                                self._outbox_pending_ids.discard(item.id)
                            elif has_divergence or is_pending:
                                for field, col in _COLUMNS.items():
                                    if hasattr(item, field):
                                        val = getattr(item, field)
                                        if val is not None:
                                            setattr(rec, col, val)
                                if item.executionMode:
                                    rec.notes = inject_mode_token(getattr(rec, "notes", None), item.executionMode)
                                rec.updated_at = datetime.now(timezone.utc)
                                self._outbox_pending_ids.discard(item.id)
                                reconciled += 1

                    if reconciled > 0:
                        s.flush()

                if session is not None:
                    _sync_with_session(session)
                else:
                    with get_session() as session_ctx:
                        _sync_with_session(session_ctx)
                        session_ctx.commit()
                if reconciled > 0:
                    self._save_outbox_to_disk()
            except Exception as ex:
                logger.warning(f"reconcile_outbox encountered error: {ex}")
            return reconciled

    def get_storage_health(self, session: Optional[object] = None) -> dict:
        db_ok = False
        db_count = 0
        mem_trades = self._fallback_memory.list_trades()
        try:
            if session is not None:
                session.execute(text("SELECT 1"))
                db_records = session.scalars(select(TradeJournalRecord)).all()
                db_count = len(db_records)
                db_ok = True
                db_by_key = {self._get_logical_key(r): r for r in db_records}
                unsynced = []
                for item in mem_trades:
                    k = self._get_logical_key(item)
                    if k not in db_by_key:
                        unsynced.append(item.id)
                    else:
                        rec = db_by_key[k]
                        mem_status = (item.status or "").upper()
                        rec_status = (rec.status or "").upper()
                        if mem_status in ("CLOSED", "EXPIRED", "FILLED") and rec_status in ("OPEN", "PENDING"):
                            unsynced.append(item.id)
                self._outbox_pending_ids.update(unsynced)
            else:
                with get_session() as session_ctx:
                    session_ctx.execute(text("SELECT 1"))
                    db_records = session_ctx.scalars(select(TradeJournalRecord)).all()
                    db_count = len(db_records)
                    db_ok = True
                    db_by_key = {self._get_logical_key(r): r for r in db_records}
                    unsynced = []
                    for item in mem_trades:
                        k = self._get_logical_key(item)
                        if k not in db_by_key:
                            unsynced.append(item.id)
                        else:
                            rec = db_by_key[k]
                            mem_status = (item.status or "").upper()
                            rec_status = (rec.status or "").upper()
                            if mem_status in ("CLOSED", "EXPIRED", "FILLED") and rec_status in ("OPEN", "PENDING"):
                                unsynced.append(item.id)
                    self._outbox_pending_ids.update(unsynced)
        except Exception as ex:
            db_ok = False
            logger.debug(f"get_storage_health DB check failed: {ex}")

        outbox_pending = len(self._outbox_pending_ids)
        if db_ok:
            durability_mode = "POSTGRES_HEALTHY" if outbox_pending == 0 else "POSTGRES_UNSYNCED_OUTBOX"
        else:
            durability_mode = "DISK_BACKED_MEMORY_DEGRADED"

        return {
            "database_connected": db_ok,
            "database_records": db_count,
            "fallback_records": len(mem_trades),
            "outbox_pending_count": outbox_pending,
            "durability_mode": durability_mode,
        }


Storage = Union[InMemoryTradeJournalStorage, DatabaseTradeJournalStorage]


class TradeJournalRepository:
    """Singleton facade over the configured trade journal storage backend."""

    _instance: Optional["TradeJournalRepository"] = None

    def __new__(cls, *args, **kwargs) -> "TradeJournalRepository":
        if cls._instance is None:
            cls._instance = super(TradeJournalRepository, cls).__new__(cls)
            cls._instance._init_storage()
        return cls._instance

    def _init_storage(self) -> None:
        self._storage: Storage = (
            DatabaseTradeJournalStorage(persistence_file=PERSISTENCE_FILE)
            if database_enabled()
            else InMemoryTradeJournalStorage(persistence_file=PERSISTENCE_FILE)
        )

    def __init__(self, storage: Optional[Union[InMemoryTradeJournalStorage, DatabaseTradeJournalStorage]] = None) -> None:
        if getattr(self, "_initialized", False) and storage is None:
            return
        self._initialized = True
        self._cached_trades: Optional[List[TradeJournalItem]] = None
        self._cached_trades_at: float = 0.0
        self._cache_lock = threading.Lock()
        if storage is not None:
            self._storage = storage
        else:
            self._init_storage()

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

    def reconcile_outbox(self, session: Optional[object] = None) -> int:
        if isinstance(self._storage, DatabaseTradeJournalStorage):
            count = self._storage.reconcile_outbox(session=session)
            if count > 0:
                self._invalidate_cache()
            return count
        return 0

    def get_storage_health(self, session: Optional[object] = None) -> dict:
        if isinstance(self._storage, DatabaseTradeJournalStorage):
            return self._storage.get_storage_health(session=session)
        fallback_count = len(self._storage.list_trades(session=session))
        return {
            "database_connected": False,
            "database_records": 0,
            "fallback_records": fallback_count,
            "outbox_pending_count": 0,
            "durability_mode": "IN_MEMORY_STORAGE",
        }


trade_journal_repository = TradeJournalRepository()
