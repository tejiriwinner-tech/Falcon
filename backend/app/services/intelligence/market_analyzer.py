"""
Falcon Market Analyzer
Analyzes market conditions: Trend, Momentum, Structure, Liquidity, Volatility, ATR, Session, State
"""
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum

from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse


class MarketState(str, Enum):
    """Market state classifications."""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"
    VOLATILE = "VOLATILE"
    BREAKOUT = "BREAKOUT"
    REVERSAL = "REVERSAL"
    ACCUMULATION = "ACCUMULATION"
    DISTRIBUTION = "DISTRIBUTION"


class MarketSession(str, Enum):
    """Trading session classifications."""
    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    OVERLAP = "OVERLAP"
    OFF_HOURS = "OFF_HOURS"


class MarketAnalyzerResult:
    """Market analysis result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        market_state: MarketState,
        session: MarketSession,
        trend_direction: str,
        trend_strength: str,
        momentum: str,
        structure_bias: str,
        liquidity_level: str,
        volatility_level: str,
        atr_value: Optional[float],
        confidence: float,
        timestamp: datetime
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.market_state = market_state
        self.session = session
        self.trend_direction = trend_direction
        self.trend_strength = trend_strength
        self.momentum = momentum
        self.structure_bias = structure_bias
        self.liquidity_level = liquidity_level
        self.volatility_level = volatility_level
        self.atr_value = atr_value
        self.confidence = confidence
        self.timestamp = timestamp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'marketState': self.market_state.value,
            'session': self.session.value,
            'trendDirection': self.trend_direction,
            'trendStrength': self.trend_strength,
            'momentum': self.momentum,
            'structureBias': self.structure_bias,
            'liquidityLevel': self.liquidity_level,
            'volatilityLevel': self.volatility_level,
            'atrValue': self.atr_value,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat()
        }


class MarketAnalyzer:
    """
    Market Analyzer - Comprehensive market condition analysis.
    
    Analyzes:
    - Trend (direction and strength)
    - Momentum (buying/selling pressure)
    - Structure (market phase)
    - Liquidity (zones and levels)
    - Volatility (ATR and price action)
    - Session (trading hours)
    - Market State (overall classification)
    """
    
    def __init__(self):
        """Initialize the market analyzer."""
        self._analysis_count = 0
    
    def analyze_market(
        self,
        symbol: str,
        timeframe: str,
        trend_result: Optional[TrendResult],
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse],
        current_price: Optional[float]
    ) -> MarketAnalyzerResult:
        """
        Analyze market conditions.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            trend_result: Trend analysis
            structure_result: Market structure analysis
            indicator_result: Indicator analysis
            current_price: Current market price
            
        Returns:
            MarketAnalyzerResult with comprehensive market analysis
        """
        self._analysis_count += 1
        
        # Extract trend information
        trend_direction = self._analyze_trend_direction(trend_result)
        trend_strength = self._analyze_trend_strength(trend_result)
        
        # Extract momentum
        momentum = self._analyze_momentum(indicator_result)
        
        # Extract structure
        structure_bias = self._analyze_structure(structure_result)
        
        # Extract liquidity
        liquidity_level = self._analyze_liquidity(structure_result)
        
        # Extract volatility
        volatility_level, atr_value = self._analyze_volatility(indicator_result, current_price)
        
        # Determine session
        session = self._determine_session()
        
        # Determine market state
        market_state = self._determine_market_state(
            trend_direction, trend_strength, structure_bias,
            volatility_level, momentum
        )
        
        # Calculate overall confidence
        confidence = self._calculate_confidence(
            trend_result, structure_result, indicator_result
        )
        
        return MarketAnalyzerResult(
            symbol=symbol,
            timeframe=timeframe,
            market_state=market_state,
            session=session,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            momentum=momentum,
            structure_bias=structure_bias,
            liquidity_level=liquidity_level,
            volatility_level=volatility_level,
            atr_value=atr_value,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc)
        )
    
    def _analyze_trend_direction(self, trend_result: Optional[TrendResult]) -> str:
        """Analyze trend direction."""
        if not trend_result:
            return "UNKNOWN"
        return trend_result.direction.value
    
    def _analyze_trend_strength(self, trend_result: Optional[TrendResult]) -> str:
        """Analyze trend strength."""
        if not trend_result:
            return "UNKNOWN"
        return trend_result.strength.value
    
    def _analyze_momentum(self, indicator_result: Optional[IndicatorResponse]) -> str:
        """Analyze momentum from RSI and MACD."""
        if not indicator_result:
            return "NEUTRAL"
        
        rsi = indicator_result.rsi_14
        macd_bullish = indicator_result.macd_line > indicator_result.macd_signal
        
        if rsi > 60 and macd_bullish:
            return "STRONG_BULLISH"
        elif rsi > 50 and macd_bullish:
            return "BULLISH"
        elif rsi < 40 and not macd_bullish:
            return "STRONG_BEARISH"
        elif rsi < 50 and not macd_bullish:
            return "BEARISH"
        else:
            return "NEUTRAL"
    
    def _analyze_structure(self, structure_result: Optional[MarketStructureResult]) -> str:
        """Analyze market structure bias."""
        if not structure_result:
            return "UNKNOWN"
        return structure_result.direction.value
    
    def _analyze_liquidity(self, structure_result: Optional[MarketStructureResult]) -> str:
        """Analyze liquidity level."""
        if not structure_result:
            return "UNKNOWN"
        
        liquidity_zones = len(structure_result.liquidityZones) if structure_result.liquidityZones else 0
        
        if liquidity_zones >= 3:
            return "HIGH"
        elif liquidity_zones >= 2:
            return "MEDIUM"
        elif liquidity_zones >= 1:
            return "LOW"
        else:
            return "UNKNOWN"
    
    def _analyze_volatility(
        self,
        indicator_result: Optional[IndicatorResponse],
        current_price: Optional[float]
    ) -> tuple[str, Optional[float]]:
        """Analyze volatility level."""
        if not indicator_result or not current_price:
            return "UNKNOWN", None
        
        atr = indicator_result.atr_14
        if not atr:
            return "UNKNOWN", None
        
        atr_pct = (atr / current_price) * 100
        
        if atr_pct > 2.0:
            return "EXTREME", atr
        elif atr_pct > 1.0:
            return "HIGH", atr
        elif atr_pct > 0.5:
            return "MEDIUM", atr
        elif atr_pct > 0.1:
            return "LOW", atr
        else:
            return "VERY_LOW", atr
    
    def _determine_session(self) -> MarketSession:
        """Determine current trading session (UTC based)."""
        now = datetime.now(timezone.utc)
        hour = now.hour
        
        if 0 <= hour < 7:
            return MarketSession.ASIA
        elif 7 <= hour < 12:
            return MarketSession.LONDON
        elif 12 <= hour < 16:
            return MarketSession.OVERLAP
        elif 16 <= hour < 21:
            return MarketSession.NEW_YORK
        else:
            return MarketSession.OFF_HOURS
    
    def _determine_market_state(
        self,
        trend_direction: str,
        trend_strength: str,
        structure_bias: str,
        volatility_level: str,
        momentum: str
    ) -> MarketState:
        """Determine overall market state."""
        if volatility_level == "EXTREME":
            return MarketState.VOLATILE
        
        if trend_direction == "BULLISH" and trend_strength in ["STRONG", "VERY_STRONG"]:
            if structure_bias == "BULLISH":
                return MarketState.BULLISH
            else:
                return MarketState.BREAKOUT
        
        if trend_direction == "BEARISH" and trend_strength in ["STRONG", "VERY_STRONG"]:
            if structure_bias == "BEARISH":
                return MarketState.BEARISH
            else:
                return MarketState.BREAKOUT
        
        if trend_direction == "SIDEWAYS" or trend_strength in ["WEAK", "VERY_WEAK"]:
            if momentum in ["STRONG_BULLISH", "STRONG_BEARISH"]:
                return MarketState.REVERSAL
            else:
                return MarketState.RANGING
        
        if structure_bias == "BULLISH" and momentum == "STRONG_BULLISH":
            return MarketState.ACCUMULATION
        
        if structure_bias == "BEARISH" and momentum == "STRONG_BEARISH":
            return MarketState.DISTRIBUTION
        
        return MarketState.RANGING
    
    def _calculate_confidence(
        self,
        trend_result: Optional[TrendResult],
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> float:
        """Calculate overall confidence in market analysis."""
        confidence_scores = []
        
        if trend_result:
            confidence_scores.append(trend_result.confidence)
        
        if structure_result:
            confidence_scores.append(structure_result.confidence)
        
        if indicator_result:
            confidence_scores.append(80.0)
        
        if not confidence_scores:
            return 0.0
        
        return sum(confidence_scores) / len(confidence_scores)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            'analysisCount': self._analysis_count
        }
