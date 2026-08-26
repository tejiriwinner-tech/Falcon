"""
Falcon Volatility Analyzer
Analyzes market volatility using ATR and price action
"""
from typing import Optional, Dict, Any
from enum import Enum

from app.schemas.indicator_models import IndicatorResponse


class VolatilityState(str, Enum):
    """Volatility state classifications."""
    EXTREME = "EXTREME"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    DORMANT = "DORMANT"


class VolatilityAnalysis:
    """Volatility analysis result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        volatility_state: VolatilityState,
        atr_value: Optional[float],
        atr_percentage: float,
        bb_width: Optional[float],
        is_expanding: bool,
        is_contracting: bool
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.volatility_state = volatility_state
        self.atr_value = atr_value
        self.atr_percentage = atr_percentage
        self.bb_width = bb_width
        self.is_expanding = is_expanding
        self.is_contracting = is_contracting
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'volatilityState': self.volatility_state.value,
            'atrValue': self.atr_value,
            'atrPercentage': self.atr_percentage,
            'bbWidth': self.bb_width,
            'isExpanding': self.is_expanding,
            'isContracting': self.is_contracting
        }


class VolatilityAnalyzer:
    """
    Volatility Analyzer - Market volatility analysis.
    
    Analyzes:
    - ATR (Average True Range)
    - ATR Percentage
    - Bollinger Band Width
    - Volatility State (EXTREME/HIGH/NORMAL/LOW/DORMANT)
    - Expansion/Contraction
    """
    
    def __init__(self):
        """Initialize the volatility analyzer."""
        self._analysis_count = 0
    
    def analyze_volatility(
        self,
        symbol: str,
        timeframe: str,
        indicator_result: Optional[IndicatorResponse],
        current_price: Optional[float]
    ) -> VolatilityAnalysis:
        """
        Analyze market volatility.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            indicator_result: Indicator analysis
            current_price: Current market price
            
        Returns:
            VolatilityAnalysis with complete volatility assessment
        """
        self._analysis_count += 1
        
        if not indicator_result or not current_price:
            return VolatilityAnalysis(
                symbol=symbol,
                timeframe=timeframe,
                volatility_state=VolatilityState.NORMAL,
                atr_value=None,
                atr_percentage=0.0,
                bb_width=None,
                is_expanding=False,
                is_contracting=False
            )
        
        atr_value = indicator_result.atr_14
        atr_percentage = (atr_value / current_price * 100) if atr_value else 0.0
        
        bb_width = None
        if indicator_result.bb_upper and indicator_result.bb_lower:
            bb_width = indicator_result.bb_upper - indicator_result.bb_lower
        
        volatility_state = self._determine_volatility_state(atr_percentage)
        
        is_expanding = self._is_expanding(indicator_result, bb_width)
        is_contracting = self._is_contracting(indicator_result, bb_width)
        
        return VolatilityAnalysis(
            symbol=symbol,
            timeframe=timeframe,
            volatility_state=volatility_state,
            atr_value=atr_value,
            atr_percentage=atr_percentage,
            bb_width=bb_width,
            is_expanding=is_expanding,
            is_contracting=is_contracting
        )
    
    def _determine_volatility_state(self, atr_percentage: float) -> VolatilityState:
        """Determine volatility state from ATR percentage."""
        if atr_percentage > 2.5:
            return VolatilityState.EXTREME
        elif atr_percentage > 1.5:
            return VolatilityState.HIGH
        elif atr_percentage > 0.5:
            return VolatilityState.NORMAL
        elif atr_percentage > 0.1:
            return VolatilityState.LOW
        else:
            return VolatilityState.DORMANT
    
    def _is_expanding(
        self,
        indicator_result: IndicatorResponse,
        bb_width: Optional[float]
    ) -> bool:
        """Check if volatility is expanding."""
        if not bb_width:
            return False
        return bb_width > indicator_result.bb_middle * 0.02 if indicator_result.bb_middle else False
    
    def _is_contracting(
        self,
        indicator_result: IndicatorResponse,
        bb_width: Optional[float]
    ) -> bool:
        """Check if volatility is contracting."""
        if not bb_width:
            return False
        return bb_width < indicator_result.bb_middle * 0.01 if indicator_result.bb_middle else False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analyzer statistics."""
        return {
            'analysisCount': self._analysis_count
        }
