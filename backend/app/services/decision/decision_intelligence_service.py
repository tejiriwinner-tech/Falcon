"""
Falcon Decision Intelligence Service
Service layer for Decision Intelligence API with Decision Repository integration.

Follows the architecture pattern: Router → Service → Repository → Database
No direct database access from API layer.
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session

from app.repositories.decision_repository import DecisionRepository
from app.core.engines.decision.decision_generator import DecisionGenerator
from app.core.engines.decision.context_builder import build_context
from app.schemas.decision_enums import DecisionRecommendation
from app.schemas.generated_decision import GeneratedDecision
from app.schemas.decision_context import DecisionContext
from app.schemas.confidence_score import ConfidenceScore

logger = logging.getLogger(__name__)


class DecisionIntelligenceService:
    """
    Service layer for Decision Intelligence API.
    
    Responsibilities:
      - Coordinate between DecisionGenerator and DecisionRepository
      - Validate inputs
      - Provide business logic for API operations
      - Transform data for API responses
      
    Design Rules:
      - No direct database access (uses DecisionRepository)
      - No API-specific logic in repository
      - Clean separation of concerns
    """
    
    def __init__(self, db: Session):
        """
        Initialize the decision intelligence service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.decision_repository = DecisionRepository(db)
        self.decision_generator = DecisionGenerator()
    
    def evaluate_decision(
        self,
        candidate_id: str,
        mission_id: str,
        instrument: str,
        timeframe: str,
        direction: str = "BUY",
        confidence: float = 50.0,
        risk_reward: float = 2.0,
        spread: float = 0.0,
        session: str = "UNKNOWN",
        trend: str = "NEUTRAL",
        volatility: str = "MODERATE",
        news_impact: str = "LOW",
        market_open: bool = True,
        data_age_seconds: int = 0,
        strategy_id: str = "default",
        strategy_name: str = "Default Strategy"
    ) -> Dict[str, Any]:
        """
        Evaluate a trading decision using the Decision Intelligence Engine.
        
        Args:
            candidate_id: Candidate identifier
            mission_id: Mission identifier
            instrument: Trading instrument
            timeframe: Trading timeframe
            direction: Trade direction (BUY/SELL)
            confidence: Candidate confidence score
            risk_reward: Risk-reward ratio
            spread: Current spread
            session: Trading session
            trend: Market trend
            volatility: Volatility level
            news_impact: News impact level
            market_open: Whether market is open
            data_age_seconds: Age of market data
            strategy_id: Strategy identifier
            strategy_name: Strategy name
            
        Returns:
            Dictionary with decision result and persistence status
        """
        import time
        
        start_time = time.time()
        
        try:
            # Create minimal DecisionContext directly from API parameters
            # This bypasses the pipeline's build_context() which expects full artifacts
            # For API evaluation, we create a minimal context with the available parameters
            context = DecisionContext(
                candidateId=candidate_id,
                missionId=mission_id,
                candidate=None,  # No full candidate for API evaluation
                validation=None,
                risk=None,
                readiness=None,
                strategy=None,
                marketState=None,
                regimeReport=None,
                # Cached values from API parameters
                spread=spread,
                session=session,
                trend=trend,
                volatility=volatility,
                newsImpact=news_impact,
                marketOpen=market_open,
                dataAgeSeconds=data_age_seconds,
                candidateDirection=direction.upper(),
                candidateConfidence=confidence,
                candidateRiskReward=risk_reward,
                # Strategy info
                strategyId=strategy_id,
                strategyName=strategy_name,
                preferredSessions=[],
                minimumConfidence=70.0,
                minimumRiskReward=1.5,
                avoidConditions=[],
                marketCompatibility=[],
                builtAt=datetime.now(timezone.utc),
                contextVersion="1.0"
            )
            
            # Generate decision using Decision Intelligence Engine
            decision = self.decision_generator.generate(context)
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            # Persist decision to repository
            decision_id = self.decision_repository.save_decision(
                mission_id=mission_id,
                decision=decision,
                context=context,
                processing_time_ms=processing_time_ms,
                instrument=instrument,
                timeframe=timeframe,
                strategy_used=strategy_name
            )
            
            # Prepare response
            response = {
                'success': True,
                'data': {
                    'decision_id': decision_id,
                    'recommendation': decision.recommendation.value,
                    'confidence': decision.confidence.overall,
                    'grade': decision.confidence.grade,
                    'reasoning': decision.reasoning,
                    'warnings': decision.warnings,
                    'processing_time_ms': processing_time_ms,
                    'confidence_breakdown': {
                        'evaluator_contribution': decision.confidence.evaluatorContribution,
                        'risk_penalty': decision.confidence.riskPenalty,
                        'validation_bonus': decision.confidence.validationBonus,
                        'readiness_bonus': decision.confidence.readinessBonus
                    }
                },
                'persistence': {
                    'persisted': decision_id is not None,
                    'decision_id': decision_id
                }
            }
            
            logger.info(
                f"Decision evaluated: {decision.recommendation.value} | "
                f"Confidence: {decision.confidence.overall:.1f} | "
                f"Persisted: {decision_id is not None}"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Decision evaluation failed: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'persistence': {
                    'persisted': False,
                    'decision_id': None
                }
            }
    
    def get_latest_decisions(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get the most recent decisions from the repository.
        
        Args:
            limit: Maximum number of decisions to return
            
        Returns:
            Dictionary with latest decisions
        """
        try:
            records = self.decision_repository.get_latest(limit=limit)
            
            decisions = []
            for record in records:
                decisions.append({
                    'decision_id': record.decision_id,
                    'mission_id': record.mission_id,
                    'instrument': record.instrument,
                    'timeframe': record.timeframe,
                    'decision': record.decision,
                    'confidence': record.confidence,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                    'processing_time_ms': record.processing_time_ms,
                    'strategy_used': record.strategy_used,
                    'entry_price': record.entry_price,
                    'stop_loss': record.stop_loss,
                    'take_profit': record.take_profit,
                    'risk_level': record.risk_level
                })
            
            return {
                'success': True,
                'data': {
                    'decisions': decisions,
                    'count': len(decisions)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get latest decisions: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'data': {
                    'decisions': [],
                    'count': 0
                }
            }
    
    def get_decision_by_id(self, decision_id: str) -> Dict[str, Any]:
        """
        Get a specific decision by its ID.
        
        Args:
            decision_id: Unique decision identifier
            
        Returns:
            Dictionary with decision details
        """
        try:
            record = self.decision_repository.get_by_id(decision_id)
            
            if not record:
                return {
                    'success': False,
                    'error': f'Decision {decision_id} not found',
                    'data': None
                }
            
            return {
                'success': True,
                'data': {
                    'decision_id': record.decision_id,
                    'mission_id': record.mission_id,
                    'engine_version': record.engine_version,
                    'instrument': record.instrument,
                    'timeframe': record.timeframe,
                    'decision': record.decision,
                    'confidence': record.confidence,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                    'processing_time_ms': record.processing_time_ms,
                    'strategy_used': record.strategy_used,
                    'entry_price': record.entry_price,
                    'stop_loss': record.stop_loss,
                    'take_profit': record.take_profit,
                    'risk_level': record.risk_level,
                    'context_snapshot': record.context_snapshot,
                    'result_snapshot': record.result_snapshot
                }
            }
        except Exception as e:
            logger.error(f"Failed to get decision by ID: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_decision_history(
        self,
        instrument: Optional[str] = None,
        strategy: Optional[str] = None,
        hours: int = 24,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get decision history with optional filters.
        
        Args:
            instrument: Filter by instrument (optional)
            strategy: Filter by strategy (optional)
            hours: Time window in hours
            limit: Maximum number of records
            
        Returns:
            Dictionary with filtered decision history
        """
        try:
            if instrument:
                records = self.decision_repository.get_by_instrument(instrument, limit=limit)
            elif strategy:
                records = self.decision_repository.get_by_strategy(strategy, limit=limit)
            else:
                records = self.decision_repository.get_recent(hours=hours, limit=limit)
            
            decisions = []
            for record in records:
                decisions.append({
                    'decision_id': record.decision_id,
                    'mission_id': record.mission_id,
                    'instrument': record.instrument,
                    'timeframe': record.timeframe,
                    'decision': record.decision,
                    'confidence': record.confidence,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None,
                    'strategy_used': record.strategy_used
                })
            
            return {
                'success': True,
                'data': {
                    'decisions': decisions,
                    'count': len(decisions),
                    'filters': {
                        'instrument': instrument,
                        'strategy': strategy,
                        'hours': hours
                    }
                }
            }
        except Exception as e:
            logger.error(f"Failed to get decision history: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'data': {
                    'decisions': [],
                    'count': 0
                }
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get decision repository statistics.
        
        Returns:
            Dictionary with repository statistics
        """
        try:
            stats = self.decision_repository.statistics()
            
            return {
                'success': True,
                'data': stats
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_confidence_statistics(self) -> Dict[str, Any]:
        """
        Get confidence-related statistics.
        
        Returns:
            Dictionary with confidence statistics
        """
        try:
            stats = self.decision_repository.statistics()
            
            confidence_stats = {
                'average_confidence': stats.get('averageConfidence', 0.0),
                'total_decisions': stats.get('totalDecisions', 0),
                'by_decision_type': stats.get('byDecision', {}),
                'by_instrument': stats.get('byInstrument', {})
            }
            
            return {
                'success': True,
                'data': confidence_stats
            }
        except Exception as e:
            logger.error(f"Failed to get confidence statistics: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_reasoning_samples(self, limit: int = 5) -> Dict[str, Any]:
        """
        Get recent decision reasoning samples.
        
        Args:
            limit: Maximum number of samples
            
        Returns:
            Dictionary with reasoning samples
        """
        try:
            records = self.decision_repository.get_latest(limit=limit)
            
            samples = []
            for record in records:
                result_snapshot = record.result_snapshot
                reasoning = result_snapshot.get('reasoning', '') if result_snapshot else ''
                
                samples.append({
                    'decision_id': record.decision_id,
                    'instrument': record.instrument,
                    'decision': record.decision,
                    'confidence': record.confidence,
                    'reasoning': reasoning,
                    'timestamp': record.timestamp.isoformat() if record.timestamp else None
                })
            
            return {
                'success': True,
                'data': {
                    'samples': samples,
                    'count': len(samples)
                }
            }
        except Exception as e:
            logger.error(f"Failed to get reasoning samples: {str(e)}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'data': {
                    'samples': [],
                    'count': 0
                }
            }