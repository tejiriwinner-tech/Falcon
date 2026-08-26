"""
Falcon Analysis API
Technical indicator, trend, market structure, and confluence analysis endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.config.database import get_db
from app.models.market_candle import Timeframe
from app.services.indicators.indicator_service import IndicatorService
from app.services.trend.trend_service import TrendService
from app.services.market_structure.structure_service import StructureService
from app.services.confluence.confluence_service import ConfluenceService
from app.services.confluence.multi_timeframe_confluence_engine import MultiTimeframeConfluenceEngine
from app.services.signals.signal_scoring_engine import SignalScoringEngine
from app.services.decision.decision_engine import AIDecisionEngine
from app.schemas.indicator_models import IndicatorResponse, IndicatorStatistics
from app.schemas.trend_models import TrendResult, TrendStatistics
from app.schemas.market_structure_models import MarketStructureResult, StructureStatistics
from app.schemas.confluence_models import (
    SignalDecision, ConfluenceStatistics,
    MultiTimeframeConfluenceResult, MultiTimeframeConfluenceStatistics
)
from app.schemas.signal_score_models import SignalScoreResult, SignalScoreStatistics
from app.schemas.decision_models import AIDecisionResult, AIDecisionStatistics

router = APIRouter()


@router.get("/indicators", response_model=IndicatorResponse)
async def get_indicators(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: str = Query(..., description="Timeframe (M1, M5, M15, M30, H1, H4, D1)"),
    limit: int = Query(200, ge=50, le=1000, description="Number of candles to use for calculation"),
    db: Session = Depends(get_db)
) -> IndicatorResponse:
    """
    Calculate technical indicators for a symbol and timeframe.
    
    Returns all calculated indicators including:
    - EMA (20, 50, 100, 200)
    - SMA (20, 50)
    - RSI (14)
    - ATR (14)
    - MACD (12, 26, 9)
    - Bollinger Bands (20, 2)
    - Trend analysis
    - Trading signal
    
    Args:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        limit: Number of historical candles to use
        db: Database session
        
    Returns:
        IndicatorResponse with all calculated indicators
        
    Raises:
        HTTPException: If timeframe is invalid or insufficient data
    """
    # Validate timeframe
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of: M1, M5, M15, M30, H1, H4, D1"
        )
    
    # Calculate indicators
    indicator_service = IndicatorService(db)
    result = indicator_service.calculate_indicators(symbol, tf, limit)
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient historical data for {symbol} {timeframe}. At least 50 candles required."
        )
    
    return result


@router.get("/indicators/statistics", response_model=IndicatorStatistics)
async def get_indicator_statistics(
    db: Session = Depends(get_db)
) -> IndicatorStatistics:
    """
    Get indicator engine runtime statistics.
    
    Returns performance metrics including:
    - Total calculations performed
    - Execution time metrics
    - Cache hit/miss ratios
    
    Args:
        db: Database session
        
    Returns:
        IndicatorStatistics with performance metrics
    """
    indicator_service = IndicatorService(db)
    return indicator_service.get_statistics()


@router.get("/trend", response_model=TrendResult)
async def get_trend(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: str = Query(..., description="Timeframe (M1, M5, M15, M30, H1, H4, D1)"),
    limit: int = Query(200, ge=50, le=1000, description="Number of candles to use for analysis"),
    db: Session = Depends(get_db)
) -> TrendResult:
    """
    Calculate market trend for a symbol and timeframe.
    
    Returns trend analysis including:
    - Trend direction (BULLISH, BEARISH, SIDEWAYS, UNKNOWN)
    - Trend strength (VERY_WEAK to VERY_STRONG)
    - Confidence score (0-100)
    - EMA alignment analysis
    - Price position analysis
    - Swing structure analysis
    
    Args:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        limit: Number of historical candles to use
        db: Database session
        
    Returns:
        TrendResult with complete trend analysis
        
    Raises:
        HTTPException: If timeframe is invalid or insufficient data
    """
    # Validate timeframe
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of: M1, M5, M15, M30, H1, H4, D1"
        )
    
    # Calculate trend
    trend_service = TrendService(db)
    result = trend_service.calculate_trend(symbol, tf, limit)
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient historical data for {symbol} {timeframe}. At least 20 candles required."
        )
    
    return result


@router.get("/trend/statistics", response_model=TrendStatistics)
async def get_trend_statistics(
    db: Session = Depends(get_db)
) -> TrendStatistics:
    """
    Get trend engine runtime statistics.
    
    Returns performance metrics including:
    - Total calculations performed
    - Average execution time
    - Cache hit/miss ratios
    - Last calculation timestamp
    
    Args:
        db: Database session
        
    Returns:
        TrendStatistics with performance metrics
    """
    trend_service = TrendService(db)
    return trend_service.get_statistics()


@router.get("/market-structure", response_model=MarketStructureResult)
async def get_market_structure(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: str = Query(..., description="Timeframe (M1, M5, M15, M30, H1, H4, D1)"),
    limit: int = Query(200, ge=50, le=1000, description="Number of candles to use for analysis"),
    db: Session = Depends(get_db)
) -> MarketStructureResult:
    """
    Analyze market structure for a symbol and timeframe.
    
    Returns market structure analysis including:
    - Swing points (highs/lows)
    - Structural events (BOS, CHoCH)
    - Support & Resistance levels
    - Supply & Demand zones
    - Liquidity zones
    - Premium/Discount zones
    - Market phase classification
    
    Args:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        limit: Number of historical candles to use
        db: Database session
        
    Returns:
        MarketStructureResult with complete structure analysis
        
    Raises:
        HTTPException: If timeframe is invalid or insufficient data
    """
    # Validate timeframe
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of: M1, M5, M15, M30, H1, H4, D1"
        )
    
    # Analyze structure
    structure_service = StructureService(db)
    result = structure_service.analyze_structure(symbol, tf, limit)
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient historical data for {symbol} {timeframe}. At least 20 candles required."
        )
    
    return result


@router.get("/market-structure/statistics", response_model=StructureStatistics)
async def get_structure_statistics(
    db: Session = Depends(get_db)
) -> StructureStatistics:
    """
    Get market structure engine runtime statistics.
    
    Returns performance metrics including:
    - Total calculations performed
    - Average execution time
    - Cache hit/miss ratios
    - Active supply/demand zones
    - Last calculation timestamp
    
    Args:
        db: Database session
        
    Returns:
        StructureStatistics with performance metrics
    """
    structure_service = StructureService(db)
    return structure_service.get_statistics()


@router.get("/confluence", response_model=SignalDecision)
async def get_confluence(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: str = Query(..., description="Timeframe (M1, M5, M15, M30, H1, H4, D1)"),
    limit: int = Query(200, ge=50, le=1000, description="Number of candles to use for analysis"),
    current_price: float = Query(None, description="Current market price (optional)"),
    db: Session = Depends(get_db)
) -> SignalDecision:
    """
    Evaluate signal confluence for a symbol and timeframe.
    
    Returns trading decision including:
    - Signal direction (BUY, SELL, WAIT)
    - Signal quality (VERY_LOW to VERY_HIGH)
    - Confidence score (0-100)
    - Trade levels (entry, stop loss, take profits, risk/reward)
    - Confluence factors (trend, structure, indicators, news, volatility, risk)
    - Detailed explanations and warnings
    
    Args:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        limit: Number of historical candles to use
        current_price: Current market price (optional)
        db: Database session
        
    Returns:
        SignalDecision with complete confluence analysis
        
    Raises:
        HTTPException: If timeframe is invalid or insufficient data
    """
    # Validate timeframe
    try:
        tf = Timeframe(timeframe)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timeframe: {timeframe}. Must be one of: M1, M5, M15, M30, H1, H4, D1"
        )
    
    # Evaluate confluence
    confluence_service = ConfluenceService(db)
    result = confluence_service.evaluate_confluence(symbol, tf, limit, current_price)
    
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Insufficient historical data for {symbol} {timeframe}. At least 20 candles required."
        )
    
    return result


@router.get("/confluence/statistics", response_model=ConfluenceStatistics)
async def get_confluence_statistics(
    db: Session = Depends(get_db)
) -> ConfluenceStatistics:
    """
    Get confluence engine runtime statistics.
    
    Returns performance metrics including:
    - Total calculations performed
    - Average execution time
    - Buy/Sell/Wait signal counts
    - Cache hit/miss ratios
    - Average confidence score
    - Last calculation timestamp
    
    Args:
        db: Database session
        
    Returns:
        ConfluenceStatistics with performance metrics
    """
    confluence_service = ConfluenceService(db)
    return confluence_service.get_statistics()


@router.get("/confluence/multi-timeframe", response_model=MultiTimeframeConfluenceResult)
async def get_multi_timeframe_confluence(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframes: str = Query("H4,H1,M15,M5", description="Comma-separated timeframes (e.g., H4,H1,M15,M5)"),
    db: Session = Depends(get_db)
) -> MultiTimeframeConfluenceResult:
    """
    Evaluate multi-timeframe confluence for a symbol.
    
    Returns confluence analysis across multiple timeframes including:
    - Individual timeframe analyses (trend, structure, indicators)
    - Overall confluence score (0-100)
    - Trading recommendation (BUY, SELL, WAIT, NO_TRADE)
    - Aligned and conflicting timeframes
    - Recommendation explanation
    
    Args:
        symbol: Instrument symbol
        timeframes: Comma-separated timeframes to analyze
        db: Database session
        
    Returns:
        MultiTimeframeConfluenceResult with complete multi-timeframe analysis
        
    Raises:
        HTTPException: If insufficient data for any timeframe
    """
    # Parse timeframes
    timeframe_list = [tf.strip() for tf in timeframes.split(",")]
    
    # Validate timeframes
    valid_timeframes = []
    for tf in timeframe_list:
        try:
            Timeframe(tf)
            valid_timeframes.append(tf)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timeframe: {tf}. Must be one of: M1, M5, M15, M30, H1, H4, D1"
            )
    
    # Initialize services
    trend_service = TrendService(db)
    structure_service = StructureService(db)
    indicator_service = IndicatorService(db)
    mt_confluence_engine = MultiTimeframeConfluenceEngine()
    
    # Collect data for each timeframe
    timeframe_data = {}
    for tf in valid_timeframes:
        tf_enum = Timeframe(tf)
        
        # Get trend
        trend_result = trend_service.calculate_trend(symbol, tf_enum, limit=200)
        if not trend_result:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient trend data for {symbol} {tf}"
            )
        
        # Get structure
        structure_result = structure_service.analyze_structure(symbol, tf_enum, limit=200)
        if not structure_result:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient structure data for {symbol} {tf}"
            )
        
        # Get indicators
        indicator_result = indicator_service.calculate_indicators(symbol, tf_enum, limit=200)
        if not indicator_result:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient indicator data for {symbol} {tf}"
            )
        
        timeframe_data[tf] = {
            "trend": trend_result,
            "structure": structure_result,
            "indicator": indicator_result
        }
    
    # Calculate multi-timeframe confluence
    result = mt_confluence_engine.calculate_confluence(symbol, timeframe_data, valid_timeframes)
    
    return result


@router.get("/confluence/multi-timeframe/statistics", response_model=MultiTimeframeConfluenceStatistics)
async def get_multi_timeframe_confluence_statistics(
    db: Session = Depends(get_db)
) -> MultiTimeframeConfluenceStatistics:
    """
    Get multi-timeframe confluence engine runtime statistics.
    
    Returns performance metrics including:
    - Total calculations performed
    - Cache hit/miss ratios
    - Average execution time
    - Fastest/slowest calculation times
    - Last calculation timestamp
    
    Args:
        db: Database session
        
    Returns:
        MultiTimeframeConfluenceStatistics with performance metrics
    """
    mt_confluence_engine = MultiTimeframeConfluenceEngine()
    stats = mt_confluence_engine.get_statistics()
    
    return MultiTimeframeConfluenceStatistics(
        calculations=stats['calculations'],
        cacheHits=stats['cacheHits'],
        cacheMisses=stats['cacheMisses'],
        averageExecutionTime=stats['averageExecutionTime'],
        fastestCalculation=stats['fastestCalculation'],
        slowestCalculation=stats['slowestCalculation'],
        lastCalculation=None  # Engine doesn't track this directly
    )


@router.get("/signal-score", response_model=SignalScoreResult)
async def get_signal_score(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: str = Query(..., description="Timeframe (M1, M5, M15, M30, H1, H4, D1)"),
    current_price: float = Query(None, description="Current market price (optional)"),
    db: Session = Depends(get_db)
) -> SignalScoreResult:
    """
    Calculate signal quality score for a symbol and timeframe.
    
    Returns comprehensive signal quality evaluation including:
    - Overall signal quality score (0-100)
    - Quality classification (EXCELLENT to INVALID)
    - Trading recommendation (STRONG_BUY to NO_SIGNAL)
    - Risk rating (LOW, MEDIUM, HIGH)
    - Component scores (Trend, Structure, Momentum, etc.)
    - Detailed explanations for each component
    
    Args:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        current_price: Current market price (optional)
        db: Database session
        
    Returns:
        SignalScoreResult with complete signal quality analysis
        
    Raises:
        HTTPException: If timeframe is invalid or insufficient data
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
    
    # Get trend result
    trend_result = trend_service.calculate_trend(symbol, tf, limit=200)
    
    # Get structure result
    structure_result = structure_service.analyze_structure(symbol, tf, limit=200)
    
    # Get indicator result
    indicator_result = indicator_service.calculate_indicators(symbol, tf, limit=200)
    
    # Get current price from indicator if not provided
    if current_price is None and indicator_result:
        current_price = indicator_result.bb_middle
    
    # Calculate signal score
    result = signal_scoring_engine.calculate_signal_score(
        symbol=symbol,
        timeframe=timeframe,
        trend_result=trend_result,
        structure_result=structure_result,
        indicator_result=indicator_result,
        current_price=current_price
    )
    
    return result


@router.get("/signal-score/statistics", response_model=SignalScoreStatistics)
async def get_signal_score_statistics(
    db: Session = Depends(get_db)
) -> SignalScoreStatistics:
    """
    Get signal scoring engine runtime statistics.
    
    Returns performance metrics including:
    - Total calculations performed
    - Average execution time
    - Cache hit/miss ratios
    - Highest/lowest scores recorded
    - Last calculation timestamp
    
    Args:
        db: Database session
        
    Returns:
        SignalScoreStatistics with performance metrics
    """
    signal_scoring_engine = SignalScoringEngine()
    stats = signal_scoring_engine.get_statistics()
    
    return SignalScoreStatistics(
        calculations=stats['calculations'],
        averageExecutionTime=stats['averageExecutionTime'],
        cacheHits=stats['cacheHits'],
        cacheMisses=stats['cacheMisses'],
        highestScore=stats['highestScore'],
        lowestScore=stats['lowestScore'],
        lastCalculation=None  # Engine doesn't track this directly
    )


@router.get("/decision", response_model=AIDecisionResult)
async def get_ai_decision(
    symbol: str = Query(..., description="Instrument symbol (e.g., XAUUSD, GBPUSD)"),
    timeframe: str = Query(..., description="Timeframe (M1, M5, M15, M30, H1, H4, D1)"),
    db: Session = Depends(get_db)
) -> AIDecisionResult:
    """
    Get AI trading decision for a symbol and timeframe.
    
    Returns comprehensive AI decision including:
    - Final decision (STRONG_BUY, BUY, WAIT, SELL, STRONG_SELL, NO_TRADE)
    - AI confidence (0-100)
    - Signal quality score
    - Trend direction and strength
    - Structure and liquidity bias
    - Multi-timeframe confluence score
    - Risk rating
    - Detailed reasoning
    - Warnings
    
    Args:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        db: Database session
        
    Returns:
        AIDecisionResult with complete AI decision analysis
        
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
    
    # Get MT confluence result (optional - not required for decision)
    mt_confluence_result = None  # Can be added if needed
    
    # Make AI decision
    result = ai_decision_engine.make_decision(
        symbol=symbol,
        timeframe=timeframe,
        trend_result=trend_result,
        structure_result=structure_result,
        indicator_result=indicator_result,
        mt_confluence_result=mt_confluence_result,
        signal_score_result=signal_score_result
    )
    
    return result


@router.get("/decision/statistics", response_model=AIDecisionStatistics)
async def get_ai_decision_statistics(
    db: Session = Depends(get_db)
) -> AIDecisionStatistics:
    """
    Get AI decision engine runtime statistics.
    
    Returns performance metrics including:
    - Total decisions made
    - BUY/SELL/WAIT counts
    - Average confidence
    - Average execution time
    - Cache hit/miss ratios
    - Highest/lowest confidence recorded
    
    Args:
        db: Database session
        
    Returns:
        AIDecisionStatistics with performance metrics
    """
    ai_decision_engine = AIDecisionEngine()
    stats = ai_decision_engine.get_statistics()
    
    return AIDecisionStatistics(
        totalDecisions=stats['totalDecisions'],
        buyCount=stats['buyCount'],
        sellCount=stats['sellCount'],
        waitCount=stats['waitCount'],
        averageConfidence=stats['averageConfidence'],
        averageExecutionTime=stats['averageExecutionTime'],
        cacheHits=stats['cacheHits'],
        cacheMisses=stats['cacheMisses'],
        highestConfidence=stats['highestConfidence'],
        lowestConfidence=stats['lowestConfidence']
    )
