"""
Falcon Market Structure Service
Service layer for market structure analysis orchestration.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.market_candle import MarketCandle, Timeframe
from app.services.history.history_service import HistoryService
from app.services.trend.trend_service import TrendService
from app.services.indicators.indicator_service import IndicatorService
from app.services.market_structure.structure_engine import StructureEngine
from app.schemas.market_structure_models import MarketStructureResult, StructureStatistics


class StructureService:
    """
    Service for market structure detection and analysis.
    
    Orchestrates structure detection by:
    - Loading historical candles from HistoryService
    - Loading trend analysis from TrendService
    - Loading indicator calculations from IndicatorService
    - Executing StructureEngine for structure analysis
    - Caching results for 60 seconds
    - Returning structured MarketStructureResult
    """
    
    # Class-level shared cache so results and hit/miss statistics persist
    # across per-request service instances, fulfilling the documented
    # "caching results for 60 seconds" design.
    _cache: dict = {}
    _cache_hits: int = 0
    _cache_misses: int = 0
    
    def __init__(self, db: Session):
        self.db = db
        self.history_service = HistoryService(db)
        self.trend_service = TrendService(db)
        self.indicator_service = IndicatorService(db)
        self.structure_engine = StructureEngine()
        
        self._cache_ttl = 60  # 60 second cache TTL
    
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

    def analyze_structure(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 200
    ) -> Optional[MarketStructureResult]:
        """
        Analyze market structure for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            limit: Number of candles to use for analysis
            
        Returns:
            MarketStructureResult with complete structure analysis or None if insufficient data
        """
        cache_key = f"{symbol}_{timeframe.value}"
        
        # Check cache
        if cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self._cache_ttl:
                self._bump_cache_hits()
                return cached_result
        
        self._bump_cache_misses()
        
        # Load historical candles
        candles = self.history_service.get_latest_candles(symbol, timeframe, limit)
        
        if len(candles) < 20:
            return None
        
        # Reverse candles to get chronological order (oldest first)
        candles_chronological = list(reversed(candles))
        
        # Load trend analysis
        trend_result = self.trend_service.calculate_trend(symbol, timeframe, limit)
        
        if trend_result is None:
            return None
        
        # Load indicators
        indicator_response = self.indicator_service.calculate_indicators(symbol, timeframe, limit)
        
        if indicator_response is None:
            return None
        
        # Analyze structure
        structure_result = self.structure_engine.analyze_structure(
            candles_chronological,
            trend_result,
            indicator_response
        )
        
        # Update cache
        self._cache[cache_key] = (structure_result, datetime.now(timezone.utc))
        
        return structure_result
    
    def get_statistics(self) -> StructureStatistics:
        """
        Get structure service statistics.
        
        Returns:
            StructureStatistics with cache and calculation metrics
        """
        engine_stats = self.structure_engine.get_statistics()
        
        # Count active zones from cache
        active_supply = 0
        active_demand = 0
        
        for cached_result, _ in self._cache.values():
            active_supply += len(cached_result.activeSupplyZones)
            active_demand += len(cached_result.activeDemandZones)
        
        return StructureStatistics(
            calculations=engine_stats['calculations'],
            average_execution_time=engine_stats['average_execution_time'],
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
            active_supply_zones=active_supply,
            active_demand_zones=active_demand,
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
