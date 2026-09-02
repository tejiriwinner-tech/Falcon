"""
Falcon Intelligence API
AI Trading Intelligence endpoints
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config.database import get_db
from app.core.validation.input_validator import InputValidator
from app.core.security.auth import verify_api_key
from app.services.intelligence.intelligence_service import IntelligenceService
from app.services.decision.decision_intelligence_service import DecisionIntelligenceService
from app.models.market_candle import Timeframe
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("")
async def get_intelligence(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: Timeframe = Query(Timeframe.H1, description="Timeframe for analysis"),
    db: Session = Depends(get_db)
):
    """
    Get complete AI trading intelligence for a symbol.
    
    Returns:
    - Overall Decision (BUY/SELL/WAIT/AVOID)
    - AI Confidence (%)
    - Signal Score (0-100)
    - Confluence Score (0-100)
    - Risk Score (0-100)
    - Market State
    - Trend Analysis
    - Entry Quality
    - Risk Management Levels (Entry, Stop, Target)
    - Reasoning
    
    This is Falcon's complete intelligence output.
    """
    try:
        # Validate and sanitize symbol input
        validated_symbol = InputValidator.validate_symbol(symbol)
        
        # Use real IntelligenceService to generate trading intelligence
        intelligence_service = IntelligenceService(db)
        
        try:
            decision = intelligence_service.get_intelligence(
                symbol=validated_symbol,
                timeframe=timeframe,
                limit=200
            )
            
            if not decision:
                # If decision engine fails, return neutral response
                now = datetime.now(timezone.utc)
                return {
                    'success': True,
                    'data': {
                        'symbol': validated_symbol,
                        'timeframe': timeframe.value,
                        'decision': 'WAIT',
                        'confidence': 50.0,
                        'signalScore': 50.0,
                        'confluenceScore': 50.0,
                        'riskScore': 50.0,
                        'marketState': 'NEUTRAL',
                        'trend': 'NEUTRAL',
                        'entry': '0.0',
                        'stop': 0.0,
                        'target': 0.0,
                        'reasoning': 'Insufficient data available for analysis. Ensure market data is available for this symbol.',
                        'timestamp': now.isoformat()
                    }
                }
            
            # Convert IntelligenceDecision to API response format
            now = datetime.now(timezone.utc)
            entry_val = getattr(decision, 'entry_price', None) or getattr(decision, 'entry', None)
            stop_val = getattr(decision, 'stop_loss', None) or getattr(decision, 'stop', None)
            target_val = getattr(decision, 'take_profit', None) or getattr(decision, 'target', None)
            return {
                'success': True,
                'data': {
                    'symbol': validated_symbol,
                    'timeframe': timeframe.value,
                    'decision': decision.decision,
                    'confidence': decision.confidence,
                    'signalScore': decision.signal_score,
                    'confluenceScore': decision.confluence_score,
                    'riskScore': decision.risk_score,
                    'marketState': decision.market_state,
                    'trend': decision.trend,
                    'entry': str(entry_val) if entry_val is not None else '0.0',
                    'stop': str(stop_val) if stop_val is not None else '0.0',
                    'target': str(target_val) if target_val is not None else '0.0',
                    'reasoning': decision.reasoning,
                    'timestamp': now.isoformat()
                }
            }
        
        except Exception as e:
            logger.error(f"Intelligence service error for {validated_symbol}: {str(e)}")
            # Return neutral response on error
            now = datetime.now(timezone.utc)
            return {
                'success': True,
                'data': {
                    'symbol': validated_symbol,
                    'timeframe': timeframe.value,
                    'decision': 'WAIT',
                    'confidence': 50.0,
                    'signalScore': 50.0,
                    'confluenceScore': 50.0,
                    'riskScore': 50.0,
                    'marketState': 'NEUTRAL',
                    'trend': 'NEUTRAL',
                    'entry': '0.0',
                    'stop': 0.0,
                    'target': 0.0,
                    'reasoning': f'Analysis failed: {str(e)}',
                    'timestamp': now.isoformat()
                }
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Intelligence API error for {validated_symbol} {timeframe.value}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate intelligence: {str(e)}"
        )


@router.get("/statistics")
async def get_intelligence_statistics(
    db: Session = Depends(get_db)
):
    """
    Get Intelligence Engine statistics.
    
    Returns execution metrics for all intelligence components.
    """
    try:
        intelligence_service = IntelligenceService(db)
        stats = intelligence_service.get_statistics()
        
        return {
            'success': True,
            'data': stats
        }
    
    except Exception as e:
        logger.error(f"Intelligence statistics error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )


# ─── Decision Intelligence Endpoints (Milestone 9) ────────────────────────

@router.get("/latest")
async def get_latest_decisions(
    limit: int = Query(10, ge=1, le=100, description="Maximum number of decisions to return"),
    db: Session = Depends(get_db)
):
    """
    Get the most recent decisions from the Decision Intelligence Engine.
    
    Returns:
    - Latest decisions with full metadata
    - Trade management information
    - Confidence scores
    """
    try:
        service = DecisionIntelligenceService(db)
        result = service.get_latest_decisions(limit=limit)
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Failed to retrieve latest decisions')
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get latest decisions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve latest decisions: {str(e)}"
        )


@router.get("/history")
async def get_decision_history(
    instrument: Optional[str] = Query(None, description="Filter by instrument"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    hours: int = Query(24, ge=1, le=168, description="Time window in hours"),
    limit: int = Query(100, ge=1, le=500, description="Maximum records to return"),
    db: Session = Depends(get_db)
):
    """
    Get decision history with optional filters.
    
    Returns:
    - Filtered decision history
    - Confidence trends
    - Strategy performance
    """
    try:
        service = DecisionIntelligenceService(db)
        result = service.get_decision_history(
            instrument=instrument,
            strategy=strategy,
            hours=hours,
            limit=limit
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Failed to retrieve decision history')
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get decision history: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve decision history: {str(e)}"
        )


@router.get("/{decision_id}")
async def get_decision_by_id(
    decision_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific decision by its unique ID.
    
    Returns:
    - Complete decision details
    - Context snapshot for replay
    - Result snapshot
    - Trade management information
    """
    try:
        service = DecisionIntelligenceService(db)
        result = service.get_decision_by_id(decision_id)
        
        if not result['success']:
            raise HTTPException(
                status_code=404,
                detail=result.get('error', f'Decision {decision_id} not found')
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get decision {decision_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve decision: {str(e)}"
        )


@router.post("/evaluate")
async def evaluate_decision(
    candidate_id: str = Query(..., description="Candidate identifier"),
    mission_id: str = Query(..., description="Mission identifier"),
    instrument: str = Query(..., description="Trading instrument"),
    timeframe: str = Query(..., description="Trading timeframe"),
    direction: str = Query("BUY", description="Trade direction (BUY/SELL)"),
    confidence: float = Query(50.0, ge=0.0, le=100.0, description="Candidate confidence"),
    risk_reward: float = Query(2.0, ge=0.1, description="Risk-reward ratio"),
    spread: float = Query(0.0, ge=0.0, description="Current spread"),
    session: str = Query("UNKNOWN", description="Trading session"),
    trend: str = Query("NEUTRAL", description="Market trend"),
    volatility: str = Query("MODERATE", description="Volatility level"),
    news_impact: str = Query("LOW", description="News impact level"),
    market_open: bool = Query(True, description="Whether market is open"),
    data_age_seconds: int = Query(0, ge=0, description="Age of market data"),
    strategy_id: str = Query("default", description="Strategy identifier"),
    strategy_name: str = Query("Default Strategy", description="Strategy name"),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Evaluate a trading decision using the Decision Intelligence Engine.
    
    This endpoint processes a candidate through the full Decision Intelligence pipeline
    and persists the result for historical analysis.
    
    Returns:
    - Decision recommendation (BUY/SELL/WAIT/AVOID/NO_TRADE/MONITOR)
    - Confidence score with grade
    - Detailed reasoning
    - Risk gate warnings
    - Persistence status
    """
    try:
        # Validate inputs
        validated_instrument = InputValidator.validate_symbol(instrument)
        validated_strategy_name = InputValidator.validate_string(strategy_name, "strategy_name", max_length=200)
        validated_direction = InputValidator.validate_string(direction, "direction", max_length=10)
        
        service = DecisionIntelligenceService(db)
        result = service.evaluate_decision(
            candidate_id=candidate_id,
            mission_id=mission_id,
            instrument=validated_instrument,
            timeframe=timeframe,
            direction=validated_direction,
            confidence=confidence,
            risk_reward=risk_reward,
            spread=spread,
            session=session,
            trend=trend,
            volatility=volatility,
            news_impact=news_impact,
            market_open=market_open,
            data_age_seconds=data_age_seconds,
            strategy_id=strategy_id,
            strategy_name=validated_strategy_name
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Decision evaluation failed')
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Decision evaluation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Decision evaluation failed: {str(e)}"
        )


@router.get("/statistics/decision")
async def get_decision_statistics(
    db: Session = Depends(get_db)
):
    """
    Get Decision Intelligence Engine statistics.
    
    Returns:
    - Total decisions count
    - Decisions by type
    - Decisions by instrument
    - Average confidence
    - Average processing time
    """
    try:
        service = DecisionIntelligenceService(db)
        result = service.get_statistics()
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Failed to retrieve statistics')
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get decision statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve statistics: {str(e)}"
        )


@router.get("/confidence")
async def get_confidence_statistics(
    db: Session = Depends(get_db)
):
    """
    Get confidence-related statistics from decision history.
    
    Returns:
    - Average confidence scores
    - Confidence distribution by decision type
    - Confidence trends by instrument
    """
    try:
        service = DecisionIntelligenceService(db)
        result = service.get_confidence_statistics()
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Failed to retrieve confidence statistics')
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get confidence statistics: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve confidence statistics: {str(e)}"
        )


@router.get("/reasoning")
async def get_reasoning_samples(
    limit: int = Query(5, ge=1, le=20, description="Number of reasoning samples"),
    db: Session = Depends(get_db)
):
    """
    Get recent decision reasoning samples.
    
    Returns:
    - Recent decision reasoning texts
    - Associated confidence scores
    - Decision types
    """
    try:
        service = DecisionIntelligenceService(db)
        result = service.get_reasoning_samples(limit=limit)
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'Failed to retrieve reasoning samples')
            )
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get reasoning samples: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve reasoning samples: {str(e)}"
        )
