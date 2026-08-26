"""
Falcon Signal Scorer
Scores signals from 0-100 using institutional criteria
"""
from typing import Optional, Dict, Any
from app.services.signals.signal_scoring_engine import SignalScoringEngine
from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.confluence_models import MultiTimeframeConfluenceResult
from app.schemas.signal_score_models import SignalScoreResult


class SignalScorer:
    """
    Signal Scorer - Wrapper around existing SignalScoringEngine.
    
    Provides a simplified interface for the Intelligence Layer.
    """
    
    def __init__(self):
        """Initialize the signal scorer."""
        self.engine = SignalScoringEngine()
    
    def score_signal(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult],
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse],
        mt_confluence_result: Optional[MultiTimeframeConfluenceResult],
        current_price: Optional[float]
    ) -> SignalScoreResult:
        """
        Score a trading signal.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            trend_result: Trend analysis
            structure_result: Market structure analysis
            indicator_result: Indicator analysis
            mt_confluence_result: Multi-timeframe confluence
            current_price: Current market price
            
        Returns:
            SignalScoreResult with score 0-100 and breakdown
        """
        return self.engine.calculate_signal_score(
            symbol=symbol,
            timeframe=timeframe,
            trend_result=trend_result,
            structure_result=structure_result,
            indicator_result=indicator_result,
            mt_confluence_result=mt_confluence_result,
            current_price=current_price
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get scorer statistics."""
        return self.engine.get_statistics()
