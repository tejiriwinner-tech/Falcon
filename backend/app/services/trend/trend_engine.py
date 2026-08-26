"""
Falcon Trend Detection Engine
Analyzes market trends using historical candles and technical indicators.
"""
import time
from typing import List, Dict, Optional, Tuple
from app.models.market_candle import MarketCandle
from app.schemas.trend_models import TrendDirection, TrendStrength, TrendResult


class TrendEngine:
    """
    Market trend detection engine.
    
    Analyzes historical candles and technical indicators to determine
    market trend direction, strength, and confidence.
    
    Trend Analysis Components:
    - EMA Alignment: Checks if EMAs are in bullish or bearish order
    - Price Position: Analyzes price relative to key EMAs
    - Swing Structure: Detects higher highs/lows and lower highs/lows
    - Confidence Scoring: Combines multiple factors for overall confidence
    """
    
    def __init__(self):
        """Initialize the trend engine."""
        self._calculation_count = 0
        self._total_execution_time = 0.0
    
    def calculate_trend(
        self,
        candles: List[MarketCandle],
        indicators: Dict[str, Optional[float]]
    ) -> TrendResult:
        """
        Calculate trend direction, strength, and confidence.
        
        Args:
            candles: Historical candle data (chronological order, oldest first)
            indicators: Dictionary of indicator values (ema_20, ema_50, ema_200, etc.)
            
        Returns:
            TrendResult with complete trend analysis
        """
        start_time = time.time()
        
        if not candles or len(candles) < 20:
            return self._create_unknown_result(candles, indicators)
        
        current_price = candles[-1].close
        
        # Analyze components
        ema_alignment_score, ema_direction = self._analyze_ema_alignment(indicators)
        price_above_ema20, price_above_ema50, price_above_ema200 = self._analyze_price_position(
            current_price, indicators
        )
        swing_structure = self._analyze_swing_structure(candles)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            ema_alignment_score,
            price_above_ema20,
            price_above_ema50,
            price_above_ema200,
            swing_structure
        )
        
        # Determine trend direction
        direction = self._determine_direction(
            ema_direction,
            price_above_ema20,
            price_above_ema50,
            price_above_ema200,
            swing_structure,
            confidence
        )
        
        # Determine trend strength
        strength = self._classify_strength(confidence)
        
        # Generate analysis text
        analysis = self._generate_analysis(
            direction,
            strength,
            ema_direction,
            swing_structure,
            confidence
        )
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        self._calculation_count += 1
        self._total_execution_time += execution_time
        
        return TrendResult(
            symbol=candles[-1].symbol,
            timeframe=candles[-1].timeframe,
            direction=direction,
            strength=strength,
            confidence=confidence,
            ema_alignment=ema_alignment_score,
            price_above_ema20=price_above_ema20,
            price_above_ema50=price_above_ema50,
            price_above_ema200=price_above_ema200,
            higher_highs=swing_structure['higher_highs'],
            higher_lows=swing_structure['higher_lows'],
            lower_highs=swing_structure['lower_highs'],
            lower_lows=swing_structure['lower_lows'],
            analysis=analysis
        )
    
    def _analyze_ema_alignment(
        self,
        indicators: Dict[str, Optional[float]]
    ) -> Tuple[float, str]:
        """
        Analyze EMA alignment for trend direction.
        
        Bullish: EMA20 > EMA50 > EMA200
        Bearish: EMA20 < EMA50 < EMA200
        
        Args:
            indicators: Dictionary of indicator values
            
        Returns:
            Tuple of (alignment_score, direction)
        """
        ema_20 = indicators.get('ema_20')
        ema_50 = indicators.get('ema_50')
        ema_200 = indicators.get('ema_200')
        
        if None in [ema_20, ema_50, ema_200]:
            return 0.0, "UNKNOWN"
        
        # Check bullish alignment
        if ema_20 > ema_50 > ema_200:
            # Calculate how well-aligned they are
            spread_20_50 = (ema_20 - ema_50) / ema_50 * 100
            spread_50_200 = (ema_50 - ema_200) / ema_200 * 100
            alignment_score = min(100, (spread_20_50 + spread_50_200) * 5)
            return alignment_score, "BULLISH"
        
        # Check bearish alignment
        if ema_20 < ema_50 < ema_200:
            spread_20_50 = (ema_50 - ema_20) / ema_20 * 100
            spread_50_200 = (ema_200 - ema_50) / ema_50 * 100
            alignment_score = min(100, (spread_20_50 + spread_50_200) * 5)
            return alignment_score, "BEARISH"
        
        # Mixed alignment (sideways)
        return 0.0, "SIDEWAYS"
    
    def _analyze_price_position(
        self,
        current_price: float,
        indicators: Dict[str, Optional[float]]
    ) -> Tuple[bool, bool, bool]:
        """
        Analyze price position relative to EMAs.
        
        Args:
            current_price: Current market price
            indicators: Dictionary of indicator values
            
        Returns:
            Tuple of (above_ema20, above_ema50, above_ema200)
        """
        ema_20 = indicators.get('ema_20')
        ema_50 = indicators.get('ema_50')
        ema_200 = indicators.get('ema_200')
        
        above_ema20 = ema_20 is not None and current_price > ema_20
        above_ema50 = ema_50 is not None and current_price > ema_50
        above_ema200 = ema_200 is not None and current_price > ema_200
        
        return above_ema20, above_ema50, above_ema200
    
    def _analyze_swing_structure(
        self,
        candles: List[MarketCandle]
    ) -> Dict[str, int]:
        """
        Analyze swing structure for higher highs/lows and lower highs/lows.
        
        Args:
            candles: Historical candle data
            
        Returns:
            Dictionary with swing structure counts
        """
        if len(candles) < 10:
            return {
                'higher_highs': 0,
                'higher_lows': 0,
                'lower_highs': 0,
                'lower_lows': 0
            }
        
        # Use last 20 candles for swing analysis
        recent_candles = candles[-20:]
        
        # Find swing highs and lows (simplified approach)
        highs = [candle.high for candle in recent_candles]
        lows = [candle.low for candle in recent_candles]
        
        higher_highs = 0
        higher_lows = 0
        lower_highs = 0
        lower_lows = 0
        
        # Compare consecutive swing points
        for i in range(1, len(highs)):
            if highs[i] > highs[i-1]:
                higher_highs += 1
            elif highs[i] < highs[i-1]:
                lower_highs += 1
            
            if lows[i] > lows[i-1]:
                higher_lows += 1
            elif lows[i] < lows[i-1]:
                lower_lows += 1
        
        return {
            'higher_highs': higher_highs,
            'higher_lows': higher_lows,
            'lower_highs': lower_highs,
            'lower_lows': lower_lows
        }
    
    def _calculate_confidence(
        self,
        ema_alignment: float,
        price_above_ema20: bool,
        price_above_ema50: bool,
        price_above_ema200: bool,
        swing_structure: Dict[str, int]
    ) -> float:
        """
        Calculate overall confidence score.
        
        Weighting:
        - EMA Alignment: 30%
        - Price Position: 25%
        - Swing Structure: 30%
        - Indicator Agreement: 15%
        
        Args:
            ema_alignment: EMA alignment score (0-100)
            price_above_ema20: Price above EMA20
            price_above_ema50: Price above EMA50
            price_above_ema200: Price above EMA200
            swing_structure: Swing structure counts
            
        Returns:
            Confidence score (0-100)
        """
        # EMA Alignment (30%)
        ema_score = ema_alignment * 0.3
        
        # Price Position (25%)
        price_score = 0.0
        if price_above_ema20:
            price_score += 8.33
        if price_above_ema50:
            price_score += 8.33
        if price_above_ema200:
            price_score += 8.34
        
        # Swing Structure (30%)
        total_swings = (
            swing_structure['higher_highs'] +
            swing_structure['higher_lows'] +
            swing_structure['lower_highs'] +
            swing_structure['lower_lows']
        )
        
        if total_swings > 0:
            bullish_swings = swing_structure['higher_highs'] + swing_structure['higher_lows']
            bearish_swings = swing_structure['lower_highs'] + swing_structure['lower_lows']
            swing_ratio = abs(bullish_swings - bearish_swings) / total_swings
            swing_score = swing_ratio * 100 * 0.3
        else:
            swing_score = 0.0
        
        # Indicator Agreement (15%)
        # Simplified: if price position aligns with EMA alignment
        indicator_score = 0.0
        if ema_alignment > 50 and (price_above_ema20 or price_above_ema50):
            indicator_score = 15.0
        elif ema_alignment < 50 and (not price_above_ema20 or not price_above_ema50):
            indicator_score = 15.0
        
        total_confidence = ema_score + price_score + swing_score + indicator_score
        return min(100.0, max(0.0, total_confidence))
    
    def _determine_direction(
        self,
        ema_direction: str,
        price_above_ema20: bool,
        price_above_ema50: bool,
        price_above_ema200: bool,
        swing_structure: Dict[str, int],
        confidence: float
    ) -> TrendDirection:
        """
        Determine overall trend direction.
        
        Args:
            ema_direction: EMA-based direction
            price_above_ema20: Price above EMA20
            price_above_ema50: Price above EMA50
            price_above_ema200: Price above EMA200
            swing_structure: Swing structure counts
            confidence: Overall confidence score
            
        Returns:
            TrendDirection enum value
        """
        if confidence < 40:
            return TrendDirection.UNKNOWN
        
        bullish_signals = 0
        bearish_signals = 0
        
        # EMA direction
        if ema_direction == "BULLISH":
            bullish_signals += 2
        elif ema_direction == "BEARISH":
            bearish_signals += 2
        
        # Price position
        if price_above_ema20 and price_above_ema50:
            bullish_signals += 2
        elif not price_above_ema20 and not price_above_ema50:
            bearish_signals += 2
        
        if price_above_ema200:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        # Swing structure
        bullish_swings = swing_structure['higher_highs'] + swing_structure['higher_lows']
        bearish_swings = swing_structure['lower_highs'] + swing_structure['lower_lows']
        
        if bullish_swings > bearish_swings:
            bullish_signals += 1
        elif bearish_swings > bullish_swings:
            bearish_signals += 1
        
        # Determine direction
        if bullish_signals > bearish_signals + 1:
            return TrendDirection.BULLISH
        elif bearish_signals > bullish_signals + 1:
            return TrendDirection.BEARISH
        else:
            return TrendDirection.SIDEWAYS
    
    def _classify_strength(self, confidence: float) -> TrendStrength:
        """
        Classify trend strength based on confidence score.
        
        Args:
            confidence: Confidence score (0-100)
            
        Returns:
            TrendStrength enum value
        """
        if confidence >= 90:
            return TrendStrength.VERY_STRONG
        elif confidence >= 75:
            return TrendStrength.STRONG
        elif confidence >= 60:
            return TrendStrength.MODERATE
        elif confidence >= 40:
            return TrendStrength.WEAK
        else:
            return TrendStrength.VERY_WEAK
    
    def _generate_analysis(
        self,
        direction: TrendDirection,
        strength: TrendStrength,
        ema_direction: str,
        swing_structure: Dict[str, int],
        confidence: float
    ) -> str:
        """
        Generate human-readable analysis text.
        
        Args:
            direction: Trend direction
            strength: Trend strength
            ema_direction: EMA-based direction
            swing_structure: Swing structure counts
            confidence: Confidence score
            
        Returns:
            Analysis text string
        """
        parts = []
        
        # Trend description
        parts.append(f"{strength.value} {direction.value.lower()} trend")
        
        # EMA description
        if ema_direction != "UNKNOWN":
            parts.append(f"with {ema_direction.lower()} EMA alignment")
        
        # Swing description
        bullish_swings = swing_structure['higher_highs'] + swing_structure['higher_lows']
        bearish_swings = swing_structure['lower_highs'] + swing_structure['lower_lows']
        
        if bullish_swings > bearish_swings:
            parts.append("and bullish swing structure")
        elif bearish_swings > bullish_swings:
            parts.append("and bearish swing structure")
        
        # Confidence
        parts.append(f"({confidence:.1f}% confidence)")
        
        return ". ".join(parts) + "."
    
    def _create_unknown_result(
        self,
        candles: List[MarketCandle],
        indicators: Dict[str, Optional[float]]
    ) -> TrendResult:
        """
        Create a result for insufficient data.
        
        Args:
            candles: Historical candle data
            indicators: Indicator values
            
        Returns:
            TrendResult with UNKNOWN direction
        """
        symbol = candles[-1].symbol if candles else "UNKNOWN"
        timeframe = candles[-1].timeframe if candles else "UNKNOWN"
        
        return TrendResult(
            symbol=symbol,
            timeframe=timeframe,
            direction=TrendDirection.UNKNOWN,
            strength=TrendStrength.VERY_WEAK,
            confidence=0.0,
            ema_alignment=0.0,
            price_above_ema20=False,
            price_above_ema50=False,
            price_above_ema200=False,
            higher_highs=0,
            higher_lows=0,
            lower_highs=0,
            lower_lows=0,
            analysis="Insufficient data for trend analysis"
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
