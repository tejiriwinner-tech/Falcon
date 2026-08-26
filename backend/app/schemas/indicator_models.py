"""
Falcon Indicator Models
Schema models for technical indicator results.
"""
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class IndicatorResult(BaseModel):
    """
    Individual technical indicator result.
    
    Represents a single calculated indicator value with metadata
    for signal interpretation and strength assessment.
    
    Attributes:
        name: Indicator name (e.g., "RSI_14", "EMA_20")
        value: Calculated indicator value
        signal: Trading signal (BUY, SELL, NEUTRAL)
        strength: Signal strength (0-100)
        timestamp: Calculation timestamp
    """
    name: str = Field(..., description="Indicator name")
    value: Optional[float] = Field(None, description="Calculated indicator value")
    signal: str = Field("NEUTRAL", description="Trading signal: BUY, SELL, or NEUTRAL")
    strength: float = Field(0.0, ge=0.0, le=100.0, description="Signal strength (0-100)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Calculation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "RSI_14",
                "value": 65.5,
                "signal": "NEUTRAL",
                "strength": 35.0,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class IndicatorResponse(BaseModel):
    """
    Complete indicator analysis response.
    
    Contains all calculated indicators for a symbol and timeframe,
    along with trend analysis and metadata.
    
    Attributes:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        timestamp: Analysis timestamp
        ema: EMA values (20, 50, 100, 200)
        sma: SMA values (20, 50)
        rsi: RSI value (14)
        atr: ATR value (14)
        macd: MACD components (line, signal, histogram)
        bollinger_bands: Bollinger Bands (upper, middle, lower)
        trend: Overall trend direction
        signal: Overall trading signal
        strength: Overall signal strength
    """
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Candle timeframe")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Analysis timestamp")
    
    # EMA values
    ema_20: Optional[float] = Field(None, description="20-period EMA")
    ema_50: Optional[float] = Field(None, description="50-period EMA")
    ema_100: Optional[float] = Field(None, description="100-period EMA")
    ema_200: Optional[float] = Field(None, description="200-period EMA")
    
    # SMA values
    sma_20: Optional[float] = Field(None, description="20-period SMA")
    sma_50: Optional[float] = Field(None, description="50-period SMA")
    
    # RSI
    rsi_14: Optional[float] = Field(None, description="14-period RSI")
    
    # ATR
    atr_14: Optional[float] = Field(None, description="14-period ATR")
    
    # MACD
    macd_line: Optional[float] = Field(None, description="MACD line")
    macd_signal: Optional[float] = Field(None, description="MACD signal line")
    macd_histogram: Optional[float] = Field(None, description="MACD histogram")
    
    # Bollinger Bands
    bb_upper: Optional[float] = Field(None, description="Bollinger Bands upper")
    bb_middle: Optional[float] = Field(None, description="Bollinger Bands middle (SMA)")
    bb_lower: Optional[float] = Field(None, description="Bollinger Bands lower")
    
    # Analysis
    trend: str = Field("NEUTRAL", description="Overall trend: BULLISH, BEARISH, or NEUTRAL")
    signal: str = Field("NEUTRAL", description="Overall signal: BUY, SELL, or NEUTRAL")
    strength: float = Field(0.0, ge=0.0, le=100.0, description="Overall signal strength (0-100)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "timestamp": "2024-01-01T12:00:00Z",
                "ema_20": 2040.5,
                "ema_50": 2035.2,
                "ema_100": 2030.8,
                "ema_200": 2025.1,
                "sma_20": 2038.9,
                "sma_50": 2034.5,
                "rsi_14": 58.3,
                "atr_14": 15.2,
                "macd_line": 5.3,
                "macd_signal": 4.8,
                "macd_histogram": 0.5,
                "bb_upper": 2055.0,
                "bb_middle": 2040.0,
                "bb_lower": 2025.0,
                "trend": "BULLISH",
                "signal": "BUY",
                "strength": 65.0
            }
        }


class IndicatorStatistics(BaseModel):
    """
    Indicator engine runtime statistics.
    
    Provides performance metrics for the indicator calculation engine.
    
    Attributes:
        calculation_count: Total number of indicator calculations performed
        total_execution_time: Total execution time in seconds
        average_execution_time: Average execution time per calculation
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
    """
    calculation_count: int = Field(0, description="Total calculations performed")
    total_execution_time: float = Field(0.0, description="Total execution time (seconds)")
    average_execution_time: float = Field(0.0, description="Average execution time (seconds)")
    cache_hits: int = Field(0, description="Number of cache hits")
    cache_misses: int = Field(0, description="Number of cache misses")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calculation_count": 150,
                "total_execution_time": 2.5,
                "average_execution_time": 0.0167,
                "cache_hits": 80,
                "cache_misses": 70
            }
        }
