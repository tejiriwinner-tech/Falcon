"""Persistence and deduplication memory for canonical signal signatures.

Backs Falcon's signal lifecycle deduplication:
- PostgreSQL / Supabase when ``DATABASE_URL`` is configured.
- Process-local in-memory storage fallback for local testing without DB.
"""

import copy
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import select

from app.core.database.models import Base, SignalSignatureRecord
from app.core.database.session import database_enabled, get_engine, get_session

logger = logging.getLogger("falcon.signal_signature_repository")


def format_signature_key(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
) -> str:
    """Computes standard canonical string key for database persistence."""
    sym = (symbol or "").replace("/", "").upper()
    dir_str = (direction or "").upper()
    ep = round(float(entry_price or 0.0), 4)
    sl = round(float(stop_loss or 0.0), 4)
    tp = round(float(take_profit or 0.0), 4)
    return f"{sym}:{dir_str}:{ep:.4f}:{sl:.4f}:{tp:.4f}"


def parse_signature_key(key: str) -> Optional[Tuple[str, str, float, float, float]]:
    """Parses standard canonical string key back into constituent fields."""
    try:
        parts = key.split(":")
        if len(parts) == 5:
            return (
                parts[0],
                parts[1],
                round(float(parts[2]), 4),
                round(float(parts[3]), 4),
                round(float(parts[4]), 4),
            )
    except Exception:
        pass
    return None


class InMemorySignalSignatureStorage:
    """Process-local storage for testing and offline runs."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.clear()

    def clear(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self._signatures: Dict[str, dict] = {}

    def record_signature(
        self,
        signature: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        status: str = "ACTIVE",
    ) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            existing = self._signatures.get(signature)
            if existing:
                ex_st = (existing.get("status") or "").upper()
                if ex_st == "ACTIVE" and status.upper() == "HOLD":
                    return
                if ex_st in {"WON", "LOST", "BREAKEVEN", "EXPIRED"} and status.upper() in {"HOLD", "ACTIVE"}:
                    return
            created_at = existing["created_at"] if existing else now
            self._signatures[signature] = {
                "signature": signature,
                "symbol": symbol.replace("/", "").upper(),
                "direction": direction.upper(),
                "entry_price": round(float(entry_price), 4),
                "stop_loss": round(float(stop_loss), 4),
                "take_profit": round(float(take_profit), 4),
                "status": status.upper(),
                "created_at": created_at,
                "updated_at": now,
            }

    def has_signature(self, signature: str) -> bool:
        with self._lock:
            return signature in self._signatures

    def get_signature(self, signature: str) -> Optional[dict]:
        with self._lock:
            val = self._signatures.get(signature)
            return copy.deepcopy(val) if val else None

    def get_all_signatures(self) -> Set[str]:
        with self._lock:
            return set(self._signatures.keys())

    def get_resolved_signatures(self) -> Set[str]:
        terminal_statuses = {"WON", "LOST", "BREAKEVEN", "EXPIRED", "CLOSED", "INVALIDATED"}
        with self._lock:
            return {
                k for k, v in self._signatures.items()
                if (v.get("status") or "").upper() in terminal_statuses
            }

    def update_status(self, signature: str, status: str) -> bool:
        with self._lock:
            if signature in self._signatures:
                self._signatures[signature]["status"] = status.upper()
                self._signatures[signature]["updated_at"] = datetime.now(timezone.utc)
                return True
            return False


class SignalSignatureRepository:
    """
    Unified signal signature repository supporting PostgreSQL and in-memory storage.
    Ensures multi-machine consistency and survival across Fly.io restarts/deploys.
    """

    def __init__(self) -> None:
        self._in_memory = InMemorySignalSignatureStorage()
        self._tables_initialized = False
        self._cached_resolved: Optional[Set[Tuple[str, str, float, float, float]]] = None
        self._cached_resolved_at: float = 0.0

    def _ensure_schema(self) -> None:
        if not self._tables_initialized and database_enabled():
            try:
                engine = get_engine()
                Base.metadata.create_all(
                    bind=engine,
                    tables=[SignalSignatureRecord.__table__],
                    checkfirst=True,
                )
                self._tables_initialized = True
            except Exception as e:
                logger.warning(f"Could not auto-create signal_signatures table: {e}")

    def record_signature(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        status: str = "ACTIVE",
    ) -> str:
        sig_key = format_signature_key(symbol, direction, entry_price, stop_loss, take_profit)
        existing = self._in_memory.get_signature(sig_key)
        # Never allow a HOLD status to downgrade or overwrite an already ACTIVE or terminal signal
        if existing:
            existing_status = (existing.get("status") or "").upper()
            if existing_status == "ACTIVE" and status.upper() == "HOLD":
                return sig_key
            if existing_status in {"WON", "LOST", "BREAKEVEN", "EXPIRED"} and status.upper() in {"HOLD", "ACTIVE"}:
                return sig_key
            if existing_status == status.upper():
                return sig_key

        self._in_memory.record_signature(
            sig_key, symbol, direction, entry_price, stop_loss, take_profit, status
        )
        self._cached_resolved = None

        if database_enabled():
            def _persist(sync: bool = False):
                try:
                    self._ensure_schema()
                    session = get_session()
                    try:
                        now = datetime.now(timezone.utc)
                        record = session.get(SignalSignatureRecord, sig_key)
                        if record is None:
                            record = SignalSignatureRecord(
                                signature=sig_key,
                                symbol=symbol.replace("/", "").upper(),
                                direction=direction.upper(),
                                entry_price=round(float(entry_price), 4),
                                stop_loss=round(float(stop_loss), 4),
                                take_profit=round(float(take_profit), 4),
                                status=status.upper(),
                                created_at=now,
                                updated_at=now,
                            )
                            session.add(record)
                        else:
                            # Protect DB row from downgrade too
                            cur_db_st = (record.status or "").upper()
                            if cur_db_st == "ACTIVE" and status.upper() == "HOLD":
                                return
                            if cur_db_st in {"WON", "LOST", "BREAKEVEN", "EXPIRED"} and status.upper() in {"HOLD", "ACTIVE"}:
                                return
                            record.status = status.upper()
                            record.updated_at = now
                        session.commit()
                    except Exception as ex:
                        session.rollback()
                        logger.warning(f"Error persisting signal signature to DB: {ex}")
                    finally:
                        session.close()
                except Exception as ex:
                    logger.warning(f"Database session error for signal signature: {ex}")

            if status.upper() in {"ACTIVE", "WON", "LOST", "BREAKEVEN", "EXPIRED"}:
                _persist(sync=True)
            else:
                threading.Thread(target=_persist, daemon=True).start()

        return sig_key

    def get_status(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> Optional[str]:
        sig_key = format_signature_key(symbol, direction, entry_price, stop_loss, take_profit)
        sig = self._in_memory.get_signature(sig_key)
        if sig and sig.get("status"):
            return (sig.get("status") or "").upper()

        if database_enabled():
            self._ensure_schema()
            try:
                session = get_session()
                try:
                    record = session.get(SignalSignatureRecord, sig_key)
                    if record is not None and record.status:
                        return record.status.upper()
                finally:
                    session.close()
            except Exception as ex:
                logger.debug(f"Error checking signature status in DB: {ex}")
        return None

    def is_active(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> bool:
        status = self.get_status(symbol, direction, entry_price, stop_loss, take_profit)
        if status == "ACTIVE":
            return True

        # Fuzzy check in-memory signatures in case float rounding slightly differed
        sym_clean = (symbol or "").replace("/", "").upper()
        dir_clean = (direction or "").upper()
        tol = 0.50 if ("XAU" in sym_clean or entry_price > 100) else 0.00025
        with self._in_memory._lock:
            for v in self._in_memory._signatures.values():
                if (
                    v.get("symbol") == sym_clean
                    and v.get("direction") == dir_clean
                    and (v.get("status") or "").upper() == "ACTIVE"
                    and abs(float(v.get("entry_price", 0.0)) - float(entry_price)) <= tol
                ):
                    return True
        return False

    def has_signature(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
    ) -> bool:
        return self.get_status(symbol, direction, entry_price, stop_loss, take_profit) is not None

    def get_all_signatures(self) -> Set[str]:
        signatures = set(self._in_memory.get_all_signatures())
        if database_enabled():
            self._ensure_schema()
            try:
                session = get_session()
                try:
                    stmt = select(SignalSignatureRecord.signature)
                    results = session.execute(stmt).scalars().all()
                    for sig in results:
                        signatures.add(sig)
                finally:
                    session.close()
            except Exception as ex:
                logger.debug(f"Error listing signatures from DB: {ex}")
        return signatures

    def get_all_signature_tuples(self) -> Set[Tuple[str, str, float, float, float]]:
        all_keys = self.get_all_signatures()
        tuples: Set[Tuple[str, str, float, float, float]] = set()
        for k in all_keys:
            parsed = parse_signature_key(k)
            if parsed:
                tuples.add(parsed)
        return tuples

    def get_resolved_signatures(self) -> Set[Tuple[str, str, float, float, float]]:
        import time as _t
        now_mono = _t.monotonic()
        if self._cached_resolved is not None and (now_mono - self._cached_resolved_at) < 30.0:
            return set(self._cached_resolved)

        resolved_keys = set(self._in_memory.get_resolved_signatures())
        if database_enabled():
            self._ensure_schema()
            try:
                session = get_session()
                try:
                    terminal_statuses = ["WON", "LOST", "BREAKEVEN", "EXPIRED", "CLOSED", "INVALIDATED"]
                    stmt = select(SignalSignatureRecord.signature).where(
                        SignalSignatureRecord.status.in_(terminal_statuses)
                    )
                    results = session.execute(stmt).scalars().all()
                    for sig in results:
                        resolved_keys.add(sig)
                finally:
                    session.close()
            except Exception as ex:
                logger.debug(f"Error querying resolved signatures from DB: {ex}")
        tuples: Set[Tuple[str, str, float, float, float]] = set()
        for k in resolved_keys:
            parsed = parse_signature_key(k)
            if parsed:
                tuples.add(parsed)
        self._cached_resolved = set(tuples)
        self._cached_resolved_at = _t.monotonic()
        return tuples

    def update_status(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        status: str,
    ) -> bool:
        sig_key = format_signature_key(symbol, direction, entry_price, stop_loss, take_profit)
        self._in_memory.update_status(sig_key, status)

        if database_enabled():
            self._ensure_schema()
            try:
                session = get_session()
                try:
                    record = session.get(SignalSignatureRecord, sig_key)
                    if record:
                        record.status = status.upper()
                        record.updated_at = datetime.now(timezone.utc)
                        session.commit()
                        return True
                except Exception as ex:
                    session.rollback()
                    logger.warning(f"Error updating signature status in DB: {ex}")
                finally:
                    session.close()
            except Exception as ex:
                logger.warning(f"Database session error on signature update: {ex}")
        return False

    def clear(self) -> None:
        self._in_memory.clear()
        self._cached_resolved = None
        self._cached_resolved_at = 0.0
        if database_enabled():
            self._ensure_schema()
            try:
                session = get_session()
                try:
                    session.query(SignalSignatureRecord).delete()
                    session.commit()
                except Exception as ex:
                    session.rollback()
                    logger.debug(f"Error clearing signal_signatures table: {ex}")
                finally:
                    session.close()
            except Exception as ex:
                logger.debug(f"Database session error on clear: {ex}")


signal_signature_repository = SignalSignatureRepository()
