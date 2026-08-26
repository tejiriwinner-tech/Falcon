"""
Falcon Indicator Service
Service layer for technical indicator calculation orchestration.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.market_candle import MarketCandle, Timeframe
from app.services.history.history_service import HistoryService
from app.services.indicators.indicator_engine import IndicatorEngine
from app.schemas.indicator_models import IndicatorResponse, IndicatorStatistics
from app.core.config import settings
from app.core.services.market_history_adapter import MarketHistoryAdapter


class IndicatorService:
    """
    Service for calculating and managing technical indicators.
    
    Orchestrates indicator calculations by:
    - Loading historical candles from the history service
    - Calculating requested indicators using the engine
    - Caching calculations to avoid repeated work
    - Returning structured indicator results
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.history_service = HistoryService(db)
        self.indicator_engine = IndicatorEngine()
        
        # Initialize market history adapter if configuration enables it
        self.market_history_adapter = None
        if settings.USE_PRICE_HISTORY_FOR_SIGNALS:
            self.market_history_adapter = MarketHistoryAdapter(db)
        
        # Calculation cache (symbol+timeframe -> indicator results)
        self._calculation_cache: dict = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def calculate_indicators(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 200
    ) -> Optional[IndicatorResponse]:
        """
        Calculate all indicators for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            limit: Number of candles to use for calculation
            
        Returns:
            IndicatorResponse with all calculated indicators or None if insufficient data
        """
        cache_key = f"{symbol}_{timeframe.value}"
        
        # Check cache
        if cache_key in self._calculation_cache:
            cached_result, cache_time = self._calculation_cache[cache_key]
            # Cache is valid for 1 minute
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < 60:
                self._cache_hits += 1
                return cached_result
        
        self._cache_misses += 1
        
        # Load historical candles from appropriate data source
        if self.market_history_adapter:
            candles = self.market_history_adapter.get_latest_candles(symbol, timeframe, limit)
        else:
            candles = self.history_service.get_latest_candles(symbol, timeframe, limit)
        
        if len(candles) < 50:  # Minimum candles for meaningful indicators
            return None
        
        # Reverse candles to get chronological order (oldest first)
        candles_chronological = list(reversed(candles))
        
        # Calculate indicators
        latest_values = self.indicator_engine.get_latest_indicator_values(candles_chronological)
        
        if not latest_values:
            return None
        
        # Determine trend and signal
        trend, signal, strength = self._analyze_signals(latest_values, candles[-1].close)
        
        # Build response
        response = IndicatorResponse(
            symbol=symbol,
            timeframe=timeframe.value,
            ema_20=latest_values.get('ema_20'),
            ema_50=latest_values.get('ema_50'),
            ema_100=latest_values.get('ema_100'),
            ema_200=latest_values.get('ema_200'),
            sma_20=latest_values.get('sma_20'),
            sma_50=latest_values.get('sma_50'),
            rsi_14=latest_values.get('rsi_14'),
            atr_14=latest_values.get('atr_14'),
            macd_line=latest_values.get('macd_line'),
            macd_signal=latest_values.get('macd_signal'),
            macd_histogram=latest_values.get('macd_histogram'),
            bb_upper=latest_values.get('bb_upper'),
            bb_middle=latest_values.get('bb_middle'),
            bb_lower=latest_values.get('bb_lower'),
            trend=trend,
            signal=signal,
            strength=strength
        )
        
        # Update cache
        self._calculation_cache[cache_key] = (response, datetime.now(timezone.utc))
        
        return response
    
    def _analyze_signals(
        self,
        indicators: Dict[str, Optional[float]],
        current_price: float
    ) -> tuple[str, str, float]:
        """
        Analyze indicator values to determine trend, signal, and strength.
        
        Args:
            indicators: Dictionary of indicator values
            current_price: Current market price
            
        Returns:
            Tuple of (trend, signal, strength)
        """
        buy_signals = 0
        sell_signals = 0
        total_signals = 0
        
        # EMA trend analysis
        ema_20 = indicators.get('ema_20')
        ema_50 = indicators.get('ema_50')
        ema_200 = indicators.get('ema_200')
        
        if ema_20 and ema_50:
            if ema_20 > ema_50:
                buy_signals += 1
            else:
                sell_signals += 1
            total_signals += 1
        
        if ema_20 and ema_200:
            if ema_20 > ema_200:
                buy_signals += 1
            else:
                sell_signals += 1
            total_signals += 1
        
        # RSI analysis
        rsi = indicators.get('rsi_14')
        if rsi:
            if rsi < 30:
                buy_signals += 2  # Oversold
            elif rsi > 70:
                sell_signals += 2  # Overbought
            elif rsi < 40:
                buy_signals += 1
            elif rsi > 60:
                sell_signals += 1
            total_signals += 2
        
        # MACD analysis
        macd_line = indicators.get('macd_line')
        macd_signal = indicators.get('macd_signal')
        macd_histogram = indicators.get('macd_histogram')
        
        if macd_line and macd_signal:
            if macd_line > macd_signal:
                buy_signals += 1
            else:
                sell_signals += 1
            total_signals += 1
        
        if macd_histogram:
            if macd_histogram > 0:
                buy_signals += 1
            else:
                sell_signals += 1
            total_signals += 1
        
        # Bollinger Bands analysis
        bb_upper = indicators.get('bb_upper')
        bb_lower = indicators.get('bb_lower')
        
        if bb_upper and bb_lower and current_price:
            if current_price < bb_lower:
                buy_signals += 2  # Price below lower band
            elif current_price > bb_upper:
                sell_signals += 2  # Price above upper band
            total_signals += 2
        
        # Determine trend
        if ema_20 and ema_50 and ema_200:
            if ema_20 > ema_50 > ema_200:
                trend = "BULLISH"
            elif ema_20 < ema_50 < ema_200:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
        else:
            trend = "NEUTRAL"
        
        # Determine signal and strength
        if total_signals == 0:
            signal = "NEUTRAL"
            strength = 0.0
        else:
            signal_ratio = (buy_signals - sell_signals) / total_signals
            
            if signal_ratio > 0.3:
                signal = "BUY"
            elif signal_ratio < -0.3:
                signal = "SELL"
            else:
                signal = "NEUTRAL"
            
            strength = abs(signal_ratio) * 100
            strength = min(max(strength, 0.0), 100.0)
        
        return trend, signal, strength
    
    def get_statistics(self) -> IndicatorStatistics:
        """
        Get indicator service statistics.
        
        Returns:
            IndicatorStatistics with cache and calculation metrics
        """
        engine_stats = self.indicator_engine.get_statistics()
        
        return IndicatorStatistics(
            calculation_count=engine_stats['calculation_count'],
            total_execution_time=engine_stats['total_execution_time'],
            average_execution_time=engine_stats['average_execution_time'],
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses
        )
    
    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear the calculation cache.
        
        Args:
            symbol: If provided, only clear cache for this symbol
        """
        if symbol:
            keys_to_delete = [k for k in self._calculation_cache.keys() if k.startswith(symbol)]
            for key in keys_to_delete:
                del self._calculation_cache[key]
        else:
            self._calculation_cache.clear()
            self._cache_hits = 0
            self._cache_misses = 0
