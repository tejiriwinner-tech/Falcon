"""
Falcon Decision Intelligence Models
Immutable historical decision storage models.
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from app.core.config.database import Base


class DecisionRecord(Base):
    """
    Immutable historical persistence for every decision produced by the Decision Engine.
    Stores raw inputs (context) and outputs (result) for future replay and explainability.
    """
    __tablename__ = "decision_records"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True, nullable=False)
    mission_id = Column(String(50), nullable=False, index=True)
    engine_version = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True, nullable=False)
    processing_time_ms = Column(Integer, nullable=False)
    
    instrument = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    decision = Column(String(10), nullable=False, index=True)  # BUY, SELL, WAIT, etc.
    confidence = Column(Float, nullable=False)
    
    # Trade management fields
    entry_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    risk_level = Column(String(20), nullable=True, index=True)
    strategy_used = Column(String(50), nullable=True, index=True)
    
    # Store the entire immutable context and result as JSON for complete replay
    context_snapshot = Column(JSON, nullable=False)
    result_snapshot = Column(JSON, nullable=False)
    
    # Composite index for querying decisions by instrument, timeframe, and type over time
    __table_args__ = (
        Index('idx_decision_instrument_timeframe', 'instrument', 'timeframe', 'decision'),
        Index('idx_decision_timestamp', 'timestamp'),
        Index('idx_decision_mission', 'mission_id'),
        Index('idx_decision_strategy', 'strategy_used'),
    )
    
    def __repr__(self):
        return f"<DecisionRecord {self.decision_id} {self.instrument} {self.decision} conf={self.confidence}>"
