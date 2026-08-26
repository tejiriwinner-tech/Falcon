"""
Falcon Risk Management API
Risk evaluation and statistics endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.config.database import get_db
from app.models.market_candle import Timeframe
from app.services.trend.trend_service import TrendService
from app.services.market_structure.structure_service import StructureService
from app.services.indicators.indicator_service import IndicatorService
from app.services.decision.decision_engine import AIDecisionEngine
from app.services.signals.signal_scoring_engine import SignalScoringEngine
from app.services.signals.signal_generator import SignalGenerator
from app.services.risk.risk_management_engine import RiskManagementEngine
from app.services.risk.risk_repository import RiskRepository
from app.schemas.risk_models import RiskAssessment, RiskStatistics

router = APIRouter()


@router.get("/evaluate", response_model=RiskAssessment)
async def evaluate_risk(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: str = Query(..., description="Timeframe (M1, M5, M15, M30, H1, H4, D1)"),
    account_balance: float = Query(default=100000.0, description="Account balance for risk calculation"),
    position_size: float = Query(default=1.0, description="Position size for risk calculation"),
    db: Session = Depends(get_db)
) -> RiskAssessment:
    """
    Evaluate risk for a trade setup.
    
    Generates a trade setup and evaluates it against Falcon's risk policy.
    Returns complete risk assessment including decision, risk score, risk percentage,
    daily exposure, portfolio exposure, correlation level, reasons, and warnings.
    
    Args:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        account_balance: Account balance for risk calculation
        position_size: Position size for risk calculation
        db: Database session
        
    Returns:
        RiskAssessment with complete risk evaluation
        
    Raises:
        HTTPException: If timeframe is invalid
    """
    # Validate timeframe
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of: M1, M5, M15, M30, H1, H4, D1"
        )
    
    # Initialize services
    trend_service = TrendService(db)
    structure_service = StructureService(db)
    indicator_service = IndicatorService(db)
    signal_scoring_engine = SignalScoringEngine()
    ai_decision_engine = AIDecisionEngine()
    signal_generator = SignalGenerator()
    risk_engine = RiskManagementEngine()
    risk_repository = RiskRepository()
    
    # Get trend result
    trend_result = trend_service.calculate_trend(symbol, tf, limit=200)
    
    # Get structure result
    structure_result = structure_service.analyze_structure(symbol, tf, limit=200)
    
    # Get indicator result
    indicator_result = indicator_service.calculate_indicators(symbol, tf, limit=200)
    
    # Get signal score result
    signal_score_result = signal_scoring_engine.calculate_signal_score(
        symbol=symbol,
        timeframe=timeframe,
        trend_result=trend_result,
        structure_result=structure_result,
        indicator_result=indicator_result,
        current_price=indicator_result.bb_middle if indicator_result else None
    )
    
    # Get AI decision
    ai_decision = ai_decision_engine.make_decision(
        symbol=symbol,
        timeframe=timeframe,
        trend_result=trend_result,
        structure_result=structure_result,
        indicator_result=indicator_result,
        signal_score_result=signal_score_result
    )
    
    # Generate signal
    trade_setup = signal_generator.generate_signal(
        symbol=symbol,
        timeframe=timeframe,
        ai_decision=ai_decision,
        trend_result=trend_result,
        structure_result=structure_result,
        indicator_result=indicator_result,
        signal_score_result=signal_score_result,
        current_price=indicator_result.bb_middle if indicator_result else None
    )
    
    # Evaluate risk
    risk_assessment = risk_engine.evaluate(
        trade_setup=trade_setup,
        ai_decision=ai_decision,
        trend_result=trend_result,
        mt_confluence_result=None,  # Confluence not used in current implementation
        account_balance=account_balance,
        position_size=position_size
    )
    
    # Save assessment to repository
    risk_repository.save_assessment(risk_assessment)
    
    return risk_assessment


@router.get("/statistics", response_model=RiskStatistics)
async def get_risk_statistics(
    db: Session = Depends(get_db)
) -> RiskStatistics:
    """
    Get risk management engine statistics.
    
    Returns performance metrics including:
    - Total assessments
    - Approved/approved with warning/rejected counts
    - Average risk score
    - Average risk percentage
    - Average risk/reward ratio
    - Average assessment time
    - Rejection reasons breakdown
    
    Args:
        db: Database session
        
    Returns:
        RiskStatistics with performance metrics
    """
    risk_engine = RiskManagementEngine()
    risk_repository = RiskRepository()
    
    # Get engine statistics
    engine_stats = risk_engine.get_statistics()
    
    # Get repository statistics
    repo_stats = risk_repository.statistics()
    
    return RiskStatistics(
        totalAssessments=repo_stats.get('totalAssessments', 0),
        approvedCount=repo_stats.get('approvedCount', 0),
        approvedWithWarningCount=repo_stats.get('approvedWithWarningCount', 0),
        rejectedCount=repo_stats.get('rejectedCount', 0),
        averageRiskScore=repo_stats.get('averageRiskScore', 0.0),
        averageRiskPercent=repo_stats.get('averageRiskPercent', 0.0),
        averageRR=repo_stats.get('averageRR', 0.0),
        averageAssessmentTime=engine_stats.get('averageAssessmentTime', 0.0),
        rejectionReasons=engine_stats.get('rejectionReasons', {})
    )
