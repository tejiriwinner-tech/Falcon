"""
Falcon Signal Repository

Persistent storage for trading signals using SQLite.
Provides methods for saving, retrieving, and managing signals.
"""
import sqlite3
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
from app.core.scheduler_config import scheduler_config
from app.schemas.signal_models import TradeSetup
from app.schemas.ai_snapshot import AISnapshot
import logging

logger = logging.getLogger(__name__)


class SignalRepository:
    """Repository for persistent signal storage using SQLite."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the signal repository.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses config default.
        """
        self.db_path = db_path or scheduler_config.SIGNAL_DB_PATH
        self._ensure_db_directory()
        self._init_db()
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists."""
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS signals (
                    signal_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit_1 REAL,
                    take_profit_2 REAL,
                    take_profit_3 REAL,
                    risk_reward_ratio REAL NOT NULL,
                    confidence REAL NOT NULL,
                    quality TEXT NOT NULL,
                    expected_hold_time TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reasoning TEXT NOT NULL,
                    warnings TEXT NOT NULL,
                    trade_management TEXT,
                    generated_at TEXT NOT NULL,
                    expires_at TEXT,
                    created_at TEXT NOT NULL,
                    ai_snapshot TEXT,
                    triggered_at TEXT,
                    tp1_hit_at TEXT,
                    tp2_hit_at TEXT,
                    tp3_hit_at TEXT,
                    sl_hit_at TEXT,
                    closed_at TEXT
                )
            """)
            
            # Add missing columns if table exists (migration)
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN ai_snapshot TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN triggered_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN tp1_hit_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN tp2_hit_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN tp3_hit_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN sl_hit_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                conn.execute("ALTER TABLE signals ADD COLUMN closed_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Create indexes for common queries
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON signals(symbol)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON signals(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol_status ON signals(symbol, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_generated_at ON signals(generated_at)")
            
            conn.commit()
    
    def _trade_setup_to_dict(self, signal: TradeSetup, ai_snapshot: Optional[AISnapshot] = None) -> Dict[str, Any]:
        """Convert a TradeSetup to a dictionary for database storage."""
        data = {
            "signal_id": signal.signalId,
            "symbol": signal.symbol,
            "timeframe": signal.timeframe,
            "signal_type": signal.signalType,
            "entry_price": signal.entryPrice,
            "stop_loss": signal.stopLoss,
            "take_profit_1": signal.takeProfit1,
            "take_profit_2": signal.takeProfit2,
            "take_profit_3": signal.takeProfit3,
            "risk_reward_ratio": signal.riskRewardRatio,
            "confidence": signal.confidence,
            "quality": signal.quality,
            "expected_hold_time": signal.expectedHoldTime,
            "status": signal.status,
            "decision": signal.decision,
            "reasoning": json.dumps(signal.reasoning),
            "warnings": json.dumps(signal.warnings),
            "trade_management": json.dumps(signal.tradeManagement.model_dump()) if signal.tradeManagement else None,
            "generated_at": signal.generatedAt.isoformat(),
            "expires_at": signal.expiresAt.isoformat() if signal.expiresAt else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "ai_snapshot": json.dumps(ai_snapshot.model_dump()) if ai_snapshot else None,
        }
        return data
    
    def _row_to_trade_setup(self, row: sqlite3.Row) -> TradeSetup:
        """Convert a database row to a TradeSetup."""
        return TradeSetup(
            signalId=row["signal_id"],
            symbol=row["symbol"],
            timeframe=row["timeframe"],
            signalType=row["signal_type"],
            entryPrice=row["entry_price"],
            stopLoss=row["stop_loss"],
            takeProfit1=row["take_profit_1"],
            takeProfit2=row["take_profit_2"],
            takeProfit3=row["take_profit_3"],
            riskRewardRatio=row["risk_reward_ratio"],
            confidence=row["confidence"],
            quality=row["quality"],
            expectedHoldTime=row["expected_hold_time"],
            status=row["status"],
            decision=row["decision"],
            reasoning=json.loads(row["reasoning"]) if row["reasoning"] else [],
            warnings=json.loads(row["warnings"]) if row["warnings"] else [],
            tradeManagement=json.loads(row["trade_management"]) if row["trade_management"] else None,
            generatedAt=datetime.fromisoformat(row["generated_at"]),
            expiresAt=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        )
    
    def save_signal(self, signal: TradeSetup, ai_snapshot: Optional[AISnapshot] = None) -> bool:
        """
        Save a signal to the repository.
        
        Args:
            signal: The signal to save
            ai_snapshot: Optional AI snapshot to store with the signal
            
        Returns:
            True if save was successful
        """
        try:
            with self._get_connection() as conn:
                data = self._trade_setup_to_dict(signal, ai_snapshot)
                conn.execute("""
                    INSERT OR REPLACE INTO signals (
                        signal_id, symbol, timeframe, signal_type, entry_price, stop_loss,
                        take_profit_1, take_profit_2, take_profit_3, risk_reward_ratio,
                        confidence, quality, expected_hold_time, status, decision,
                        reasoning, warnings, trade_management, generated_at, expires_at, created_at,
                        ai_snapshot, triggered_at, tp1_hit_at, tp2_hit_at, tp3_hit_at, sl_hit_at, closed_at
                    ) VALUES (
                        :signal_id, :symbol, :timeframe, :signal_type, :entry_price, :stop_loss,
                        :take_profit_1, :take_profit_2, :take_profit_3, :risk_reward_ratio,
                        :confidence, :quality, :expected_hold_time, :status, :decision,
                        :reasoning, :warnings, :trade_management, :generated_at, :expires_at, :created_at,
                        :ai_snapshot, NULL, NULL, NULL, NULL, NULL, NULL
                    )
                """, data)
                conn.commit()
                logger.info(f"Saved signal {signal.signalId} to repository")
                return True
        except Exception as e:
            logger.error(f"Failed to save signal {signal.signalId}: {e}")
            return False
    
    def get_live_signals(self) -> List[TradeSetup]:
        """
        Get all active signals.
        
        Returns:
            List of active signals
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM signals WHERE status = 'ACTIVE'
                    ORDER BY generated_at DESC
                """)
                return [self._row_to_trade_setup(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get live signals: {e}")
            return []
    
    def get_signal_history(
        self,
        symbol: Optional[str] = None,
        status: Optional[str] = None,
        timeframe: Optional[str] = None,
        limit: int = 100
    ) -> List[TradeSetup]:
        """
        Get signal history with optional filters.
        
        Args:
            symbol: Filter by symbol (optional)
            status: Filter by status (optional)
            timeframe: Filter by timeframe (optional)
            limit: Maximum number of signals to return
            
        Returns:
            List of signals matching the filters
        """
        try:
            query = "SELECT * FROM signals WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            if timeframe:
                query += " AND timeframe = ?"
                params.append(timeframe)
            
            query += " ORDER BY generated_at DESC LIMIT ?"
            params.append(limit)
            
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                return [self._row_to_trade_setup(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get signal history: {e}")
            return []
    
    def get_latest_signal(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None
    ) -> Optional[TradeSetup]:
        """
        Get the most recent signal.
        
        Args:
            symbol: Filter by symbol (optional)
            timeframe: Filter by timeframe (optional)
            
        Returns:
            The latest signal or None
        """
        try:
            query = "SELECT * FROM signals WHERE 1=1"
            params = []
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if timeframe:
                query += " AND timeframe = ?"
                params.append(timeframe)
            
            query += " ORDER BY generated_at DESC LIMIT 1"
            
            with self._get_connection() as conn:
                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                return self._row_to_trade_setup(row) if row else None
        except Exception as e:
            logger.error(f"Failed to get latest signal: {e}")
            return None
    
    def active_count(self) -> int:
        """
        Get the count of active signals.
        
        Returns:
            Number of active signals
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'ACTIVE'")
                return cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to get active count: {e}")
            return 0
    
    def expire_signal(self, signal_id: str) -> bool:
        """
        Mark a signal as expired.
        
        Args:
            signal_id: The signal ID to expire
            
        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE signals SET status = 'EXPIRED', expires_at = ?
                    WHERE signal_id = ?
                """, (datetime.now(timezone.utc).isoformat(), signal_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to expire signal {signal_id}: {e}")
            return False
    
    def expire_all(self) -> int:
        """
        Mark all active signals as expired.
        
        Returns:
            Number of signals expired
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    UPDATE signals SET status = 'EXPIRED', expires_at = ?
                    WHERE status = 'ACTIVE'
                """, (datetime.now(timezone.utc).isoformat(),))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to expire all signals: {e}")
            return 0
    
    def signal_exists(self, signal_id: str) -> bool:
        """
        Check if a signal exists in the repository.
        
        Args:
            signal_id: The signal ID to check
            
        Returns:
            True if the signal exists
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM signals WHERE signal_id = ?",
                    (signal_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check signal existence: {e}")
            return False
    
    def delete_old_signals(self, days: int = 7) -> int:
        """
        Delete signals older than the specified number of days.
        
        Args:
            days: Number of days to keep signals
            
        Returns:
            Number of signals deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=days)
            
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    DELETE FROM signals WHERE generated_at < ?
                """, (cutoff_date.isoformat(),))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"Failed to delete old signals: {e}")
            return 0
    
    def get_repository_stats(self) -> Dict[str, Any]:
        """
        Get repository statistics.
        
        Returns:
            Dictionary with repository statistics
        """
        try:
            with self._get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
                active = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'ACTIVE'").fetchone()[0]
                expired = conn.execute("SELECT COUNT(*) FROM signals WHERE status = 'EXPIRED'").fetchone()[0]
                
                # Per-symbol counts
                symbol_counts = {}
                for row in conn.execute("""
                    SELECT symbol, COUNT(*) as count FROM signals
                    GROUP BY symbol
                """):
                    symbol_counts[row[0]] = row[1]
                
                return {
                    "total_signals": total,
                    "active_signals": active,
                    "expired_signals": expired,
                    "symbol_counts": symbol_counts,
                }
        except Exception as e:
            logger.error(f"Failed to get repository statistics: {e}")
            return {}
    
    def update_signal_status(self, signal_id: str, new_status: str) -> bool:
        """
        Update signal status and record timestamp.
        
        Args:
            signal_id: The signal ID to update
            new_status: The new status (TRIGGERED, TP1_HIT, TP2_HIT, TP3_HIT, SL_HIT, CLOSED)
            
        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                timestamp = datetime.now(timezone.utc).isoformat()
                
                # Map status to timestamp column
                status_to_column = {
                    "TRIGGERED": "triggered_at",
                    "TP1_HIT": "tp1_hit_at",
                    "TP2_HIT": "tp2_hit_at",
                    "TP3_HIT": "tp3_hit_at",
                    "SL_HIT": "sl_hit_at",
                    "CLOSED": "closed_at",
                }
                
                column = status_to_column.get(new_status)
                if column:
                    conn.execute(f"""
                        UPDATE signals SET status = ?, {column} = ?
                        WHERE signal_id = ?
                    """, (new_status, timestamp, signal_id))
                else:
                    conn.execute("""
                        UPDATE signals SET status = ?
                        WHERE signal_id = ?
                    """, (new_status, signal_id))
                
                conn.commit()
                logger.info(f"Updated signal {signal_id} to status {new_status}")
                return True
        except Exception as e:
            logger.error(f"Failed to update signal status {signal_id}: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get repository statistics.
        
        Returns:
            Dictionary with repository statistics
        """
        try:
            with self._get_connection() as conn:
                now = datetime.now(timezone.utc)
                
                # Get total signals
                total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
                
                # Get active signals (not expired)
                active = conn.execute(
                    "SELECT COUNT(*) FROM signals WHERE expires_at IS NULL OR expires_at > ?",
                    (now.isoformat(),)
                ).fetchone()[0]
                
                # Get expired signals
                expired = conn.execute(
                    "SELECT COUNT(*) FROM signals WHERE expires_at IS NOT NULL AND expires_at <= ?",
                    (now.isoformat(),)
                ).fetchone()[0]
                
                # Get symbol counts
                symbol_rows = conn.execute(
                    "SELECT symbol, COUNT(*) as count FROM signals GROUP BY symbol"
                ).fetchall()
                symbol_counts = {row["symbol"]: row["count"] for row in symbol_rows}
                
                return {
                    "total_signals": total,
                    "active_signals": active,
                    "expired_signals": expired,
                    "symbol_counts": symbol_counts
                }
        except Exception as e:
            logger.error(f"Failed to get repository statistics: {e}")
            return {
                "total_signals": 0,
                "active_signals": 0,
                "expired_signals": 0,
                "symbol_counts": {}
            }
    
    def get_ai_snapshot(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the AI snapshot for a signal.
        
        Args:
            signal_id: The signal ID
            
        Returns:
            AI snapshot dictionary or None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT ai_snapshot FROM signals WHERE signal_id = ?",
                    (signal_id,)
                )
                row = cursor.fetchone()
                if row and row["ai_snapshot"]:
                    return json.loads(row["ai_snapshot"])
                return None
        except Exception as e:
            logger.error(f"Failed to get AI snapshot for {signal_id}: {e}")
            return None
