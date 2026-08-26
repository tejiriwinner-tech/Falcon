"""
Falcon Market Data Repository
Data access layer for historical market candle data.
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from app.models.market_candle import MarketCandle, Timeframe


class MarketRepository:
    """Repository for market candle data operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_candle(self, candle: MarketCandle) -> MarketCandle:
        """
        Save a single market candle to the database.
        
        Args:
            candle: MarketCandle instance to save
            
        Returns:
            The saved candle with assigned ID
        """
        self.db.add(candle)
        self.db.commit()
        self.db.refresh(candle)
        return candle
    
    def save_many(self, candles: List[MarketCandle]) -> int:
        """
        Save multiple candles in a single transaction.
        
        Args:
            candles: List of MarketCandle instances to save
            
        Returns:
            Number of candles saved
        """
        self.db.add_all(candles)
        self.db.commit()
        return len(candles)
    
    def get_latest(
        self, 
        symbol: str, 
        timeframe: Timeframe,
        limit: int = 1
    ) -> List[MarketCandle]:
        """
        Get the most recent candles for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            limit: Maximum number of candles to return
            
        Returns:
            List of candles ordered by timestamp (most recent first)
        """
        return self.db.query(MarketCandle)\
            .filter(
                and_(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe.value
                )
            )\
            .order_by(desc(MarketCandle.timestamp))\
            .limit(limit)\
            .all()
    
    def get_history(
        self,
        symbol: str,
        timeframe: Timeframe,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[MarketCandle]:
        """
        Get historical candles for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            start_time: Start of time range (inclusive)
            end_time: End of time range (inclusive)
            limit: Maximum number of candles to return
            
        Returns:
            List of candles ordered by timestamp (oldest first)
        """
        query = self.db.query(MarketCandle)\
            .filter(
                and_(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe.value
                )
            )
        
        if start_time:
            query = query.filter(MarketCandle.timestamp >= start_time)
        
        if end_time:
            query = query.filter(MarketCandle.timestamp <= end_time)
        
        query = query.order_by(MarketCandle.timestamp)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def delete_old_history(
        self,
        symbol: str,
        timeframe: Timeframe,
        older_than: datetime
    ) -> int:
        """
        Delete historical candles older than a specified timestamp.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            older_than: Delete candles with timestamp older than this
            
        Returns:
            Number of candles deleted
        """
        deleted = self.db.query(MarketCandle)\
            .filter(
                and_(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe.value,
                    MarketCandle.timestamp < older_than
                )
            )\
            .delete()
        
        self.db.commit()
        return deleted
    
    def history_exists(
        self,
        symbol: str,
        timeframe: Timeframe,
        timestamp: datetime
    ) -> bool:
        """
        Check if a candle exists for the given symbol, timeframe, and timestamp.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            timestamp: Candle timestamp to check
            
        Returns:
            True if candle exists, False otherwise
        """
        return self.db.query(MarketCandle)\
            .filter(
                and_(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe.value,
                    MarketCandle.timestamp == timestamp
                )
            )\
            .first() is not None
    
    def get_candle_count(
        self,
        symbol: str,
        timeframe: Timeframe
    ) -> int:
        """
        Get the total count of candles for a symbol and timeframe.
        
        Args:
            symbol: Instrument symbol
            timeframe: Candle timeframe
            
        Returns:
            Number of candles in database
        """
        return self.db.query(MarketCandle)\
            .filter(
                and_(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe.value
                )
            )\
            .count()
