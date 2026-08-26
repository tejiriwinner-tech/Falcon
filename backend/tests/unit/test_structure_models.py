"""
Unit tests for Structure models
Tests market structure schema models.
"""
import unittest
from datetime import datetime, timezone
from app.schemas.market_structure_models import (
    StructureDirection, StructureEvent, ZoneType, SwingPoint,
    StructureZone, MarketStructureResult, StructureStatistics
)


class TestStructureDirection(unittest.TestCase):
    """Test cases for StructureDirection enum."""
    
    def test_structure_direction_values(self):
        """Test structure direction enum values."""
        self.assertEqual(StructureDirection.BULLISH.value, "BULLISH")
        self.assertEqual(StructureDirection.BEARISH.value, "BEARISH")
        self.assertEqual(StructureDirection.NEUTRAL.value, "NEUTRAL")
        self.assertEqual(StructureDirection.UNKNOWN.value, "UNKNOWN")


class TestStructureEvent(unittest.TestCase):
    """Test cases for StructureEvent enum."""
    
    def test_structure_event_values(self):
        """Test structure event enum values."""
        self.assertEqual(StructureEvent.NONE.value, "NONE")
        self.assertEqual(StructureEvent.BOS.value, "BOS")
        self.assertEqual(StructureEvent.CHOCH.value, "CHOCH")
        self.assertEqual(StructureEvent.RANGE_BREAKOUT.value, "RANGE_BREAKOUT")


class TestZoneType(unittest.TestCase):
    """Test cases for ZoneType enum."""
    
    def test_zone_type_values(self):
        """Test zone type enum values."""
        self.assertEqual(ZoneType.SUPPLY.value, "SUPPLY")
        self.assertEqual(ZoneType.DEMAND.value, "DEMAND")
        self.assertEqual(ZoneType.SUPPRESSION.value, "SUPPRESSION")
        self.assertEqual(ZoneType.ACCUMULATION.value, "ACCUMULATION")
        self.assertEqual(ZoneType.PREMIUM.value, "PREMIUM")
        self.assertEqual(ZoneType.DISCOUNT.value, "DISCOUNT")
        self.assertEqual(ZoneType.LIQUIDITY.value, "LIQUIDITY")


class TestSwingPoint(unittest.TestCase):
    """Test cases for SwingPoint model."""
    
    def test_create_swing_point(self):
        """Test creating a swing point."""
        swing = SwingPoint(
            price=2050.0,
            timestamp=datetime.now(timezone.utc),
            type="HIGH",
            strength=85.0,
            index=45
        )
        
        self.assertEqual(swing.price, 2050.0)
        self.assertEqual(swing.type, "HIGH")
        self.assertEqual(swing.strength, 85.0)
        self.assertEqual(swing.index, 45)
    
    def test_strength_validation(self):
        """Test strength validation (0-100)."""
        # Valid strengths
        swing1 = SwingPoint(
            price=2050.0,
            timestamp=datetime.now(timezone.utc),
            type="HIGH",
            strength=0.0,
            index=45
        )
        
        swing2 = SwingPoint(
            price=2050.0,
            timestamp=datetime.now(timezone.utc),
            type="HIGH",
            strength=100.0,
            index=45
        )
        
        self.assertEqual(swing1.strength, 0.0)
        self.assertEqual(swing2.strength, 100.0)


class TestStructureZone(unittest.TestCase):
    """Test cases for StructureZone model."""
    
    def test_create_structure_zone(self):
        """Test creating a structure zone."""
        zone = StructureZone(
            zoneType=ZoneType.SUPPLY,
            high=2060.0,
            low=2050.0,
            midpoint=2055.0,
            strength=75.0,
            touches=3,
            active=True
        )
        
        self.assertEqual(zone.zoneType, ZoneType.SUPPLY)
        self.assertEqual(zone.high, 2060.0)
        self.assertEqual(zone.low, 2050.0)
        self.assertEqual(zone.midpoint, 2055.0)
        self.assertEqual(zone.strength, 75.0)
        self.assertEqual(zone.touches, 3)
        self.assertTrue(zone.active)
    
    def test_strength_validation(self):
        """Test strength validation (0-100)."""
        zone = StructureZone(
            zoneType=ZoneType.DEMAND,
            high=2040.0,
            low=2030.0,
            midpoint=2035.0,
            strength=50.0,
            touches=0,
            active=True
        )
        
        self.assertEqual(zone.strength, 50.0)
    
    def test_touches_validation(self):
        """Test touches validation (non-negative)."""
        zone = StructureZone(
            zoneType=ZoneType.LIQUIDITY,
            high=2050.0,
            low=2045.0,
            midpoint=2047.5,
            strength=80.0,
            touches=0,
            active=True
        )
        
        self.assertEqual(zone.touches, 0)


class TestMarketStructureResult(unittest.TestCase):
    """Test cases for MarketStructureResult model."""
    
    def test_create_market_structure_result(self):
        """Test creating a market structure result."""
        result = MarketStructureResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=StructureDirection.BULLISH,
            currentEvent=StructureEvent.BOS,
            lastBos="Bullish BOS at 2050.0",
            lastChoch=None,
            swingHighs=[],
            swingLows=[],
            higherHigh=True,
            higherLow=True,
            lowerHigh=False,
            lowerLow=False,
            support=[2040.0, 2030.0],
            resistance=[2060.0, 2070.0],
            activeSupplyZones=[],
            activeDemandZones=[],
            premiumZone=None,
            discountZone=None,
            liquidityZones=[],
            marketPhase="TRENDING",
            confidence=78.5,
            analysis="Bullish structure with recent BOS"
        )
        
        self.assertEqual(result.symbol, "XAUUSD")
        self.assertEqual(result.timeframe, "H1")
        self.assertEqual(result.direction, StructureDirection.BULLISH)
        self.assertEqual(result.currentEvent, StructureEvent.BOS)
        self.assertTrue(result.higherHigh)
        self.assertTrue(result.higherLow)
        self.assertEqual(result.marketPhase, "TRENDING")
        self.assertEqual(result.confidence, 78.5)
    
    def test_confidence_validation(self):
        """Test confidence validation (0-100)."""
        result = MarketStructureResult(
            symbol="XAUUSD",
            timeframe="H1",
            direction=StructureDirection.NEUTRAL,
            currentEvent=StructureEvent.NONE,
            lastBos=None,
            lastChoch=None,
            swingHighs=[],
            swingLows=[],
            higherHigh=False,
            higherLow=False,
            lowerHigh=False,
            lowerLow=False,
            support=[],
            resistance=[],
            activeSupplyZones=[],
            activeDemandZones=[],
            premiumZone=None,
            discountZone=None,
            liquidityZones=[],
            marketPhase="RANGING",
            confidence=50.0,
            analysis="Test"
        )
        
        self.assertEqual(result.confidence, 50.0)


class TestStructureStatistics(unittest.TestCase):
    """Test cases for StructureStatistics model."""
    
    def test_create_structure_statistics(self):
        """Test creating structure statistics."""
        stats = StructureStatistics(
            calculations=150,
            average_execution_time=3.2,
            cache_hits=100,
            cache_misses=50,
            active_supply_zones=3,
            active_demand_zones=2,
            last_calculation=datetime.now(timezone.utc)
        )
        
        self.assertEqual(stats.calculations, 150)
        self.assertEqual(stats.average_execution_time, 3.2)
        self.assertEqual(stats.cache_hits, 100)
        self.assertEqual(stats.cache_misses, 50)
        self.assertEqual(stats.active_supply_zones, 3)
        self.assertEqual(stats.active_demand_zones, 2)
    
    def test_structure_statistics_defaults(self):
        """Test structure statistics default values."""
        stats = StructureStatistics()
        
        self.assertEqual(stats.calculations, 0)
        self.assertEqual(stats.average_execution_time, 0.0)
        self.assertEqual(stats.cache_hits, 0)
        self.assertEqual(stats.cache_misses, 0)
        self.assertEqual(stats.active_supply_zones, 0)
        self.assertEqual(stats.active_demand_zones, 0)
        self.assertIsNone(stats.last_calculation)


if __name__ == '__main__':
    unittest.main()
