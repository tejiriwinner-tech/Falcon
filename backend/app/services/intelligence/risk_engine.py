"""
Falcon Risk Engine
Calculates Stop Loss, Take Profit, Risk/Reward, Position Risk
"""
from typing import Optional, Dict, Any
from enum import Enum

from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse


class RiskLevel(str, Enum):
    """Risk level classifications."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXTREME = "EXTREME"


class RiskCalculation:
    """Risk calculation result."""
    def __init__(
        self,
        symbol: str,
        timeframe: str,
        entry_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: Optional[float],
        take_profit_3: Optional[float],
        risk_reward_ratio: float,
        position_risk_pct: float,
        risk_level: RiskLevel,
        expected_drawdown_pct: float,
        expected_gain_pct: float
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profit_1 = take_profit_1
        self.take_profit_2 = take_profit_2
        self.take_profit_3 = take_profit_3
        self.risk_reward_ratio = risk_reward_ratio
        self.position_risk_pct = position_risk_pct
        self.risk_level = risk_level
        self.expected_drawdown_pct = expected_drawdown_pct
        self.expected_gain_pct = expected_gain_pct
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'entryPrice': self.entry_price,
            'stopLoss': self.stop_loss,
            'takeProfit1': self.take_profit_1,
            'takeProfit2': self.take_profit_2,
            'takeProfit3': self.take_profit_3,
            'riskRewardRatio': self.risk_reward_ratio,
            'positionRiskPct': self.position_risk_pct,
            'riskLevel': self.risk_level.value,
            'expectedDrawdownPct': self.expected_drawdown_pct,
            'expectedGainPct': self.expected_gain_pct
        }


class RiskEngine:
    """
    Risk Engine - Professional risk management calculations.
    
    Calculates:
    - Stop Loss (based on ATR and structure)
    - Take Profit levels (3 targets)
    - Risk/Reward ratio
    - Position risk percentage
    - Expected drawdown and gain
    - Overall risk level
    """
    
    def __init__(
        self,
        default_stop_loss_atr_multiple: float = 2.0,
        default_risk_pct: float = 1.0,
        min_rr_ratio: float = 2.0
    ):
        """
        Initialize the risk engine.
        
        Args:
            default_stop_loss_atr_multiple: ATR multiple for stop loss
            default_risk_pct: Default risk percentage per trade
            min_rr_ratio: Minimum risk/reward ratio
        """
        self.stop_loss_atr_multiple = default_stop_loss_atr_multiple
        self.default_risk_pct = default_risk_pct
        self.min_rr_ratio = min_rr_ratio
        self._calculation_count = 0
    
    def calculate_risk(
        self,
        symbol: str,
        timeframe: str,
        direction: str,
        entry_price: float,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> RiskCalculation:
        """
        Calculate risk parameters for a trade.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe
            direction: Trade direction (BUY or SELL)
            entry_price: Entry price
            structure_result: Market structure analysis
            indicator_result: Indicator analysis
            
        Returns:
            RiskCalculation with complete risk analysis
        """
        self._calculation_count += 1
        
        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(
            direction, entry_price, structure_result, indicator_result
        )
        
        # Calculate take profit levels
        tp1, tp2, tp3 = self._calculate_take_profits(
            direction, entry_price, stop_loss, structure_result
        )
        
        # Calculate risk/reward ratio
        risk_reward_ratio = self._calculate_rr_ratio(entry_price, stop_loss, tp1)
        
        # Calculate position risk
        position_risk_pct = self.default_risk_pct
        
        # Calculate expected drawdown and gain
        expected_drawdown_pct = abs((entry_price - stop_loss) / entry_price) * 100
        expected_gain_pct = abs((tp1 - entry_price) / entry_price) * 100
        
        # Determine risk level
        risk_level = self._determine_risk_level(
            risk_reward_ratio, expected_drawdown_pct, indicator_result
        )
        
        return RiskCalculation(
            symbol=symbol,
            timeframe=timeframe,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            risk_reward_ratio=risk_reward_ratio,
            position_risk_pct=position_risk_pct,
            risk_level=risk_level,
            expected_drawdown_pct=expected_drawdown_pct,
            expected_gain_pct=expected_gain_pct
        )
    
    def _calculate_stop_loss(
        self,
        direction: str,
        entry_price: float,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> float:
        """Calculate stop loss level."""
        if indicator_result and indicator_result.atr_14:
            atr_distance = indicator_result.atr_14 * self.stop_loss_atr_multiple
            
            if direction == "BUY":
                return entry_price - atr_distance
            else:
                return entry_price + atr_distance
        
        default_sl_pct = 0.01
        
        if direction == "BUY":
            return entry_price * (1 - default_sl_pct)
        else:
            return entry_price * (1 + default_sl_pct)
    
    def _calculate_take_profits(
        self,
        direction: str,
        entry_price: float,
        stop_loss: float,
        structure_result: Optional[MarketStructureResult]
    ) -> tuple[float, Optional[float], Optional[float]]:
        """Calculate take profit levels."""
        risk_distance = abs(entry_price - stop_loss)
        
        if direction == "BUY":
            if structure_result and structure_result.resistance:
                resistances = sorted(
                    [r for r in structure_result.resistance if r > entry_price]
                )
                if resistances:
                    tp1 = resistances[0]
                    tp2 = resistances[1] if len(resistances) > 1 else tp1 * 1.01
                    tp3 = resistances[2] if len(resistances) > 2 else tp1 * 1.02
                    return tp1, tp2, tp3
            
            tp1 = entry_price + (risk_distance * 2.0)
            tp2 = entry_price + (risk_distance * 3.0)
            tp3 = entry_price + (risk_distance * 4.0)
            return tp1, tp2, tp3
        
        else:
            if structure_result and structure_result.support:
                supports = sorted(
                    [s for s in structure_result.support if s < entry_price],
                    reverse=True
                )
                if supports:
                    tp1 = supports[0]
                    tp2 = supports[1] if len(supports) > 1 else tp1 * 0.99
                    tp3 = supports[2] if len(supports) > 2 else tp1 * 0.98
                    return tp1, tp2, tp3
            
            tp1 = entry_price - (risk_distance * 2.0)
            tp2 = entry_price - (risk_distance * 3.0)
            tp3 = entry_price - (risk_distance * 4.0)
            return tp1, tp2, tp3
    
    def _calculate_rr_ratio(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> float:
        """Calculate risk/reward ratio."""
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        
        if risk <= 0:
            return 0.0
        
        return reward / risk
    
    def _determine_risk_level(
        self,
        rr_ratio: float,
        expected_drawdown_pct: float,
        indicator_result: Optional[IndicatorResponse]
    ) -> RiskLevel:
        """Determine overall risk level."""
        risk_factors = 0
        
        if rr_ratio < self.min_rr_ratio:
            risk_factors += 1
        
        if expected_drawdown_pct > 2.0:
            risk_factors += 1
        
        if indicator_result and indicator_result.atr_14:
            atr_ratio = indicator_result.atr_14 / indicator_result.bb_middle if indicator_result.bb_middle else 0
            if atr_ratio > 0.02:
                risk_factors += 1
        
        if risk_factors >= 3:
            return RiskLevel.EXTREME
        elif risk_factors == 2:
            return RiskLevel.HIGH
        elif risk_factors == 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get engine statistics."""
        return {
            'calculationCount': self._calculation_count
        }
