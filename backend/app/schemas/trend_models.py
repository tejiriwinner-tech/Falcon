"""
Falcon Trend Models
Schema models for trend detection results.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class TrendDirection(str, Enum):
    """Market trend direction classification."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    SIDEWAYS = "SIDEWAYS"
    UNKNOWN = "UNKNOWN"


class TrendStrength(str, Enum):
    """Trend strength classification."""
    VERY_WEAK = "VERY_WEAK"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"


class TrendResult(BaseModel):
    """
    Complete trend analysis result.
    
    Contains trend classification, strength, confidence, and detailed
    analysis components for market trend detection.
    
    Attributes:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        direction: Trend direction (BULLISH, BEARISH, SIDEWAYS, UNKNOWN)
        strength: Trend strength (VERY_WEAK to VERY_STRONG)
        confidence: Confidence score (0-100)
        ema_alignment: EMA alignment score (0-100)
        price_above_ema20: Whether price is above EMA20
        price_above_ema50: Whether price is above EMA50
        price_above_ema200: Whether price is above EMA200
        higher_highs: Number of higher highs detected
        higher_lows: Number of higher lows detected
        lower_highs: Number of lower highs detected
        lower_lows: Number of lower lows detected
        analysis: Detailed analysis text
        timestamp: Analysis timestamp
    """
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Candle timeframe")
    direction: TrendDirection = Field(..., description="Trend direction")
    strength: TrendStrength = Field(..., description="Trend strength")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence score (0-100)")
    ema_alignment: float = Field(..., ge=0.0, le=100.0, description="EMA alignment score (0-100)")
    price_above_ema20: bool = Field(..., description="Price above EMA20")
    price_above_ema50: bool = Field(..., description="Price above EMA50")
    price_above_ema200: bool = Field(..., description="Price above EMA200")
    higher_highs: int = Field(..., ge=0, description="Number of higher highs")
    higher_lows: int = Field(..., ge=0, description="Number of higher lows")
    lower_highs: int = Field(..., ge=0, description="Number of lower highs")
    lower_lows: int = Field(..., ge=0, description="Number of lower lows")
    analysis: str = Field(..., description="Detailed analysis text")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "direction": "BULLISH",
                "strength": "STRONG",
                "confidence": 82.5,
                "ema_alignment": 90.0,
                "price_above_ema20": True,
                "price_above_ema50": True,
                "price_above_ema200": True,
                "higher_highs": 5,
                "higher_lows": 4,
                "lower_highs": 1,
                "lower_lows": 2,
                "analysis": "Strong bullish trend with EMA alignment and higher highs structure",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class TrendStatistics(BaseModel):
    """
    Trend engine runtime statistics.
    
    Provides performance metrics for the trend detection engine.
    
    Attributes:
        calculations: Total number of trend calculations performed
        average_execution_time: Average execution time in milliseconds
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        last_calculation: Timestamp of last calculation
    """
    calculations: int = Field(0, description="Total calculations performed")
    average_execution_time: float = Field(0.0, description="Average execution time (ms)")
    cache_hits: int = Field(0, description="Number of cache hits")
    cache_misses: int = Field(0, description="Number of cache misses")
    last_calculation: Optional[datetime] = Field(None, description="Last calculation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calculations": 200,
                "average_execution_time": 1.5,
                "cache_hits": 150,
                "cache_misses": 50,
                "last_calculation": "2024-01-01T12:00:00Z"
            }
        }
