"""
Falcon Confluence Service
Service layer for signal confluence and decision orchestration.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.market_candle import Timeframe
from app.services.trend.trend_service import TrendService
from app.services.market_structure.structure_service import StructureService
from app.services.indicators.indicator_service import IndicatorService
from app.services.confluence.confluence_engine import ConfluenceEngine
from app.schemas.confluence_models import SignalDecision, ConfluenceStatistics


class ConfluenceService:
    """
    Service for signal confluence and trading decision analysis.
    
    Orchestrates confluence analysis by:
    - Loading trend analysis from TrendService
    - Loading market structure from StructureService
    - Loading indicator calculations from IndicatorService
    - Executing ConfluenceEngine for decision analysis
    - Caching results for 30 seconds
    - Returning structured SignalDecision
    """
    
    # Class-level shared cache so results and hit/miss statistics persist
    # across per-request service instances, fulfilling the documented
    # "caching results for 30 seconds" design.
    _cache: dict = {}
    _cache_hits: int = 0
    _cache_misses: int = 0
    
    def __init__(self, db: Session):
        self.db = db
        self.trend_service = TrendService(db)
        self.structure_service = StructureService(db)
        self.indicator_service = IndicatorService(db)
        self.confluence_engine = ConfluenceEngine()
        
        self._cache_ttl = 30  # 30 second cache TTL
    
    def _bump_cache_hits(self) -> None:
        """Increment the shared cache-hit counter (property-aware)."""
        cls = type(self)
        if isinstance(cls.__dict__.get("_cache_hits"), property):
            self._cache_hits += 1
        else:
            cls._cache_hits += 1

    def _bump_cache_misses(self) -> None:
        """Increment the shared cache-miss counter (property-aware)."""
        cls = type(self)
        if isinstance(cls.__dict__.get("_cache_misses"), property):
            self._cache_misses += 1
        else:
            cls._cache_misses += 1

    def _reset_cache_stats(self) -> None:
        """Zero the shared cache counters (property-aware)."""
        cls = type(self)
        for name in ("_cache_hits", "_cache_misses"):
            if isinstance(cls.__dict__.get(name), property):
                setattr(self, name, 0)
            else:
                setattr(cls, name, 0)

    def evaluate_confluence(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 200,
        current_price: Optional[float] = None
    ) -> Optional[SignalDecision]:
        """
        Evaluate signal confluence for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            limit: Number of candles to use for analysis
            current_price: Current market price (optional, will use latest candle if not provided)
            
        Returns:
            SignalDecision with complete confluence analysis or None if insufficient data
        """
        cache_key = f"{symbol}_{timeframe.value}"
        
        # Check cache
        if cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self._cache_ttl:
                self._bump_cache_hits()
                return cached_result
        
        self._bump_cache_misses()
        
        # Load trend analysis
        trend_result = self.trend_service.calculate_trend(symbol, timeframe, limit)
        
        if trend_result is None:
            return None
        
        # Load market structure
        structure_result = self.structure_service.analyze_structure(symbol, timeframe, limit)
        
        if structure_result is None:
            return None
        
        # Load indicators
        indicator_result = self.indicator_service.calculate_indicators(symbol, timeframe, limit)
        
        if indicator_result is None:
            return None
        
        # Get current price from latest candle if not provided
        if current_price is None:
            candles = self.indicator_service.history_service.get_latest_candles(symbol, timeframe, 1)
            if candles:
                current_price = candles[0].close
            else:
                current_price = indicator_result.bb_middle  # Fallback to BB middle
        
        # Evaluate confluence
        signal_decision = self.confluence_engine.evaluate(
            trend_result,
            structure_result,
            indicator_result,
            current_price,
            news_events=None,  # News integration not yet implemented
            economic_calendar=None  # Economic calendar integration not yet implemented
        )
        
        # Update cache
        self._cache[cache_key] = (signal_decision, datetime.now(timezone.utc))
        
        return signal_decision
    
    def get_statistics(self) -> ConfluenceStatistics:
        """
        Get confluence service statistics.
        
        Returns:
            ConfluenceStatistics with cache and calculation metrics
        """
        engine_stats = self.confluence_engine.get_statistics()
        
        return ConfluenceStatistics(
            calculations=engine_stats['calculations'],
            average_execution_time=engine_stats['average_execution_time'],
            buy_signals=engine_stats['buy_signals'],
            sell_signals=engine_stats['sell_signals'],
            wait_signals=engine_stats['wait_signals'],
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
            average_confidence=engine_stats['average_confidence'],
            last_calculation=datetime.now(timezone.utc) if self._cache_hits + self._cache_misses > 0 else None
        )
    
    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear the calculation cache.
        
        Args:
            symbol: If provided, only clear cache for this symbol
        """
        if symbol:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(symbol)]
            for key in keys_to_delete:
                del self._cache[key]
        else:
            self._cache.clear()
            self._reset_cache_stats()
