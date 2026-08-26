"""
Signal Repository
Persistent storage for generated signals using SQLite.
"""
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional
from app.schemas.signal_models import TradeSetup, SignalStatus


class SignalRepository:
    """
    Signal repository for persistent storage.
    
    Stores every generated signal in SQLite for historical tracking.
    """
    
    def __init__(self, db_path: str = "signals.db"):
        """Initialize the signal repository."""
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                signalId TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                signalType TEXT NOT NULL,
                entryPrice REAL NOT NULL,
                stopLoss REAL NOT NULL,
                takeProfit1 REAL,
                takeProfit2 REAL,
                takeProfit3 REAL,
                riskRewardRatio REAL NOT NULL,
                confidence REAL NOT NULL,
                quality TEXT NOT NULL,
                expectedHoldTime TEXT NOT NULL,
                status TEXT NOT NULL,
                decision TEXT NOT NULL,
                reasoning TEXT,
                warnings TEXT,
                tradeManagement TEXT,
                generatedAt TEXT NOT NULL,
                expiresAt TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_signal(self, signal: TradeSetup) -> bool:
        """Save a signal to the repository."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.signalId,
                signal.symbol,
                signal.timeframe,
                signal.signalType.value,
                signal.entryPrice,
                signal.stopLoss,
                signal.takeProfit1,
                signal.takeProfit2,
                signal.takeProfit3,
                signal.riskRewardRatio,
                signal.confidence,
                signal.quality,
                signal.expectedHoldTime,
                signal.status.value,
                signal.decision,
                ",".join(signal.reasoning),
                ",".join(signal.warnings),
                str(signal.tradeManagement.dict()) if signal.tradeManagement else None,
                signal.generatedAt.isoformat(),
                signal.expiresAt.isoformat() if signal.expiresAt else None
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Error saving signal: {e}")
            return False
    
    def get_signal(self, signal_id: str) -> Optional[TradeSetup]:
        """Get a signal by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM signals WHERE signalId = ?", (signal_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                return self._row_to_signal(row)
            return None
        except Exception as e:
            logger.error(f"Error getting signal: {e}")
            return None
    
    def list_signals(
        self,
        symbol: Optional[str] = None,
        status: Optional[SignalStatus] = None,
        limit: int = 100
    ) -> List[TradeSetup]:
        """List signals with optional filters."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM signals"
            params = []
            
            if symbol or status:
                conditions = []
                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)
                if status:
                    conditions.append("status = ?")
                    params.append(status.value)
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY generatedAt DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            conn.close()
            
            return [self._row_to_signal(row) for row in rows]
        except Exception as e:
            logger.error(f"Error listing signals: {e}")
            return []
    
    def active_signals(self, limit: int = 100) -> List[TradeSetup]:
        """Get all active signals."""
        return self.list_signals(status=SignalStatus.ACTIVE, limit=limit)
    
    def expired_signals(self, limit: int = 100) -> List[TradeSetup]:
        """Get all expired signals."""
        return self.list_signals(status=SignalStatus.EXPIRED, limit=limit)
    
    def statistics(self) -> dict:
        """Get repository statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM signals")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM signals WHERE signalType = 'BUY'")
            buy_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM signals WHERE signalType = 'SELL'")
            sell_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM signals WHERE signalType = 'WAIT'")
            wait_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM signals WHERE status = 'EXPIRED'")
            expired_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT AVG(confidence) FROM signals")
            avg_conf = cursor.fetchone()[0] or 0.0
            
            cursor.execute("SELECT AVG(riskRewardRatio) FROM signals")
            avg_rr = cursor.fetchone()[0] or 0.0
            
            conn.close()
            
            return {
                'totalSignals': total,
                'buySignals': buy_count,
                'sellSignals': sell_count,
                'waitSignals': wait_count,
                'expiredSignals': expired_count,
                'averageConfidence': round(avg_conf, 2),
                'averageRR': round(avg_rr, 2)
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def _row_to_signal(self, row) -> TradeSetup:
        """Convert database row to TradeSetup object."""
        from app.schemas.signal_models import SignalType, SignalStatus, TradeManagement
        import json
        
        return TradeSetup(
            signalId=row[0],
            symbol=row[1],
            timeframe=row[2],
            signalType=SignalType(row[3]),
            entryPrice=row[4],
            stopLoss=row[5],
            takeProfit1=row[6],
            takeProfit2=row[7],
            takeProfit3=row[8],
            riskRewardRatio=row[9],
            confidence=row[10],
            quality=row[11],
            expectedHoldTime=row[12],
            status=SignalStatus(row[13]),
            decision=row[14],
            reasoning=row[15].split(",") if row[15] else [],
            warnings=row[16].split(",") if row[16] else [],
            tradeManagement=TradeManagement(**json.loads(row[17])) if row[17] else None,
            generatedAt=datetime.fromisoformat(row[18]),
            expiresAt=datetime.fromisoformat(row[19]) if row[19] else None
        )
