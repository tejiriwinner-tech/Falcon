"""
Falcon Decision Repository
Enterprise-grade persistence layer for Decision Intelligence Engine.

Follows Repository Pattern strictly - responsible only for persistence,
no business logic. Integrates with existing SQLAlchemy infrastructure.
"""
import logging
import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func

from app.models.decision_model import DecisionRecord
from app.schemas.generated_decision import GeneratedDecision
from app.schemas.decision_context import DecisionContext

logger = logging.getLogger(__name__)


def _serialize_pydantic(obj) -> Any:
    """
    Serialize Pydantic models to JSON-safe Python objects.
    
    Handles datetime objects, enums, and nested Pydantic models.
    """
    if obj is None:
        return None
    elif isinstance(obj, str):
        return obj
    elif isinstance(obj, (int, float, bool)):
        return obj
    elif hasattr(obj, 'model_dump'):
        # Pydantic v2
        return obj.model_dump(mode='json')
    elif hasattr(obj, 'dict'):
        # Pydantic v1
        return obj.dict()
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, (list, tuple)):
        return [_serialize_pydantic(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: _serialize_pydantic(value) for key, value in obj.items()}
    elif hasattr(obj, 'value'):
        # Enum-like objects
        return obj.value
    else:
        # For unknown types, convert to string representation
        return str(obj)


class DecisionRepository:
    """
    Repository for decision record persistence operations.
    
    Responsibilities:
      - Persist GeneratedDecision with complete context
      - Retrieve decisions by various criteria
      - Provide statistics and analysis data
      - Handle database errors gracefully
    
    Design Rules:
      - No business logic
      - All errors logged and never propagated
      - Follows existing MarketRepository pattern
      - Uses existing SQLAlchemy infrastructure
    """
    
    def __init__(self, db: Session):
        """
        Initialize the decision repository.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
    
    def save_decision(
        self,
        mission_id: str,
        decision: GeneratedDecision,
        context: DecisionContext,
        processing_time_ms: int,
        instrument: str,
        timeframe: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        risk_level: Optional[str] = None,
        strategy_used: Optional[str] = None
    ) -> Optional[str]:
        """
        Persist a decision with complete context for deterministic replay.
        
        Args:
            mission_id: Mission identifier
            decision: GeneratedDecision from DecisionGenerator
            context: DecisionContext used for the decision
            processing_time_ms: Processing time in milliseconds
            instrument: Trading instrument
            timeframe: Trading timeframe
            entry_price: Optional entry price
            stop_loss: Optional stop loss
            take_profit: Optional take profit
            risk_level: Optional risk level
            strategy_used: Optional strategy name
            
        Returns:
            decision_id if successful, None if failed
        """
        try:
            # Serialize context and result to JSON-safe Python objects
            context_dict = _serialize_pydantic(context)
            result_dict = _serialize_pydantic(decision)
            
            record = DecisionRecord(
                mission_id=mission_id,
                engine_version="1.0.0",  # DecisionGenerator version
                processing_time_ms=processing_time_ms,
                instrument=instrument,
                timeframe=timeframe,
                decision=decision.recommendation.value,
                confidence=decision.confidence.overall,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_level=risk_level,
                strategy_used=strategy_used,
                context_snapshot=context_dict,
                result_snapshot=result_dict
            )
            
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            
            logger.info(
                f"Decision persisted: {record.decision_id} | "
                f"Mission: {mission_id} | "
                f"Instrument: {instrument} | "
                f"Decision: {decision.recommendation.value} | "
                f"Confidence: {decision.confidence.overall:.1f}"
            )
            
            return record.decision_id
            
        except Exception as e:
            logger.error(f"Failed to persist decision: {str(e)}", exc_info=True)
            self.db.rollback()
            return None
    
    def get_latest(self, limit: int = 10) -> List[DecisionRecord]:
        """
        Get the most recent decisions.
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List of DecisionRecord ordered by timestamp (most recent first)
        """
        try:
            return self.db.query(DecisionRecord)\
                .order_by(desc(DecisionRecord.timestamp))\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"Failed to get latest decisions: {str(e)}", exc_info=True)
            return []
    
    def get_by_id(self, decision_id: str) -> Optional[DecisionRecord]:
        """
        Get a decision by its unique ID.
        
        Args:
            decision_id: Unique decision identifier
            
        Returns:
            DecisionRecord if found, None otherwise
        """
        try:
            return self.db.query(DecisionRecord)\
                .filter(DecisionRecord.decision_id == decision_id)\
                .first()
        except Exception as e:
            logger.error(f"Failed to get decision by ID {decision_id}: {str(e)}", exc_info=True)
            return None
    
    def get_recent(
        self,
        hours: int = 24,
        limit: int = 100
    ) -> List[DecisionRecord]:
        """
        Get decisions from the recent time period.
        
        Args:
            hours: Number of hours to look back
            limit: Maximum number of records to return
            
        Returns:
            List of DecisionRecord from the specified time period
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            return self.db.query(DecisionRecord)\
                .filter(DecisionRecord.timestamp >= cutoff_time)\
                .order_by(desc(DecisionRecord.timestamp))\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"Failed to get recent decisions: {str(e)}", exc_info=True)
            return []
    
    def get_by_instrument(
        self,
        instrument: str,
        limit: int = 50
    ) -> List[DecisionRecord]:
        """
        Get decisions for a specific instrument.
        
        Args:
            instrument: Trading instrument symbol
            limit: Maximum number of records to return
            
        Returns:
            List of DecisionRecord for the instrument
        """
        try:
            return self.db.query(DecisionRecord)\
                .filter(DecisionRecord.instrument == instrument)\
                .order_by(desc(DecisionRecord.timestamp))\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"Failed to get decisions for instrument {instrument}: {str(e)}", exc_info=True)
            return []
    
    def get_by_strategy(
        self,
        strategy_name: str,
        limit: int = 50
    ) -> List[DecisionRecord]:
        """
        Get decisions for a specific strategy.
        
        Args:
            strategy_name: Strategy name
            limit: Maximum number of records to return
            
        Returns:
            List of DecisionRecord for the strategy
        """
        try:
            return self.db.query(DecisionRecord)\
                .filter(DecisionRecord.strategy_used == strategy_name)\
                .order_by(desc(DecisionRecord.timestamp))\
                .limit(limit)\
                .all()
        except Exception as e:
            logger.error(f"Failed to get decisions for strategy {strategy_name}: {str(e)}", exc_info=True)
            return []
    
    def get_by_date_range(
        self,
        start_time: datetime,
        end_time: datetime,
        limit: Optional[int] = None
    ) -> List[DecisionRecord]:
        """
        Get decisions within a specific date range.
        
        Args:
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of records to return
            
        Returns:
            List of DecisionRecord within the date range
        """
        try:
            query = self.db.query(DecisionRecord)\
                .filter(
                    and_(
                        DecisionRecord.timestamp >= start_time,
                        DecisionRecord.timestamp <= end_time
                    )
                )\
                .order_by(desc(DecisionRecord.timestamp))
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
        except Exception as e:
            logger.error(f"Failed to get decisions by date range: {str(e)}", exc_info=True)
            return []
    
    def count(self) -> int:
        """
        Get total count of decisions in repository.
        
        Returns:
            Total number of decision records
        """
        try:
            return self.db.query(DecisionRecord).count()
        except Exception as e:
            logger.error(f"Failed to count decisions: {str(e)}", exc_info=True)
            return 0
    
    def statistics(self) -> Dict[str, Any]:
        """
        Get repository statistics.
        
        Returns:
            Dictionary with decision statistics
        """
        try:
            total = self.db.query(DecisionRecord).count()
            
            if total == 0:
                return {
                    'totalDecisions': 0,
                    'byDecision': {},
                    'byInstrument': {},
                    'averageConfidence': 0.0,
                    'averageProcessingTimeMs': 0.0
                }
            
            # Count by decision type
            by_decision = dict(self.db.query(
                DecisionRecord.decision,
                func.count(DecisionRecord.id)
            ).group_by(DecisionRecord.decision).all())
            
            # Count by instrument
            by_instrument = dict(self.db.query(
                DecisionRecord.instrument,
                func.count(DecisionRecord.id)
            ).group_by(DecisionRecord.instrument).all())
            
            # Average confidence
            avg_confidence = self.db.query(
                func.avg(DecisionRecord.confidence)
            ).scalar() or 0.0
            
            # Average processing time
            avg_processing_time = self.db.query(
                func.avg(DecisionRecord.processing_time_ms)
            ).scalar() or 0.0
            
            return {
                'totalDecisions': total,
                'byDecision': by_decision,
                'byInstrument': by_instrument,
                'averageConfidence': round(avg_confidence, 2),
                'averageProcessingTimeMs': round(avg_processing_time, 2)
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}", exc_info=True)
            return {
                'totalDecisions': 0,
                'byDecision': {},
                'byInstrument': {},
                'averageConfidence': 0.0,
                'averageProcessingTimeMs': 0.0
            }
    
    def delete_old(self, older_than: datetime) -> int:
        """
        Delete decisions older than a specified timestamp.
        
        Args:
            older_than: Delete decisions with timestamp older than this
            
        Returns:
            Number of decisions deleted
        """
        try:
            deleted = self.db.query(DecisionRecord)\
                .filter(DecisionRecord.timestamp < older_than)\
                .delete()
            
            self.db.commit()
            logger.info(f"Deleted {deleted} old decisions older than {older_than}")
            return deleted
        except Exception as e:
            logger.error(f"Failed to delete old decisions: {str(e)}", exc_info=True)
            self.db.rollback()
            return 0
    
    def exists(self, decision_id: str) -> bool:
        """
        Check if a decision exists by ID.
        
        Args:
            decision_id: Unique decision identifier
            
        Returns:
            True if decision exists, False otherwise
        """
        try:
            return self.db.query(DecisionRecord)\
                .filter(DecisionRecord.decision_id == decision_id)\
                .first() is not None
        except Exception as e:
            logger.error(f"Failed to check decision existence: {str(e)}", exc_info=True)
            return False
    
    def update_metadata(
        self,
        decision_id: str,
        entry_price: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None
    ) -> bool:
        """
        Update trade management metadata for a decision.
        
        Args:
            decision_id: Unique decision identifier
            entry_price: Optional entry price
            stop_loss: Optional stop loss
            take_profit: Optional take profit
            
        Returns:
            True if successful, False otherwise
        """
        try:
            record = self.db.query(DecisionRecord)\
                .filter(DecisionRecord.decision_id == decision_id)\
                .first()
            
            if not record:
                logger.warning(f"Decision {decision_id} not found for metadata update")
                return False
            
            if entry_price is not None:
                record.entry_price = entry_price
            if stop_loss is not None:
                record.stop_loss = stop_loss
            if take_profit is not None:
                record.take_profit = take_profit
            
            self.db.commit()
            logger.info(f"Updated metadata for decision {decision_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to update metadata for decision {decision_id}: {str(e)}", exc_info=True)
            self.db.rollback()
            return False