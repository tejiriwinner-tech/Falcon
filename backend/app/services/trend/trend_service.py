"""
Falcon Trend Service
Service layer for trend detection orchestration.
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.market_candle import MarketCandle, Timeframe
from app.services.history.history_service import HistoryService
from app.services.indicators.indicator_service import IndicatorService
from app.services.trend.trend_engine import TrendEngine
from app.schemas.trend_models import TrendResult, TrendStatistics
from app.core.config import settings
from app.core.services.market_history_adapter import MarketHistoryAdapter


class TrendService:
    """
    Service for trend detection and analysis.
    
    Orchestrates trend detection by:
    - Loading historical candles from HistoryService
    - Loading indicator calculations from IndicatorService
    - Executing TrendEngine for trend analysis
    - Caching results for 1 minute
    - Returning structured TrendResult
    """
    
    # Class-level shared cache so results and hit/miss statistics persist
    # across per-request service instances, fulfilling the documented
    # "caching results for 1 minute" design.
    _cache: dict = {}
    _cache_hits: int = 0
    _cache_misses: int = 0
    
    def __init__(self, db: Session):
        self.db = db
        self.history_service = HistoryService(db)
        self.indicator_service = IndicatorService(db)
        self.trend_engine = TrendEngine()
        
        # Initialize market history adapter if configuration enables it
        self.market_history_adapter = None
        if settings.USE_PRICE_HISTORY_FOR_SIGNALS:
            self.market_history_adapter = MarketHistoryAdapter(db)
        
        self._cache_ttl = 60  # 1 minute cache TTL
    
    def _bump_cache_hits(self) -> None:
        """Increment the shared cache-hit counter.

        Handles both a plain class-level int (real app) and a property
        (trend API test monkey-patches counters into properties backed by
        class-local shared values).
        """
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

    def calculate_trend(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 200
    ) -> Optional[TrendResult]:
        """
        Calculate trend for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            limit: Number of candles to use for analysis
            
        Returns:
            TrendResult with complete trend analysis or None if insufficient data
        """
        cache_key = f"{symbol}_{timeframe.value}"
        
        # Check cache
        if cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self._cache_ttl:
                self._bump_cache_hits()
                return cached_result
        
        self._bump_cache_misses()
        
        # Load historical candles from appropriate data source
        if self.market_history_adapter:
            candles = self.market_history_adapter.get_latest_candles(symbol, timeframe, limit)
        else:
            candles = self.history_service.get_latest_candles(symbol, timeframe, limit)
        
        if len(candles) < 20:
            return None
        
        # Reverse candles to get chronological order (oldest first)
        candles_chronological = list(reversed(candles))
        
        # Load indicators
        indicator_response = self.indicator_service.calculate_indicators(symbol, timeframe, limit)
        
        if indicator_response is None:
            return None
        
        # Build indicators dictionary
        indicators = {
            'ema_20': indicator_response.ema_20,
            'ema_50': indicator_response.ema_50,
            'ema_100': indicator_response.ema_100,
            'ema_200': indicator_response.ema_200,
            'sma_20': indicator_response.sma_20,
            'sma_50': indicator_response.sma_50,
            'rsi_14': indicator_response.rsi_14,
            'atr_14': indicator_response.atr_14,
            'macd_line': indicator_response.macd_line,
            'macd_signal': indicator_response.macd_signal,
            'macd_histogram': indicator_response.macd_histogram,
            'bb_upper': indicator_response.bb_upper,
            'bb_middle': indicator_response.bb_middle,
            'bb_lower': indicator_response.bb_lower
        }
        
        # Calculate trend
        trend_result = self.trend_engine.calculate_trend(candles_chronological, indicators)
        
        # Update cache
        self._cache[cache_key] = (trend_result, datetime.now(timezone.utc))
        
        return trend_result
    
    def get_statistics(self) -> TrendStatistics:
        """
        Get trend service statistics.
        
        Returns:
            TrendStatistics with cache and calculation metrics
        """
        engine_stats = self.trend_engine.get_statistics()
        
        return TrendStatistics(
            calculations=engine_stats['calculations'],
            average_execution_time=engine_stats['average_execution_time'],
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
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
