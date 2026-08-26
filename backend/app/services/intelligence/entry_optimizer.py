"""
Falcon Entry Optimizer
Determines Best Entry, Confirmation Entry, Aggressive/Conservative/Late Entry
"""
from typing import Optional, Dict, Any
from enum import Enum

from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse


class EntryQuality(str, Enum):
    """Entry quality classifications."""
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    POOR = "POOR"
    INVALID = "INVALID"


class EntryType(str, Enum):
    """Entry type classifications."""
    BEST = "BEST"
    CONFIRMATION = "CONFIRMATION"
    AGGRESSIVE = "AGGRESSIVE"
    CONSERVATIVE = "CONSERVATIVE"
    LATE = "LATE"


class EntryOptimization:
    """Entry optimization result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        entry_type: EntryType,
        entry_quality: EntryQuality,
        entry_price: float,
        confirmation_price: Optional[float],
        aggressive_price: Optional[float],
        conservative_price: Optional[float],
        reasoning: str
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.entry_type = entry_type
        self.entry_quality = entry_quality
        self.entry_price = entry_price
        self.confirmation_price = confirmation_price
        self.aggressive_price = aggressive_price
        self.conservative_price = conservative_price
        self.reasoning = reasoning
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'entryType': self.entry_type.value,
            'entryQuality': self.entry_quality.value,
            'entryPrice': self.entry_price,
            'confirmationPrice': self.confirmation_price,
            'aggressivePrice': self.aggressive_price,
            'conservativePrice': self.conservative_price,
            'reasoning': self.reasoning
        }


class EntryOptimizer:
    """
    Entry Optimizer - Optimal entry point determination.
    
    Determines:
    - Best Entry (optimal entry point)
    - Confirmation Entry (wait for confirmation)
    - Aggressive Entry (early entry)
    - Conservative Entry (safe entry)
    - Late Entry (missed optimal entry)
    - Entry Quality (EXCELLENT/GOOD/AVERAGE/POOR)
    """
    
    def __init__(self):
        """Initialize the entry optimizer."""
        self._optimization_count = 0
    
    def optimize_entry(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
        current_price: float,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> EntryOptimization:
        """
        Optimize entry point for a trade.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            direction: Trade direction (BUY or SELL)
            current_price: Current market price
            structure_result: Market structure analysis
            indicator_result: Indicator analysis
            
        Returns:
            EntryOptimization with optimal entry strategies
        """
        self._optimization_count += 1
        
        entry_type = self._determine_entry_type(
            direction, current_price, structure_result, indicator_result
        )
        
        entry_price = current_price
        
        confirmation_price = self._calculate_confirmation_entry(
            direction, current_price, structure_result
        )
        
        aggressive_price = self._calculate_aggressive_entry(
            direction, current_price, structure_result
        )
        
        conservative_price = self._calculate_conservative_entry(
            direction, current_price, structure_result
        )
        
        entry_quality = self._determine_entry_quality(
            direction, current_price, structure_result, indicator_result
        )
        
        reasoning = self._generate_reasoning(
            entry_type, entry_quality, direction, structure_result
        )
        
        return EntryOptimization(
            symbol=symbol,
            timeframe=timeframe,
            entry_type=entry_type,
            entry_quality=entry_quality,
            entry_price=entry_price,
            confirmation_price=confirmation_price,
            aggressive_price=aggressive_price,
            conservative_price=conservative_price,
            reasoning=reasoning
        )
    
    def _determine_entry_type(
        self,
        direction: str,
        current_price: float,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> EntryType:
        """Determine the current entry type."""
        if not structure_result or not indicator_result:
            return EntryType.LATE
        
        if direction == "BUY":
            if structure_result.activeDemandZones:
                demand_zones = structure_result.activeDemandZones
                for zone in demand_zones:
                    if zone.get('low', 0) <= current_price <= zone.get('high', 0):
                        return EntryType.BEST
            
            if indicator_result.rsi_14 < 40:
                return EntryType.AGGRESSIVE
            elif indicator_result.rsi_14 < 50:
                return EntryType.CONFIRMATION
            elif indicator_result.rsi_14 < 60:
                return EntryType.CONSERVATIVE
            else:
                return EntryType.LATE
        
        else:
            if structure_result.activeSupplyZones:
                supply_zones = structure_result.activeSupplyZones
                for zone in supply_zones:
                    if zone.get('low', 0) <= current_price <= zone.get('high', 0):
                        return EntryType.BEST
            
            if indicator_result.rsi_14 > 60:
                return EntryType.AGGRESSIVE
            elif indicator_result.rsi_14 > 50:
                return EntryType.CONFIRMATION
            elif indicator_result.rsi_14 > 40:
                return EntryType.CONSERVATIVE
            else:
                return EntryType.LATE
        
        return EntryType.LATE
    
    def _calculate_confirmation_entry(
        self,
        direction: str,
        current_price: float,
        structure_result: Optional[MarketStructureResult]
    ) -> Optional[float]:
        """Calculate confirmation entry price."""
        offset_pct = 0.0005
        
        if direction == "BUY":
            return current_price * (1 + offset_pct)
        else:
            return current_price * (1 - offset_pct)
    
    def _calculate_aggressive_entry(
        self,
        direction: str,
        current_price: float,
        structure_result: Optional[MarketStructureResult]
    ) -> Optional[float]:
        """Calculate aggressive entry price."""
        offset_pct = 0.001
        
        if direction == "BUY":
            return current_price * (1 - offset_pct)
        else:
            return current_price * (1 + offset_pct)
    
    def _calculate_conservative_entry(
        self,
        direction: str,
        current_price: float,
        structure_result: Optional[MarketStructureResult]
    ) -> Optional[float]:
        """Calculate conservative entry price."""
        offset_pct = 0.0015
        
        if direction == "BUY":
            return current_price * (1 + offset_pct)
        else:
            return current_price * (1 - offset_pct)
    
    def _determine_entry_quality(
        self,
        direction: str,
        current_price: float,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> EntryQuality:
        """Determine entry quality."""
        if not structure_result or not indicator_result:
            return EntryQuality.POOR
        
        quality_score = 0
        
        if direction == "BUY":
            if structure_result.activeDemandZones:
                quality_score += 3
            
            if indicator_result.rsi_14 < 40:
                quality_score += 2
            elif indicator_result.rsi_14 < 50:
                quality_score += 1
            
            if indicator_result.macd_line > indicator_result.macd_signal:
                quality_score += 2
        
        else:
            if structure_result.activeSupplyZones:
                quality_score += 3
            
            if indicator_result.rsi_14 > 60:
                quality_score += 2
            elif indicator_result.rsi_14 > 50:
                quality_score += 1
            
            if indicator_result.macd_line < indicator_result.macd_signal:
                quality_score += 2
        
        if quality_score >= 6:
            return EntryQuality.EXCELLENT
        elif quality_score >= 4:
            return EntryQuality.GOOD
        elif quality_score >= 2:
            return EntryQuality.AVERAGE
        else:
            return EntryQuality.POOR
    
    def _generate_reasoning(
        self,
        entry_type: EntryType,
        entry_quality: EntryQuality,
        direction: str,
        structure_result: Optional[MarketStructureResult]
    ) -> str:
        """Generate reasoning for entry recommendation."""
        if entry_quality == EntryQuality.EXCELLENT:
            return f"Excellent {entry_type.value} entry for {direction}. All conditions aligned."
        elif entry_quality == EntryQuality.GOOD:
            return f"Good {entry_type.value} entry for {direction}. Favorable conditions."
        elif entry_quality == EntryQuality.AVERAGE:
            return f"Average {entry_type.value} entry for {direction}. Proceed with caution."
        else:
            return f"Poor {entry_type.value} entry for {direction}. Consider waiting."
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        return {
            'optimizationCount': self._optimization_count
        }
