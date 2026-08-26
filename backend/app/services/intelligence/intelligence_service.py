"""
Falcon Intelligence Service
Service layer for the Intelligence Engine with database integration
"""
from typing import Optional
from sqlalchemy.orm import Session

from app.services.intelligence.intelligence_engine import IntelligenceEngine, IntelligenceDecision
from app.services.trend.trend_service import TrendService
from app.services.market_structure.structure_service import StructureService
from app.services.indicators.indicator_service import IndicatorService
from app.services.confluence.confluence_service import ConfluenceService
from app.models.market_candle import Timeframe
from app.core.providers import provider_manager


class IntelligenceService:
    """
    Intelligence Service - Facade for the Intelligence Layer.
    
    Integrates with existing Falcon services:
    - TrendService
    - StructureService
    - IndicatorService
    - ConfluenceService
    - ProviderManager
    
    Provides a single method to get complete AI intelligence.
    """
    
    def __init__(self, db: Session):
        """
        Initialize the intelligence service.
        
        Args:
            db: Database session
        """
        self.db = db
        self.intelligence_engine = IntelligenceEngine()
        
        self.trend_service = TrendService(db)
        self.structure_service = StructureService(db)
        self.indicator_service = IndicatorService(db)
        self.confluence_service = ConfluenceService(db)
        
        self.provider_manager = provider_manager
    
    def get_intelligence(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 200
    ) -> Optional[IntelligenceDecision]:
        """
        Get complete AI intelligence for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            limit: Number of candles to analyze
            
        Returns:
            IntelligenceDecision with complete AI analysis
        """
        trend_result = self.trend_service.calculate_trend(symbol, timeframe, limit)
        
        structure_result = self.structure_service.analyze_structure(symbol, timeframe, limit)
        
        indicator_result = self.indicator_service.calculate_indicators(symbol, timeframe, limit)
        
        mt_confluence_result = self.confluence_service.evaluate_confluence(
            symbol, timeframe, limit
        )
        
        current_price = self._get_current_price(symbol)
        
        if not current_price:
            return None
        
        decision = self.intelligence_engine.make_decision(
            symbol=symbol,
            timeframe=timeframe.value,
            trend_result=trend_result,
            structure_result=structure_result,
            indicator_result=indicator_result,
            mt_confluence_result=mt_confluence_result,
            current_price=current_price
        )
        
        return decision
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        """Get current market price for a symbol."""
        try:
            quote_response = self.provider_manager.get_market_quote(symbol)
            if quote_response and quote_response.quote:
                return quote_response.quote.lastPrice
            return None
        except Exception:
            return None
    
    def get_statistics(self) -> dict:
        """Get intelligence service statistics."""
        return self.intelligence_engine.get_statistics()
