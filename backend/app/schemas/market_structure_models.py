"""
Falcon Market Structure Models
Schema models for institutional market structure analysis.
"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field


class StructureDirection(str, Enum):
    """Market structure direction classification."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class StructureEvent(str, Enum):
    """Market structure event types."""
    NONE = "NONE"
    BOS = "BOS"  # Break of Structure
    CHOCH = "CHOCH"  # Change of Character
    RANGE_BREAKOUT = "RANGE_BREAKOUT"


class ZoneType(str, Enum):
    """Market structure zone types."""
    SUPPLY = "SUPPLY"
    DEMAND = "DEMAND"
    SUPPRESSION = "SUPPRESSION"
    ACCUMULATION = "ACCUMULATION"
    PREMIUM = "PREMIUM"
    DISCOUNT = "DISCOUNT"
    LIQUIDITY = "LIQUIDITY"


class SwingPoint(BaseModel):
    """
    Swing point in market structure.
    
    Represents a pivot high or low in price action.
    
    Attributes:
        price: Swing point price
        timestamp: Swing point timestamp
        type: Swing point type (HIGH or LOW)
        strength: Swing point strength (0-100)
        index: Index in candle array
    """
    price: float = Field(..., description="Swing point price")
    timestamp: datetime = Field(..., description="Swing point timestamp")
    type: str = Field(..., description="Swing point type (HIGH or LOW)")
    strength: float = Field(..., ge=0.0, le=100.0, description="Swing point strength (0-100)")
    index: int = Field(..., ge=0, description="Index in candle array")
    
    class Config:
        json_schema_extra = {
            "example": {
                "price": 2050.0,
                "timestamp": "2024-01-01T12:00:00Z",
                "type": "HIGH",
                "strength": 85.0,
                "index": 45
            }
        }


class StructureZone(BaseModel):
    """
    Market structure zone.
    
    Represents a significant price zone (supply, demand, liquidity, etc.).
    
    Attributes:
        zoneType: Zone type
        high: Zone high price
        low: Zone low price
        midpoint: Zone midpoint price
        strength: Zone strength (0-100)
        touches: Number of times price touched this zone
        active: Whether zone is currently active
        createdAt: Zone creation timestamp
    """
    zoneType: ZoneType = Field(..., description="Zone type")
    high: float = Field(..., description="Zone high price")
    low: float = Field(..., description="Zone low price")
    midpoint: float = Field(..., description="Zone midpoint price")
    strength: float = Field(..., ge=0.0, le=100.0, description="Zone strength (0-100)")
    touches: int = Field(..., ge=0, description="Number of touches")
    active: bool = Field(..., description="Whether zone is active")
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "zoneType": "SUPPLY",
                "high": 2060.0,
                "low": 2050.0,
                "midpoint": 2055.0,
                "strength": 75.0,
                "touches": 3,
                "active": True,
                "createdAt": "2024-01-01T12:00:00Z"
            }
        }


class MarketStructureResult(BaseModel):
    """
    Complete market structure analysis result.
    
    Contains comprehensive market structure analysis including swing points,
    structural events, zones, and market phase.
    
    Attributes:
        symbol: Instrument symbol
        timeframe: Candle timeframe
        direction: Structure direction
        currentEvent: Current structural event
        lastBos: Last break of structure
        lastChoch: Last change of character
        swingHighs: List of swing highs
        swingLows: List of swing lows
        higherHigh: Whether current high is higher than previous
        higherLow: Whether current low is higher than previous
        lowerHigh: Whether current high is lower than previous
        lowerLow: Whether current low is lower than previous
        support: Support levels
        resistance: Resistance levels
        activeSupplyZones: Active supply zones
        activeDemandZones: Active demand zones
        premiumZone: Premium zone info
        discountZone: Discount zone info
        liquidityZones: Liquidity zones
        marketPhase: Current market phase
        confidence: Analysis confidence (0-100)
        analysis: Detailed analysis text
        timestamp: Analysis timestamp
    """
    symbol: str = Field(..., description="Instrument symbol")
    timeframe: str = Field(..., description="Candle timeframe")
    direction: StructureDirection = Field(..., description="Structure direction")
    currentEvent: StructureEvent = Field(..., description="Current structural event")
    lastBos: Optional[str] = Field(None, description="Last break of structure")
    lastChoch: Optional[str] = Field(None, description="Last change of character")
    swingHighs: List[SwingPoint] = Field(default_factory=list, description="Swing highs")
    swingLows: List[SwingPoint] = Field(default_factory=list, description="Swing lows")
    higherHigh: bool = Field(..., description="Higher high detected")
    higherLow: bool = Field(..., description="Higher low detected")
    lowerHigh: bool = Field(..., description="Lower high detected")
    lowerLow: bool = Field(..., description="Lower low detected")
    support: List[float] = Field(default_factory=list, description="Support levels")
    resistance: List[float] = Field(default_factory=list, description="Resistance levels")
    activeSupplyZones: List[StructureZone] = Field(default_factory=list, description="Active supply zones")
    activeDemandZones: List[StructureZone] = Field(default_factory=list, description="Active demand zones")
    premiumZone: Optional[dict] = Field(None, description="Premium zone info")
    discountZone: Optional[dict] = Field(None, description="Discount zone info")
    liquidityZones: List[StructureZone] = Field(default_factory=list, description="Liquidity zones")
    marketPhase: str = Field(..., description="Market phase")
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence score (0-100)")
    analysis: str = Field(..., description="Detailed analysis text")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Analysis timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "direction": "BULLISH",
                "currentEvent": "BOS",
                "lastBos": "Bullish BOS at 2050.0",
                "lastChoch": None,
                "swingHighs": [],
                "swingLows": [],
                "higherHigh": True,
                "higherLow": True,
                "lowerHigh": False,
                "lowerLow": False,
                "support": [2040.0, 2030.0],
                "resistance": [2060.0, 2070.0],
                "activeSupplyZones": [],
                "activeDemandZones": [],
                "premiumZone": None,
                "discountZone": None,
                "liquidityZones": [],
                "marketPhase": "TRENDING",
                "confidence": 78.5,
                "analysis": "Bullish structure with recent BOS",
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }


class StructureStatistics(BaseModel):
    """
    Market structure engine runtime statistics.
    
    Provides performance metrics for the structure detection engine.
    
    Attributes:
        calculations: Total number of structure calculations performed
        average_execution_time: Average execution time in milliseconds
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses
        active_supply_zones: Number of active supply zones
        active_demand_zones: Number of active demand zones
        last_calculation: Timestamp of last calculation
    """
    calculations: int = Field(0, description="Total calculations performed")
    average_execution_time: float = Field(0.0, description="Average execution time (ms)")
    cache_hits: int = Field(0, description="Number of cache hits")
    cache_misses: int = Field(0, description="Number of cache misses")
    active_supply_zones: int = Field(0, description="Number of active supply zones")
    active_demand_zones: int = Field(0, description="Number of active demand zones")
    last_calculation: Optional[datetime] = Field(None, description="Last calculation timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calculations": 150,
                "average_execution_time": 3.2,
                "cache_hits": 100,
                "cache_misses": 50,
                "active_supply_zones": 3,
                "active_demand_zones": 2,
                "last_calculation": "2024-01-01T12:00:00Z"
            }
        }
