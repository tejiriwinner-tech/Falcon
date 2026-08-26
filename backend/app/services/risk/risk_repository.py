"""
Risk Repository
Persistent storage for risk assessments using SQLite.
"""
import sqlite3
import logging
from datetime import datetime, timezone
from typing import List, Optional
from app.schemas.risk_models import RiskAssessment, RiskDecision

logger = logging.getLogger(__name__)


class RiskRepository:
    """
    Risk repository for persistent storage.
    
    Stores every risk assessment in SQLite for historical tracking.
    """
    
    def __init__(self, db_path: str = "risk_assessments.db"):
        """Initialize the risk repository."""
        self.db_path = db_path
        self._conn = None
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        # For in-memory databases, keep connection open
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(self.db_path)
            cursor = self._conn.cursor()
        else:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_assessments (
                signalId TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                decision TEXT NOT NULL,
                overallRiskScore REAL NOT NULL,
                riskPercent REAL NOT NULL,
                rr REAL NOT NULL,
                dailyExposure REAL NOT NULL,
                portfolioExposure REAL NOT NULL,
                correlationLevel TEXT NOT NULL,
                approved INTEGER NOT NULL,
                reasons TEXT,
                warnings TEXT,
                assessedAt TEXT NOT NULL
            )
        """)
        
        if self.db_path == ":memory:":
            self._conn.commit()
        else:
            conn.commit()
            conn.close()
    
    def save_assessment(self, assessment: RiskAssessment) -> bool:
        """Save a risk assessment to the repository."""
        try:
            conn = self._conn if self._conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO risk_assessments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                assessment.signalId,
                assessment.symbol,
                assessment.timeframe,
                assessment.decision.value,
                assessment.overallRiskScore,
                assessment.riskPercent,
                assessment.rr,
                assessment.dailyExposure,
                assessment.portfolioExposure,
                assessment.correlationLevel,
                1 if assessment.approved else 0,
                ",".join(assessment.reasons),
                ",".join(assessment.warnings),
                assessment.assessedAt.isoformat()
            ))
            
            conn.commit()
            if not self._conn:
                conn.close()
            return True
        except Exception as e:
            logger.error(f"Error saving risk assessment: {e}")
            return False
    
    def get_assessment(self, signal_id: str) -> Optional[RiskAssessment]:
        """Get a risk assessment by signal ID."""
        try:
            conn = self._conn if self._conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM risk_assessments WHERE signalId = ?", (signal_id,))
            row = cursor.fetchone()
            
            if not self._conn:
                conn.close()
            
            if row:
                return self._row_to_assessment(row)
            return None
        except Exception as e:
            logger.error(f"Error getting risk assessment: {e}")
            return None
    
    def list_assessments(
        self,
        symbol: Optional[str] = None,
        decision: Optional[RiskDecision] = None,
        approved: Optional[bool] = None,
        limit: int = 100
    ) -> List[RiskAssessment]:
        """List risk assessments with optional filters."""
        try:
            conn = self._conn if self._conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = "SELECT * FROM risk_assessments"
            params = []
            
            if symbol or decision or approved is not None:
                conditions = []
                if symbol:
                    conditions.append("symbol = ?")
                    params.append(symbol)
                if decision:
                    conditions.append("decision = ?")
                    params.append(decision.value)
                if approved is not None:
                    conditions.append("approved = ?")
                    params.append(1 if approved else 0)
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY assessedAt DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            if not self._conn:
                conn.close()
            
            return [self._row_to_assessment(row) for row in rows]
        except Exception as e:
            logger.error(f"Error listing risk assessments: {e}")
            return []
    
    def approved_assessments(self, limit: int = 100) -> List[RiskAssessment]:
        """Get all approved risk assessments."""
        return self.list_assessments(approved=True, limit=limit)
    
    def rejected_assessments(self, limit: int = 100) -> List[RiskAssessment]:
        """Get all rejected risk assessments."""
        return self.list_assessments(approved=False, limit=limit)
    
    def statistics(self) -> dict:
        """Get repository statistics."""
        try:
            conn = self._conn if self._conn else sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM risk_assessments")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM risk_assessments WHERE decision = 'APPROVED'")
            approved_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM risk_assessments WHERE decision = 'APPROVED_WITH_WARNING'")
            approved_with_warning_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM risk_assessments WHERE decision = 'REJECTED'")
            rejected_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT AVG(overallRiskScore) FROM risk_assessments")
            avg_risk_score = cursor.fetchone()[0] or 0.0
            
            cursor.execute("SELECT AVG(riskPercent) FROM risk_assessments")
            avg_risk_percent = cursor.fetchone()[0] or 0.0
            
            cursor.execute("SELECT AVG(rr) FROM risk_assessments")
            avg_rr = cursor.fetchone()[0] or 0.0
            
            if not self._conn:
                conn.close()
            
            return {
                'totalAssessments': total,
                'approvedCount': approved_count,
                'approvedWithWarningCount': approved_with_warning_count,
                'rejectedCount': rejected_count,
                'averageRiskScore': round(avg_risk_score, 2),
                'averageRiskPercent': round(avg_risk_percent, 2),
                'averageRR': round(avg_rr, 2)
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}
    
    def _row_to_assessment(self, row) -> RiskAssessment:
        """Convert database row to RiskAssessment object."""
        return RiskAssessment(
            signalId=row[0],
            symbol=row[1],
            timeframe=row[2],
            decision=RiskDecision(row[3]),
            overallRiskScore=row[4],
            riskPercent=row[5],
            rr=row[6],
            dailyExposure=row[7],
            portfolioExposure=row[8],
            correlationLevel=row[9],
            approved=bool(row[10]),
            reasons=row[11].split(",") if row[11] else [],
            warnings=row[12].split(",") if row[12] else [],
            assessedAt=datetime.fromisoformat(row[13])
        )
