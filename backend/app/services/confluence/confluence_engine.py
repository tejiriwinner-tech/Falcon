"""
Falcon Confluence Engine
Combines multiple analysis factors into institutional-grade trading decisions.
"""
import time
from typing import List, Dict, Optional, Any
from app.schemas.confluence_models import (
    SignalDirection, SignalQuality, ConfirmationStatus,
    ConfluenceFactor, TradeLevels, SignalDecision
)
from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse


class ConfluenceEngine:
    """
    Signal confluence and decision engine.
    
    Combines trend, market structure, indicators, news, volatility,
    and risk filters into a single institutional-grade trading decision.
    
    Filter Weights:
    - Trend: 25%
    - Market Structure: 25%
    - Indicators: 20%
    - News: 15%
    - Volatility: 10%
    - Risk: 5%
    """
    
    def __init__(self, news_window_minutes: int = 30, min_rr: float = 2.0):
        """
        Initialize the confluence engine.
        
        Args:
            news_window_minutes: Minutes before/after news to reject signals
            min_rr: Minimum risk/reward ratio
        """
        self.news_window_minutes = news_window_minutes
        self.min_rr = min_rr
        self._calculation_count = 0
        self._total_execution_time = 0.0
        self._buy_signals = 0
        self._sell_signals = 0
        self._wait_signals = 0
        self._total_confidence = 0.0
    
    def evaluate(
        self,
        trend_result: TrendResult,
        structure_result: MarketStructureResult,
        indicator_result: IndicatorResponse,
        current_price: float,
        news_events: Optional[List[Dict]] = None,
        economic_calendar: Optional[List[Dict]] = None
    ) -> SignalDecision:
        """
        Evaluate confluence and generate trading decision.
        
        Args:
            trend_result: Trend analysis result
            structure_result: Market structure result
            indicator_result: Indicator analysis result
            current_price: Current market price
            news_events: Recent news events (optional)
            economic_calendar: Economic calendar events (optional)
            
        Returns:
            SignalDecision with complete analysis
        """
        start_time = time.time()
        
        # Evaluate each filter
        trend_factor = self._evaluate_trend(trend_result)
        structure_factor = self._evaluate_structure(structure_result)
        indicator_factor = self._evaluate_indicators(indicator_result)
        news_factor = self._evaluate_news(news_events, economic_calendar)
        volatility_factor = self._evaluate_volatility(indicator_result, current_price)
        risk_factor = self._evaluate_risk(structure_result, current_price)
        
        # Calculate overall confidence
        confidence = self._calculate_confidence([
            trend_factor, structure_factor, indicator_factor,
            news_factor, volatility_factor, risk_factor
        ])
        
        # Make decision
        direction = self._make_decision(
            trend_factor, structure_factor, indicator_factor,
            news_factor, volatility_factor, risk_factor, confidence
        )
        
        # Calculate trade levels
        trade_levels = self._calculate_trade_levels(
            direction, structure_result, current_price, indicator_result
        )
        
        # Determine quality
        quality = self._classify_quality(confidence)
        
        # Generate explanations
        factors = [trend_factor, structure_factor, indicator_factor, news_factor, volatility_factor, risk_factor]
        reasons, warnings = self._generate_explanations(factors, direction, trade_levels)
        
        # Generate summaries
        trend_summary = self._generate_trend_summary(trend_result)
        structure_summary = self._generate_structure_summary(structure_result)
        indicator_summary = self._generate_indicator_summary(indicator_result)
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000
        self._calculation_count += 1
        self._total_execution_time += execution_time
        self._total_confidence += confidence
        
        if direction == SignalDirection.BUY:
            self._buy_signals += 1
        elif direction == SignalDirection.SELL:
            self._sell_signals += 1
        else:
            self._wait_signals += 1
        
        return SignalDecision(
            symbol=trend_result.symbol,
            timeframe=trend_result.timeframe,
            direction=direction,
            quality=quality,
            confidence=confidence,
            tradeLevels=trade_levels,
            trend=trend_summary,
            marketStructure=structure_summary,
            indicatorSummary=indicator_summary,
            factors=factors,
            reasons=reasons,
            warnings=warnings
        )
    
    def _evaluate_trend(self, trend_result: TrendResult) -> ConfluenceFactor:
        """Evaluate trend filter (25% weight)."""
        weight = 0.25
        
        if trend_result.direction.value == "BULLISH":
            if trend_result.strength.value in ["STRONG", "VERY_STRONG"]:
                return ConfluenceFactor(
                    name="Trend",
                    status=ConfirmationStatus.CONFIRMED,
                    score=trend_result.confidence,
                    weight=weight,
                    reason=f"Strong bullish trend ({trend_result.strength.value})"
                )
            else:
                return ConfluenceFactor(
                    name="Trend",
                    status=ConfirmationStatus.PARTIAL,
                    score=trend_result.confidence * 0.7,
                    weight=weight,
                    reason=f"Weak bullish trend ({trend_result.strength.value})"
                )
        elif trend_result.direction.value == "BEARISH":
            if trend_result.strength.value in ["STRONG", "VERY_STRONG"]:
                return ConfluenceFactor(
                    name="Trend",
                    status=ConfirmationStatus.CONFIRMED,
                    score=trend_result.confidence,
                    weight=weight,
                    reason=f"Strong bearish trend ({trend_result.strength.value})"
                )
            else:
                return ConfluenceFactor(
                    name="Trend",
                    status=ConfirmationStatus.PARTIAL,
                    score=trend_result.confidence * 0.7,
                    weight=weight,
                    reason=f"Weak bearish trend ({trend_result.strength.value})"
                )
        else:
            return ConfluenceFactor(
                name="Trend",
                status=ConfirmationStatus.REJECTED,
                score=0.0,
                weight=weight,
                reason="Sideways or unknown trend"
            )
    
    def _evaluate_structure(self, structure_result: MarketStructureResult) -> ConfluenceFactor:
        """Evaluate market structure filter (25% weight)."""
        weight = 0.25
        
        # Check for bullish structure
        if structure_result.direction.value == "BULLISH":
            if structure_result.currentEvent.value in ["BOS", "CHOCH"]:
                if structure_result.activeDemandZones:
                    return ConfluenceFactor(
                        name="Market Structure",
                        status=ConfirmationStatus.CONFIRMED,
                        score=structure_result.confidence,
                        weight=weight,
                        reason=f"Bullish {structure_result.currentEvent.value} in demand zone"
                    )
                else:
                    return ConfluenceFactor(
                        name="Market Structure",
                        status=ConfirmationStatus.PARTIAL,
                        score=structure_result.confidence * 0.8,
                        weight=weight,
                        reason=f"Bullish {structure_result.currentEvent.value} without demand zone"
                    )
            else:
                return ConfluenceFactor(
                    name="Market Structure",
                    status=ConfirmationStatus.PARTIAL,
                    score=structure_result.confidence * 0.6,
                    weight=weight,
                    reason="Bullish structure but no clear event"
                )
        elif structure_result.direction.value == "BEARISH":
            if structure_result.currentEvent.value in ["BOS", "CHOCH"]:
                if structure_result.activeSupplyZones:
                    return ConfluenceFactor(
                        name="Market Structure",
                        status=ConfirmationStatus.CONFIRMED,
                        score=structure_result.confidence,
                        weight=weight,
                        reason=f"Bearish {structure_result.currentEvent.value} in supply zone"
                    )
                else:
                    return ConfluenceFactor(
                        name="Market Structure",
                        status=ConfirmationStatus.PARTIAL,
                        score=structure_result.confidence * 0.8,
                        weight=weight,
                        reason=f"Bearish {structure_result.currentEvent.value} without supply zone"
                    )
            else:
                return ConfluenceFactor(
                    name="Market Structure",
                    status=ConfirmationStatus.PARTIAL,
                    score=structure_result.confidence * 0.6,
                    weight=weight,
                    reason="Bearish structure but no clear event"
                )
        else:
            return ConfluenceFactor(
                name="Market Structure",
                status=ConfirmationStatus.REJECTED,
                score=0.0,
                weight=weight,
                reason="Neutral or unknown structure"
            )
    
    def _evaluate_indicators(self, indicator_result: IndicatorResponse) -> ConfluenceFactor:
        """Evaluate indicator filter (20% weight)."""
        weight = 0.20
        score = 0.0
        reasons = []
        
        # EMA alignment
        if indicator_result.ema_20 and indicator_result.ema_50 and indicator_result.ema_200:
            if indicator_result.ema_20 > indicator_result.ema_50 > indicator_result.ema_200:
                score += 30
                reasons.append("Bullish EMA alignment")
            elif indicator_result.ema_20 < indicator_result.ema_50 < indicator_result.ema_200:
                score += 30
                reasons.append("Bearish EMA alignment")
        
        # RSI
        if indicator_result.rsi_14:
            if 40 < indicator_result.rsi_14 < 60:
                score += 25
                reasons.append("RSI in healthy range")
            elif indicator_result.rsi_14 < 30:
                score += 15
                reasons.append("RSI oversold (potential bounce)")
            elif indicator_result.rsi_14 > 70:
                score += 15
                reasons.append("RSI overbought (potential pullback)")
        
        # MACD
        if indicator_result.macd_line and indicator_result.macd_signal:
            if indicator_result.macd_line > indicator_result.macd_signal:
                score += 25
                reasons.append("Bullish MACD")
            else:
                score += 25
                reasons.append("Bearish MACD")
        
        # ATR (volatility check)
        if indicator_result.atr_14:
            score += 20
            reasons.append("ATR available")
        
        status = ConfirmationStatus.CONFIRMED if score >= 70 else ConfirmationStatus.PARTIAL if score >= 40 else ConfirmationStatus.REJECTED
        
        return ConfluenceFactor(
            name="Indicators",
            status=status,
            score=score,
            weight=weight,
            reason=", ".join(reasons) if reasons else "Insufficient indicator data"
        )
    
    def _evaluate_news(
        self,
        news_events: Optional[List[Dict]],
        economic_calendar: Optional[List[Dict]]
    ) -> ConfluenceFactor:
        """Evaluate news filter (15% weight)."""
        weight = 0.15
        
        # Simplified news check - in production, this would check actual news
        # For now, assume no high-impact news
        return ConfluenceFactor(
            name="News",
            status=ConfirmationStatus.CONFIRMED,
            score=100.0,
            weight=weight,
            reason="No high-impact news in window"
        )
    
    def _evaluate_volatility(
        self,
        indicator_result: IndicatorResponse,
        current_price: float
    ) -> ConfluenceFactor:
        """Evaluate volatility filter (10% weight)."""
        weight = 0.10
        
        if not indicator_result.atr_14:
            return ConfluenceFactor(
                name="Volatility",
                status=ConfirmationStatus.PARTIAL,
                score=50.0,
                weight=weight,
                reason="ATR not available"
            )
        
        # Calculate ATR percentage
        atr_pct = (indicator_result.atr_14 / current_price) * 100
        
        # Reject very low volatility (< 0.1%)
        if atr_pct < 0.1:
            return ConfluenceFactor(
                name="Volatility",
                status=ConfirmationStatus.REJECTED,
                score=0.0,
                weight=weight,
                reason=f"Very low volatility ({atr_pct:.2f}%)"
            )
        
        # Reject extreme volatility (> 2%)
        if atr_pct > 2.0:
            return ConfluenceFactor(
                name="Volatility",
                status=ConfirmationStatus.REJECTED,
                score=0.0,
                weight=weight,
                reason=f"Extreme volatility ({atr_pct:.2f}%)"
            )
        
        # Healthy volatility
        return ConfluenceFactor(
            name="Volatility",
            status=ConfirmationStatus.CONFIRMED,
            score=100.0,
            weight=weight,
            reason=f"Healthy volatility ({atr_pct:.2f}%)"
        )
    
    def _evaluate_risk(
        self,
        structure_result: MarketStructureResult,
        current_price: float
    ) -> ConfluenceFactor:
        """Evaluate risk filter (5% weight)."""
        weight = 0.05
        
        # Calculate potential RR based on structure
        if structure_result.support and structure_result.resistance:
            nearest_support = min(structure_result.support, key=lambda x: abs(x - current_price))
            nearest_resistance = min(structure_result.resistance, key=lambda x: abs(x - current_price))
            
            risk = abs(current_price - nearest_support)
            reward = abs(nearest_resistance - current_price)
            
            if risk > 0:
                rr = reward / risk
                if rr >= self.min_rr:
                    return ConfluenceFactor(
                        name="Risk",
                        status=ConfirmationStatus.CONFIRMED,
                        score=100.0,
                        weight=weight,
                        reason=f"Good RR ratio ({rr:.2f})"
                    )
                else:
                    return ConfluenceFactor(
                        name="Risk",
                        status=ConfirmationStatus.REJECTED,
                        score=0.0,
                        weight=weight,
                        reason=f"Poor RR ratio ({rr:.2f})"
                    )
        
        return ConfluenceFactor(
            name="Risk",
            status=ConfirmationStatus.PARTIAL,
            score=50.0,
            weight=weight,
            reason="Unable to calculate RR ratio"
        )
    
    def _calculate_confidence(self, factors: List[ConfluenceFactor]) -> float:
        """Calculate overall confidence score."""
        total_score = 0.0
        for factor in factors:
            total_score += factor.score * factor.weight
        
        return min(100.0, max(0.0, total_score))
    
    def _make_decision(
        self,
        trend_factor: ConfluenceFactor,
        structure_factor: ConfluenceFactor,
        indicator_factor: ConfluenceFactor,
        news_factor: ConfluenceFactor,
        volatility_factor: ConfluenceFactor,
        risk_factor: ConfluenceFactor,
        confidence: float
    ) -> SignalDirection:
        """Make trading decision based on all factors."""
        # Check for rejections
        rejections = [
            factor for factor in [trend_factor, structure_factor, indicator_factor,
                               news_factor, volatility_factor, risk_factor]
            if factor.status == ConfirmationStatus.REJECTED
        ]
        
        if rejections:
            return SignalDirection.WAIT
        
        # Check for low confidence
        if confidence < 60:
            return SignalDirection.WAIT
        
        # Determine direction based on trend and structure
        bullish_signals = 0
        bearish_signals = 0
        
        if trend_factor.status == ConfirmationStatus.CONFIRMED:
            if "bullish" in trend_factor.reason.lower():
                bullish_signals += 1
            elif "bearish" in trend_factor.reason.lower():
                bearish_signals += 1
        
        if structure_factor.status == ConfirmationStatus.CONFIRMED:
            if "bullish" in structure_factor.reason.lower():
                bullish_signals += 1
            elif "bearish" in structure_factor.reason.lower():
                bearish_signals += 1
        
        if indicator_factor.status == ConfirmationStatus.CONFIRMED:
            if "bullish" in indicator_factor.reason.lower():
                bullish_signals += 1
            elif "bearish" in indicator_factor.reason.lower():
                bearish_signals += 1
        
        # Make decision
        if bullish_signals > bearish_signals:
            return SignalDirection.BUY
        elif bearish_signals > bullish_signals:
            return SignalDirection.SELL
        else:
            return SignalDirection.WAIT
    
    def _calculate_trade_levels(
        self,
        direction: SignalDirection,
        structure_result: MarketStructureResult,
        current_price: float,
        indicator_result: IndicatorResponse
    ) -> TradeLevels:
        """Calculate trade levels (entry, SL, TP, RR)."""
        trade_levels = TradeLevels()
        
        if direction == SignalDirection.WAIT:
            return trade_levels
        
        # Use current price as entry
        trade_levels.entry = current_price
        
        # Calculate stop loss based on ATR
        if indicator_result.atr_14:
            atr = 2 * indicator_result.atr_14
            if direction == SignalDirection.BUY:
                trade_levels.stopLoss = current_price - atr
            else:
                trade_levels.stopLoss = current_price + atr
        else:
            # Default 1% SL
            if direction == SignalDirection.BUY:
                trade_levels.stopLoss = current_price * 0.99
            else:
                trade_levels.stopLoss = current_price * 1.01
        
        # Calculate take profits based on structure
        if direction == SignalDirection.BUY:
            if structure_result.resistance:
                trade_levels.takeProfit1 = min(structure_result.resistance, key=lambda x: abs(x - current_price))
                trade_levels.takeProfit2 = trade_levels.takeProfit1 * 1.01 if trade_levels.takeProfit1 else None
                trade_levels.takeProfit3 = trade_levels.takeProfit1 * 1.02 if trade_levels.takeProfit1 else None
            else:
                # Default TPs
                risk = abs(current_price - trade_levels.stopLoss)
                trade_levels.takeProfit1 = current_price + (risk * 2)
                trade_levels.takeProfit2 = current_price + (risk * 3)
                trade_levels.takeProfit3 = current_price + (risk * 4)
        else:
            if structure_result.support:
                trade_levels.takeProfit1 = min(structure_result.support, key=lambda x: abs(x - current_price))
                trade_levels.takeProfit2 = trade_levels.takeProfit1 * 0.99 if trade_levels.takeProfit1 else None
                trade_levels.takeProfit3 = trade_levels.takeProfit1 * 0.98 if trade_levels.takeProfit1 else None
            else:
                # Default TPs
                risk = abs(trade_levels.stopLoss - current_price)
                trade_levels.takeProfit1 = current_price - (risk * 2)
                trade_levels.takeProfit2 = current_price - (risk * 3)
                trade_levels.takeProfit3 = current_price - (risk * 4)
        
        # Calculate RR
        if trade_levels.entry and trade_levels.stopLoss and trade_levels.takeProfit1:
            risk = abs(trade_levels.entry - trade_levels.stopLoss)
            reward = abs(trade_levels.takeProfit1 - trade_levels.entry)
            trade_levels.riskReward = reward / risk if risk > 0 else None
        
        return trade_levels
    
    def _classify_quality(self, confidence: float) -> SignalQuality:
        """Classify signal quality based on confidence."""
        if confidence >= 90:
            return SignalQuality.VERY_HIGH
        elif confidence >= 80:
            return SignalQuality.HIGH
        elif confidence >= 70:
            return SignalQuality.MEDIUM
        elif confidence >= 50:
            return SignalQuality.LOW
        else:
            return SignalQuality.VERY_LOW
    
    def _generate_explanations(
        self,
        factors: List[ConfluenceFactor],
        direction: SignalDirection,
        trade_levels: TradeLevels
    ) -> tuple[List[str], List[str]]:
        """Generate reasons and warnings."""
        reasons = []
        warnings = []
        
        for factor in factors:
            if factor.status == ConfirmationStatus.CONFIRMED:
                reasons.append(f"✓ {factor.reason}")
            elif factor.status == ConfirmationStatus.REJECTED:
                warnings.append(f"✗ {factor.reason}")
        
        # Add trade level info
        if direction != SignalDirection.WAIT and trade_levels.riskReward:
            reasons.append(f"✓ RR {trade_levels.riskReward:.1f}")
        
        return reasons, warnings
    
    def _generate_trend_summary(self, trend_result: TrendResult) -> str:
        """Generate trend summary."""
        return f"{trend_result.direction.value} trend ({trend_result.strength.value})"
    
    def _generate_structure_summary(self, structure_result: MarketStructureResult) -> str:
        """Generate structure summary."""
        return f"{structure_result.direction.value} structure ({structure_result.currentEvent.value})"
    
    def _generate_indicator_summary(self, indicator_result: IndicatorResponse) -> str:
        """Generate indicator summary."""
        return f"{indicator_result.trend} trend ({indicator_result.signal} signal)"
    
    def get_statistics(self) -> Dict[str, any]:
        """Get engine statistics."""
        avg_execution_time = (
            self._total_execution_time / self._calculation_count
            if self._calculation_count > 0
            else 0.0
        )
        
        avg_confidence = (
            self._total_confidence / self._calculation_count
            if self._calculation_count > 0
            else 0.0
        )
        
        return {
            'calculations': self._calculation_count,
            'average_execution_time': round(avg_execution_time, 2),
            'buy_signals': self._buy_signals,
            'sell_signals': self._sell_signals,
            'wait_signals': self._wait_signals,
            'average_confidence': round(avg_confidence, 2)
        }
    
    def reset_statistics(self) -> None:
        """Reset engine statistics."""
        self._calculation_count = 0
        self._total_execution_time = 0.0
        self._buy_signals = 0
        self._sell_signals = 0
        self._wait_signals = 0
        self._total_confidence = 0.0
