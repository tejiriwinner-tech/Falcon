"""
Falcon History Service
Service layer for historical market candle management and caching.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.market_candle import MarketCandle, Timeframe
from app.repositories.market_repository import MarketRepository


class HistoryService:
    """
    Service for managing historical market candle data.
    
    Provides caching, duplicate prevention, and automatic data cleanup
    for historical market data storage.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = MarketRepository(db)
        
        # In-memory cache for recent candles (symbol+timeframe -> list of candles)
        self._cache: dict = {}
        self._cache_max_size = 1000  # Maximum candles per symbol+timeframe
        self._cache_ttl = 300  # Cache TTL in seconds (5 minutes)
        self._cache_timestamps: dict = {}
    
    def save_candle(
        self,
        symbol: str,
        timeframe: Timeframe,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float = 0.0,
        provider: str = "unknown",
        timestamp: Optional[datetime] = None
    ) -> Optional[MarketCandle]:
        """
        Save a single candle with duplicate prevention.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            open_price: Opening price
            high: Highest price
            low: Lowest price
            close: Closing price
            volume: Trading volume
            provider: Data provider name
            timestamp: Candle timestamp (defaults to current time)
            
        Returns:
            Saved candle or None if duplicate
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        
        # Check for duplicate
        if self.repository.history_exists(symbol, timeframe, timestamp):
            return None
        
        candle = MarketCandle(
            symbol=symbol,
            timeframe=timeframe.value,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
            provider=provider,
            timestamp=timestamp
        )
        
        saved = self.repository.save_candle(candle)
        
        # Update cache
        self._update_cache(symbol, timeframe, saved)
        
        return saved
    
    def save_many_candles(
        self,
        candles: List[dict]
    ) -> int:
        """
        Save multiple candles with duplicate prevention.
        
        Args:
            candles: List of candle dictionaries with keys:
                symbol, timeframe, open, high, low, close, volume, provider, timestamp
                
        Returns:
            Number of candles actually saved (excluding duplicates)
        """
        saved_count = 0
        for candle_data in candles:
            candle = MarketCandle(
                symbol=candle_data['symbol'],
                timeframe=candle_data['timeframe'],
                open=candle_data['open'],
                high=candle_data['high'],
                low=candle_data['low'],
                close=candle_data['close'],
                volume=candle_data.get('volume', 0.0),
                provider=candle_data.get('provider', 'unknown'),
                timestamp=candle_data.get('timestamp', datetime.now(timezone.utc))
            )
            
            if not self.repository.history_exists(
                candle.symbol,
                Timeframe(candle.timeframe),
                candle.timestamp
            ):
                self.db.add(candle)
                saved_count += 1
        
        self.db.commit()
        return saved_count
    
    def get_latest_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 100
    ) -> List[MarketCandle]:
        """
        Get the most recent candles with caching.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            limit: Maximum number of candles to return
            
        Returns:
            List of candles ordered by timestamp (most recent first)
        """
        cache_key = f"{symbol}_{timeframe.value}"
        
        # Check cache
        if cache_key in self._cache:
            cached_candles, cache_time = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self._cache_ttl:
                return cached_candles[:limit]
        
        # Fetch from database
        candles = self.repository.get_latest(symbol, timeframe, limit)
        
        # Update cache
        self._cache[cache_key] = (candles, datetime.now(timezone.utc))
        
        return candles

    def get_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        limit: int = 100
    ) -> List[MarketCandle]:
        """Alias for get_latest_candles."""
        return self.get_latest_candles(symbol, timeframe, limit)
    
    def get_historical_candles(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[MarketCandle]:
        """
        Get historical candles for a time range.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of candles to return
            
        Returns:
            List of candles ordered by timestamp (oldest first)
        """
        return self.repository.get_history(symbol, timeframe, start_time, end_time, limit)
    
    def clean_old_data(
        self,
        symbol: str,
        timeframe: Timeframe,
        days_to_keep: int = 90
    ) -> int:
        """
        Automatically clean old historical data.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            days_to_keep: Number of days of history to keep
            
        Returns:
            Number of candles deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        deleted = self.repository.delete_old_history(symbol, timeframe, cutoff_date)
        
        # Clear cache for this symbol+timeframe
        cache_key = f"{symbol}_{timeframe.value}"
        if cache_key in self._cache:
            del self._cache[cache_key]
        
        return deleted
    
    def _update_cache(
        self,
        symbol: str,
        timeframe: Timeframe,
        candle: MarketCandle
    ) -> None:
        """Update the in-memory cache with a new candle."""
        cache_key = f"{symbol}_{timeframe.value}"
        
        if cache_key not in self._cache:
            self._cache[cache_key] = ([candle], datetime.now(timezone.utc))
        else:
            candles, _ = self._cache[cache_key]
            candles.insert(0, candle)  # Add to front (most recent)
            
            # Enforce cache size limit
            if len(candles) > self._cache_max_size:
                candles.pop()
            
            self._cache[cache_key] = (candles, datetime.now(timezone.utc))
    
    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear the in-memory cache.
        
        Args:
            symbol: If provided, only clear cache for this symbol
        """
        if symbol:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(symbol)]
            for key in keys_to_delete:
                del self._cache[key]
        else:
            self._cache.clear()
    
    def get_cache_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_cached = sum(len(candles) for candles, _ in self._cache.values())
        return {
            "cached_symbols": len(self._cache),
            "total_cached_candles": total_cached,
            "cache_max_size_per_symbol": self._cache_max_size,
            "cache_ttl_seconds": self._cache_ttl
        }
