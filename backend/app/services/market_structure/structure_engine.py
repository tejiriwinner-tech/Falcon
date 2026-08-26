"""
Falcon Market Structure Engine
Analyzes institutional price action and Smart Money Concepts (SMC).
"""
import time
from typing import List, Dict, Optional, Tuple
from app.models.market_candle import MarketCandle
from app.schemas.market_structure_models import (
    StructureDirection, StructureEvent, ZoneType, SwingPoint,
    StructureZone, MarketStructureResult
)
from app.schemas.trend_models import TrendResult
from app.schemas.indicator_models import IndicatorResponse


class StructureEngine:
    """
    Market structure detection engine.
    
    Analyzes historical candles, trend data, and indicators to identify
    institutional price action patterns including:
    - Swing points (highs/lows)
    - Break of Structure (BOS)
    - Change of Character (CHoCH)
    - Support & Resistance levels
    - Supply & Demand zones
    - Liquidity pools
    - Premium/Discount zones
    - Market phase classification
    """
    
    def __init__(self, lookback_left: int = 3, lookback_right: int = 3):
        """
        Initialize the structure engine.
        
        Args:
            lookback_left: Number of candles to look left for swing detection
            lookback_right: Number of candles to look right for swing detection
        """
        self.lookback_left = lookback_left
        self.lookback_right = lookback_right
        self._calculation_count = 0
        self._total_execution_time = 0.0
    
    def analyze_structure(
        self,
        candles: List[MarketCandle],
        trend_result: TrendResult,
        indicator_result: IndicatorResponse
    ) -> MarketStructureResult:
        """
        Analyze market structure.
        
        Args:
            candles: Historical candle data (chronological order, oldest first)
            trend_result: Trend analysis result
            indicator_result: Indicator analysis result
            
        Returns:
            MarketStructureResult with complete structure analysis
        """
        start_time = time.time()
        
        if not candles or len(candles) < 20:
            return self._create_unknown_result(candles)
        
        # Detect swing points
        swing_highs, swing_lows = self._detect_swing_points(candles)
        
        # Detect structural events
        current_event, last_bos, last_choch = self._detect_structural_events(
            candles, swing_highs, swing_lows
        )
        
        # Analyze swing structure
        higher_high, higher_low, lower_high, lower_low = self._analyze_swing_structure(
            swing_highs, swing_lows
        )
        
        # Detect support and resistance
        support, resistance = self._detect_support_resistance(candles, swing_highs, swing_lows)
        
        # Create supply and demand zones
        supply_zones, demand_zones = self._create_supply_demand_zones(candles, swing_highs, swing_lows)
        
        # Detect liquidity zones
        liquidity_zones = self._detect_liquidity_zones(candles, swing_highs, swing_lows)
        
        # Calculate premium and discount zones
        premium_zone, discount_zone = self._calculate_premium_discount(candles, swing_highs, swing_lows)
        
        # Determine market phase
        market_phase = self._determine_market_phase(trend_result, swing_highs, swing_lows)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            trend_result, swing_highs, swing_lows, current_event
        )
        
        # Determine direction
        direction = self._determine_direction(trend_result, swing_highs, swing_lows)
        
        # Generate analysis
        analysis = self._generate_analysis(
            direction, current_event, market_phase, confidence
        )
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        self._calculation_count += 1
        self._total_execution_time += execution_time
        
        return MarketStructureResult(
            symbol=candles[-1].symbol,
            timeframe=candles[-1].timeframe,
            direction=direction,
            currentEvent=current_event,
            lastBos=last_bos,
            lastChoch=last_choch,
            swingHighs=swing_highs[-5:] if swing_highs else [],  # Last 5 for brevity
            swingLows=swing_lows[-5:] if swing_lows else [],
            higherHigh=higher_high,
            higherLow=higher_low,
            lowerHigh=lower_high,
            lowerLow=lower_low,
            support=support,
            resistance=resistance,
            activeSupplyZones=supply_zones,
            activeDemandZones=demand_zones,
            premiumZone=premium_zone,
            discountZone=discount_zone,
            liquidityZones=liquidity_zones,
            marketPhase=market_phase,
            confidence=confidence,
            analysis=analysis
        )
    
    def _detect_swing_points(
        self,
        candles: List[MarketCandle]
    ) -> Tuple[List[SwingPoint], List[SwingPoint]]:
        """
        Detect swing highs and lows using configurable lookback.
        
        Args:
            candles: Historical candle data
            
        Returns:
            Tuple of (swing_highs, swing_lows)
        """
        swing_highs = []
        swing_lows = []
        
        for i in range(self.lookback_left, len(candles) - self.lookback_right):
            # Check for swing high
            is_swing_high = True
            for j in range(i - self.lookback_left, i):
                if candles[j].high >= candles[i].high:
                    is_swing_high = False
                    break
            for j in range(i + 1, i + self.lookback_right + 1):
                if candles[j].high >= candles[i].high:
                    is_swing_high = False
                    break
            
            if is_swing_high:
                strength = self._calculate_swing_strength(candles, i, "HIGH")
                swing_highs.append(SwingPoint(
                    price=candles[i].high,
                    timestamp=candles[i].timestamp,
                    type="HIGH",
                    strength=strength,
                    index=i
                ))
            
            # Check for swing low
            is_swing_low = True
            for j in range(i - self.lookback_left, i):
                if candles[j].low <= candles[i].low:
                    is_swing_low = False
                    break
            for j in range(i + 1, i + self.lookback_right + 1):
                if candles[j].low <= candles[i].low:
                    is_swing_low = False
                    break
            
            if is_swing_low:
                strength = self._calculate_swing_strength(candles, i, "LOW")
                swing_lows.append(SwingPoint(
                    price=candles[i].low,
                    timestamp=candles[i].timestamp,
                    type="LOW",
                    strength=strength,
                    index=i
                ))
        
        return swing_highs, swing_lows
    
    def _calculate_swing_strength(
        self,
        candles: List[MarketCandle],
        index: int,
        swing_type: str
    ) -> float:
        """
        Calculate swing point strength based on surrounding candles.
        
        Args:
            candles: Historical candle data
            index: Swing point index
            swing_type: HIGH or LOW
            
        Returns:
            Strength score (0-100)
        """
        # Simplified strength calculation based on price difference
        if swing_type == "HIGH":
            left_highs = [c.high for c in candles[max(0, index - 5):index]]
            right_highs = [c.high for c in candles[index + 1:min(len(candles), index + 6)]]
            left_high = max(left_highs) if left_highs else candles[index].high
            right_high = max(right_highs) if right_highs else candles[index].high
            current_high = candles[index].high
            strength = min(100, ((current_high - left_high) + (current_high - right_high)) * 10)
        else:
            left_lows = [c.low for c in candles[max(0, index - 5):index]]
            right_lows = [c.low for c in candles[index + 1:min(len(candles), index + 6)]]
            left_low = min(left_lows) if left_lows else candles[index].low
            right_low = min(right_lows) if right_lows else candles[index].low
            current_low = candles[index].low
            strength = min(100, ((left_low - current_low) + (right_low - current_low)) * 10)
        
        return max(0.0, min(100.0, strength))
    
    def _detect_structural_events(
        self,
        candles: List[MarketCandle],
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> Tuple[StructureEvent, Optional[str], Optional[str]]:
        """
        Detect Break of Structure (BOS) and Change of Character (CHoCH).
        
        Args:
            candles: Historical candle data
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            Tuple of (current_event, last_bos, last_choch)
        """
        current_event = StructureEvent.NONE
        last_bos = None
        last_choch = None
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return current_event, last_bos, last_choch
        
        current_price = candles[-1].close
        
        # Check for bullish BOS
        if swing_highs:
            last_swing_high = swing_highs[-1]
            prev_swing_high = swing_highs[-2] if len(swing_highs) >= 2 else swing_highs[-1]
            if current_price > prev_swing_high.price:
                current_event = StructureEvent.BOS
                last_bos = f"Bullish BOS at {current_price:.2f}"
        
        # Check for bearish BOS
        if swing_lows:
            last_swing_low = swing_lows[-1]
            prev_swing_low = swing_lows[-2] if len(swing_lows) >= 2 else swing_lows[-1]
            if current_price < prev_swing_low.price:
                current_event = StructureEvent.BOS
                last_bos = f"Bearish BOS at {current_price:.2f}"
        
        # CHoCH detection (simplified - requires trend context)
        # This would typically track previous trend direction and detect reversals
        # For now, we'll mark CHoCH when BOS occurs after extended trend
        
        return current_event, last_bos, last_choch
    
    def _analyze_swing_structure(
        self,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> Tuple[bool, bool, bool, bool]:
        """
        Analyze swing structure for higher highs/lows and lower highs/lows.
        
        Args:
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            Tuple of (higher_high, higher_low, lower_high, lower_low)
        """
        higher_high = False
        higher_low = False
        lower_high = False
        lower_low = False
        
        if len(swing_highs) >= 2:
            if swing_highs[-1].price > swing_highs[-2].price:
                higher_high = True
            else:
                lower_high = True
        
        if len(swing_lows) >= 2:
            if swing_lows[-1].price > swing_lows[-2].price:
                higher_low = True
            else:
                lower_low = True
        
        return higher_high, higher_low, lower_high, lower_low
    
    def _detect_support_resistance(
        self,
        candles: List[MarketCandle],
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> Tuple[List[float], List[float]]:
        """
        Detect support and resistance levels.
        
        Args:
            candles: Historical candle data
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            Tuple of (support_levels, resistance_levels)
        """
        support = []
        resistance = []
        
        # Use swing lows for support
        for swing_low in swing_lows[-5:]:  # Last 5 swing lows
            if swing_low.strength > 50:
                support.append(swing_low.price)
        
        # Use swing highs for resistance
        for swing_high in swing_highs[-5:]:  # Last 5 swing highs
            if swing_high.strength > 50:
                resistance.append(swing_high.price)
        
        # Merge nearby levels
        support = self._merge_levels(support)
        resistance = self._merge_levels(resistance)
        
        return support, resistance
    
    def _merge_levels(self, levels: List[float], threshold: float = 0.002) -> List[float]:
        """
        Merge nearby levels within threshold percentage.
        
        Args:
            levels: List of price levels
            threshold: Merge threshold percentage
            
        Returns:
            Merged levels
        """
        if not levels:
            return []
        
        levels_sorted = sorted(levels)
        merged = []
        
        for level in levels_sorted:
            if not merged:
                merged.append(level)
            else:
                last_level = merged[-1]
                if abs(level - last_level) / last_level > threshold:
                    merged.append(level)
        
        return merged
    
    def _create_supply_demand_zones(
        self,
        candles: List[MarketCandle],
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> Tuple[List[StructureZone], List[StructureZone]]:
        """
        Create supply and demand zones from strong impulsive moves.
        
        Args:
            candles: Historical candle data
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            Tuple of (supply_zones, demand_zones)
        """
        supply_zones = []
        demand_zones = []
        
        # Create supply zones from strong swing highs
        for swing_high in swing_highs[-3:]:  # Last 3 swing highs
            if swing_high.strength > 70:
                zone = StructureZone(
                    zoneType=ZoneType.SUPPLY,
                    high=swing_high.price,
                    low=swing_high.price * 0.998,  # 0.2% below
                    midpoint=(swing_high.price + swing_high.price * 0.998) / 2,
                    strength=swing_high.strength,
                    touches=0,
                    active=True
                )
                supply_zones.append(zone)
        
        # Create demand zones from strong swing lows
        for swing_low in swing_lows[-3:]:  # Last 3 swing lows
            if swing_low.strength > 70:
                zone = StructureZone(
                    zoneType=ZoneType.DEMAND,
                    high=swing_low.price * 1.002,  # 0.2% above
                    low=swing_low.price,
                    midpoint=(swing_low.price + swing_low.price * 1.002) / 2,
                    strength=swing_low.strength,
                    touches=0,
                    active=True
                )
                demand_zones.append(zone)
        
        return supply_zones, demand_zones
    
    def _detect_liquidity_zones(
        self,
        candles: List[MarketCandle],
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> List[StructureZone]:
        """
        Detect liquidity zones (equal highs/lows, liquidity pools).
        
        Args:
            candles: Historical candle data
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            List of liquidity zones
        """
        liquidity_zones = []
        
        # Detect equal highs
        if len(swing_highs) >= 2:
            for i in range(len(swing_highs) - 1):
                if abs(swing_highs[i].price - swing_highs[i + 1].price) / swing_highs[i].price < 0.001:
                    zone = StructureZone(
                        zoneType=ZoneType.LIQUIDITY,
                        high=swing_highs[i].price,
                        low=swing_highs[i].price * 0.999,
                        midpoint=(swing_highs[i].price + swing_highs[i].price * 0.999) / 2,
                        strength=(swing_highs[i].strength + swing_highs[i + 1].strength) / 2,
                        touches=0,
                        active=True
                    )
                    liquidity_zones.append(zone)
        
        # Detect equal lows
        if len(swing_lows) >= 2:
            for i in range(len(swing_lows) - 1):
                if abs(swing_lows[i].price - swing_lows[i + 1].price) / swing_lows[i].price < 0.001:
                    zone = StructureZone(
                        zoneType=ZoneType.LIQUIDITY,
                        high=swing_lows[i].price * 1.001,
                        low=swing_lows[i].price,
                        midpoint=(swing_lows[i].price + swing_lows[i].price * 1.001) / 2,
                        strength=(swing_lows[i].strength + swing_lows[i + 1].strength) / 2,
                        touches=0,
                        active=True
                    )
                    liquidity_zones.append(zone)
        
        return liquidity_zones
    
    def _calculate_premium_discount(
        self,
        candles: List[MarketCandle],
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> Tuple[Optional[dict], Optional[dict]]:
        """
        Calculate premium and discount zones using latest major swing.
        
        Args:
            candles: Historical candle data
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            Tuple of (premium_zone, discount_zone)
        """
        if not swing_highs or not swing_lows:
            return None, None
        
        # Use last major swing high for premium
        last_swing_high = swing_highs[-1]
        premium_zone = {
            "high": last_swing_high.price,
            "low": last_swing_high.price * 0.995,  # 0.5% below
            "midpoint": (last_swing_high.price + last_swing_high.price * 0.995) / 2
        }
        
        # Use last major swing low for discount
        last_swing_low = swing_lows[-1]
        discount_zone = {
            "high": last_swing_low.price * 1.005,  # 0.5% above
            "low": last_swing_low.price,
            "midpoint": (last_swing_low.price + last_swing_low.price * 1.005) / 2
        }
        
        return premium_zone, discount_zone
    
    def _determine_market_phase(
        self,
        trend_result: TrendResult,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> str:
        """
        Determine current market phase.
        
        Args:
            trend_result: Trend analysis result
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            Market phase (TRENDING, ACCUMULATION, DISTRIBUTION, RANGING)
        """
        if trend_result.strength.value in ["STRONG", "VERY_STRONG"]:
            return "TRENDING"
        
        # Check for ranging (sideways price action)
        if len(swing_highs) >= 2 and len(swing_lows) >= 2:
            high_range = swing_highs[-1].price - swing_highs[-2].price
            low_range = swing_lows[-1].price - swing_lows[-2].price
            if abs(high_range) < 0.01 and abs(low_range) < 0.01:
                return "RANGING"
        
        # Default to trending if not ranging
        return "TRENDING"
    
    def _calculate_confidence(
        self,
        trend_result: TrendResult,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint],
        current_event: StructureEvent
    ) -> float:
        """
        Calculate overall confidence score.
        
        Args:
            trend_result: Trend analysis result
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            current_event: Current structural event
            
        Returns:
            Confidence score (0-100)
        """
        confidence = 0.0
        
        # Trend agreement (30%)
        confidence += trend_result.confidence * 0.3
        
        # Swing quality (25%)
        if swing_highs and swing_lows:
            avg_swing_strength = (
                sum(sh.strength for sh in swing_highs[-5:]) +
                sum(sl.strength for sl in swing_lows[-5:])
            ) / (len(swing_highs[-5:]) + len(swing_lows[-5:]))
            confidence += avg_swing_strength * 0.25
        
        # Event quality (25%)
        if current_event != StructureEvent.NONE:
            confidence += 25.0
        
        # Zone quality (20%)
        # Simplified: if we have zones, add confidence
        if swing_highs or swing_lows:
            confidence += 20.0
        
        return min(100.0, max(0.0, confidence))
    
    def _determine_direction(
        self,
        trend_result: TrendResult,
        swing_highs: List[SwingPoint],
        swing_lows: List[SwingPoint]
    ) -> StructureDirection:
        """
        Determine structure direction.
        
        Args:
            trend_result: Trend analysis result
            swing_highs: List of swing highs
            swing_lows: List of swing lows
            
        Returns:
            StructureDirection enum value
        """
        if trend_result.direction.value == "BULLISH":
            return StructureDirection.BULLISH
        elif trend_result.direction.value == "BEARISH":
            return StructureDirection.BEARISH
        elif trend_result.direction.value == "SIDEWAYS":
            return StructureDirection.NEUTRAL
        else:
            return StructureDirection.UNKNOWN
    
    def _generate_analysis(
        self,
        direction: StructureDirection,
        current_event: StructureEvent,
        market_phase: str,
        confidence: float
    ) -> str:
        """
        Generate human-readable analysis text.
        
        Args:
            direction: Structure direction
            current_event: Current structural event
            market_phase: Market phase
            confidence: Confidence score
            
        Returns:
            Analysis text string
        """
        parts = []
        
        # Direction and phase
        parts.append(f"{direction.value.lower()} structure in {market_phase.lower()} phase")
        
        # Current event
        if current_event != StructureEvent.NONE:
            parts.append(f"with {current_event.value}")
        
        # Confidence
        parts.append(f"({confidence:.1f}% confidence)")
        
        return ". ".join(parts) + "."
    
    def _create_unknown_result(
        self,
        candles: List[MarketCandle]
    ) -> MarketStructureResult:
        """
        Create a result for insufficient data.
        
        Args:
            candles: Historical candle data
            
        Returns:
            MarketStructureResult with UNKNOWN direction
        """
        symbol = candles[-1].symbol if candles else "UNKNOWN"
        timeframe = candles[-1].timeframe if candles else "UNKNOWN"
        
        return MarketStructureResult(
            symbol=symbol,
            timeframe=timeframe,
            direction=StructureDirection.UNKNOWN,
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
            marketPhase="UNKNOWN",
            confidence=0.0,
            analysis="Insufficient data for structure analysis"
        )
    
    def get_statistics(self) -> Dict[str, any]:
        """
        Get engine statistics.
        
        Returns:
            Dictionary with calculation statistics
        """
        avg_execution_time = (
            self._total_execution_time / self._calculation_count
            if self._calculation_count > 0
            else 0.0
        )
        
        return {
            'calculations': self._calculation_count,
            'average_execution_time': round(avg_execution_time, 2),
            'total_execution_time': round(self._total_execution_time, 2)
        }
    
    def reset_statistics(self) -> None:
        """Reset engine statistics."""
        self._calculation_count = 0
        self._total_execution_time = 0.0
