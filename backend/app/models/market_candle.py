"""
Falcon Market Data Models
Historical market candle data storage models.
"""
from enum import Enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.orm import declarative_base
from app.core.config.database import Base


class Timeframe(str, Enum):
    """Supported timeframes for historical candle data."""
    M1 = "M1"   # 1 minute
    M5 = "M5"   # 5 minutes
    M15 = "M15" # 15 minutes
    M30 = "M30" # 30 minutes
    H1 = "H1"   # 1 hour
    H4 = "H4"   # 4 hours
    D1 = "D1"   # 1 day


class MarketCandle(Base):
    """
    Historical market candle data model.
    
    Stores OHLCV (Open, High, Low, Close, Volume) data for various instruments
    across multiple timeframes. Used for technical indicator calculations and
    historical analysis.
    
    Attributes:
        id: Primary key
        symbol: Instrument symbol (e.g., "XAUUSD", "GBPUSD")
        timeframe: Timeframe of the candle (M1, M5, M15, M30, H1, H4, D1)
        open: Opening price
        high: Highest price
        low: Lowest price
        close: Closing price
        volume: Trading volume
        provider: Data provider name
        timestamp: Candle timestamp (start of the period)
        created_at: Record creation timestamp
    """
    __tablename__ = "market_candles"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False, default=0.0)
    provider = Column(String(50), nullable=False, default="unknown")
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Composite index for efficient symbol+timeframe+timestamp queries
    __table_args__ = (
        Index('idx_symbol_timeframe_timestamp', 'symbol', 'timeframe', 'timestamp'),
        Index('idx_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<MarketCandle {self.symbol} {self.timeframe} {self.timestamp} close={self.close}>"
