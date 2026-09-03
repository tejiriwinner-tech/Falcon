"""
Falcon Intelligent Signal Generator
Transforms AI decisions into complete institutional-quality trading setups.
"""
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any, Dict
from app.schemas.signal_models import (
    SignalType, SignalStatus, TradeSetup, SignalStatistics, TradeManagement
)
from app.schemas.decision_models import DecisionType, AIDecisionResult
from app.schemas.trend_models import TrendResult
from app.schemas.market_structure_models import MarketStructureResult
from app.schemas.indicator_models import IndicatorResponse
from app.schemas.signal_score_models import SignalScoreResult
from app.schemas.signal_settings import SignalSettings
from app.services.patterns.candlestick_pattern_engine import candlestick_pattern_engine, PatternBias


class SignalGenerator:
    """
    Intelligent Signal Generator.
    
    Transforms AI decisions into complete institutional-quality trading setups.
    Behaves like a professional market analyst - provides entry, stop loss,
    take profits, risk/reward, and trade management recommendations.
    """
    
    def __init__(self, settings: Optional[SignalSettings] = None):
        """Initialize the signal generator."""
        # Use provided settings or default
        self.settings = settings if settings else SignalSettings()
        
        # Cache (symbol + timeframe -> result)
        self._cache: dict = {}
        self._cache_ttl = 60  # 60 seconds cache TTL
        
        # Statistics
        self._signals_generated = 0
        self._buy_signals = 0
        self._sell_signals = 0
        self._wait_signals = 0
        self._expired_signals = 0
        self._total_confidence = 0.0
        self._total_rr = 0.0
        self._total_generation_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._signal_counter = 0
    
    def generate_signal(
        self,
        symbol: str,
        timeframe: str,
        ai_decision: AIDecisionResult,
        trend_result: Optional[TrendResult] = None,
        structure_result: Optional[MarketStructureResult] = None,
        indicator_result: Optional[IndicatorResponse] = None,
        signal_score_result: Optional[SignalScoreResult] = None,
        current_price: Optional[float] = None,
        candles: Optional[List[Any]] = None
    ) -> TradeSetup:
        """
        Generate complete trade setup from AI decision.
        
        Args:
            symbol: Instrument symbol
            timeframe: Timeframe analyzed
            ai_decision: AI decision result
            trend_result: Trend analysis result
            structure_result: Market structure result
            indicator_result: Indicator analysis result
            signal_score_result: Signal score result
            current_price: Current market price
            candles: Historical & live candles for candlestick pattern recognition
            
        Returns:
            TradeSetup with complete trading recommendation
        """
        start_time = time.time()
        
        # Create cache key
        cache_key = f"{symbol}_{timeframe}"
        
        # Check cache
        if cache_key in self._cache:
            cached_result, cache_time = self._cache[cache_key]
            if (datetime.now(timezone.utc) - cache_time).total_seconds() < self._cache_ttl:
                self._cache_hits += 1
                return cached_result
        
        self._cache_misses += 1
        
        # Determine signal type from AI decision
        signal_type = self._map_decision_to_signal_type(ai_decision.decision)

        # ── Institutional Candlestick Pattern Recognition ────────────
        detected_patterns = []
        pattern_notes = []
        if candles and len(candles) >= 2:
            detected_patterns = candlestick_pattern_engine.analyze_patterns(
                candles, symbol=symbol, timeframe=timeframe, current_live_price=current_price
            )
            for p in detected_patterns[:2]:
                pattern_notes.append(f"{p.pattern_name} ({p.confidence:.0f}%)")

        if detected_patterns:
            top_p = detected_patterns[0]
            if signal_type == SignalType.BUY and top_p.bias == PatternBias.BULLISH:
                ai_decision.confidence = min(98.0, max(ai_decision.confidence, top_p.confidence))
            elif signal_type == SignalType.SELL and top_p.bias == PatternBias.BEARISH:
                ai_decision.confidence = min(98.0, max(ai_decision.confidence, top_p.confidence))
            elif signal_type == SignalType.WAIT and top_p.confidence >= 85.0:
                if top_p.bias == PatternBias.BULLISH:
                    signal_type = SignalType.BUY
                    ai_decision.confidence = top_p.confidence
                elif top_p.bias == PatternBias.BEARISH:
                    signal_type = SignalType.SELL
                    ai_decision.confidence = top_p.confidence
        
        # Generate signal ID
        signal_id = self._generate_signal_id()
        
        # Calculate entry price
        entry_price = self._calculate_entry_price(
            signal_type, structure_result, indicator_result, current_price
        )
        
        # Calculate stop loss
        stop_loss = self._calculate_stop_loss(
            signal_type, entry_price, structure_result, indicator_result
        )
        
        # Calculate take profits
        tp1, tp2, tp3 = self._calculate_take_profits(
            signal_type, entry_price, stop_loss, structure_result, indicator_result
        )
        
        # Calculate risk/reward ratio
        rr_ratio = self._calculate_risk_reward(entry_price, stop_loss, tp1)
        
        # Reject if RR below minimum (from settings)
        if rr_ratio < self.settings.minimum_rr:
            # Return WAIT signal instead
            signal_type = SignalType.WAIT
            entry_price = current_price if current_price else 0.0
            stop_loss = entry_price
            tp1, tp2, tp3 = None, None, None
            rr_ratio = 0.0
        
        # Calculate expected hold time
        expected_hold_time = self._calculate_hold_time(timeframe)
        
        # Calculate expiration time
        expires_at = self._calculate_expiration(timeframe)
        
        # Generate trade management recommendations
        trade_management = self._generate_trade_management()
        
        # Update statistics
        execution_time = (time.time() - start_time) * 1000
        self._signals_generated += 1
        self._total_confidence += ai_decision.confidence
        self._total_rr += rr_ratio
        self._total_generation_time += execution_time
        
        if signal_type == SignalType.BUY:
            self._buy_signals += 1
        elif signal_type == SignalType.SELL:
            self._sell_signals += 1
        else:
            self._wait_signals += 1
        
        # Include candlestick pattern notes in reasoning
        final_reasoning = ai_decision.reasoning
        if pattern_notes:
            final_reasoning = f"{final_reasoning} | Candlestick Trigger: {', '.join(pattern_notes)}"

        # Create result
        result = TradeSetup(
            signalId=signal_id,
            symbol=symbol,
            timeframe=timeframe,
            signalType=signal_type,
            entryPrice=entry_price,
            stopLoss=stop_loss,
            takeProfit1=tp1,
            takeProfit2=tp2,
            takeProfit3=tp3,
            riskRewardRatio=rr_ratio,
            confidence=ai_decision.confidence,
            quality=signal_score_result.quality if signal_score_result else "UNKNOWN",
            expectedHoldTime=expected_hold_time,
            status=SignalStatus.ACTIVE,
            decision=ai_decision.decision.value,
            reasoning=final_reasoning,
            warnings=ai_decision.warnings,
            tradeManagement=trade_management,
            generatedAt=datetime.now(timezone.utc),
            expiresAt=expires_at
        )
        
        # Update cache
        self._cache[cache_key] = (result, datetime.now(timezone.utc))
        
        return result
    
    def _map_decision_to_signal_type(self, decision: DecisionType) -> SignalType:
        """Map AI decision to signal type."""
        if decision == DecisionType.STRONG_BUY or decision == DecisionType.BUY:
            return SignalType.BUY
        elif decision == DecisionType.STRONG_SELL or decision == DecisionType.SELL:
            return SignalType.SELL
        elif decision == DecisionType.WAIT:
            return SignalType.WAIT
        else:
            return SignalType.NONE
    
    def _generate_signal_id(self) -> str:
        """Generate unique signal ID."""
        self._signal_counter += 1
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        counter_str = str(self._signal_counter).zfill(6)
        return f"SIG-{date_str}-{counter_str}"
    
    def _calculate_entry_price(
        self,
        signal_type: SignalType,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse],
        current_price: Optional[float]
    ) -> float:
        """Calculate entry price based on signal type and market conditions."""
        if signal_type == SignalType.WAIT or signal_type == SignalType.NONE:
            return current_price if current_price else 0.0
        
        # Use current price as base
        base_price = current_price if current_price else (
            indicator_result.bb_middle if indicator_result else 0.0
        )
        
        if signal_type == SignalType.BUY:
            # For BUY: prefer demand zone or EMA20 retracement
            if structure_result and structure_result.activeDemandZones:
                # Use nearest demand zone
                nearest_zone = min(structure_result.activeDemandZones, key=lambda x: abs(x - base_price))
                return nearest_zone
            elif indicator_result and indicator_result.ema_20:
                # Retracement to EMA20
                return indicator_result.ema_20
            else:
                # Break and retest - use current price
                return base_price
        else:  # SELL
            # For SELL: prefer supply zone or EMA20 retracement
            if structure_result and structure_result.activeSupplyZones:
                # Use nearest supply zone
                nearest_zone = min(structure_result.activeSupplyZones, key=lambda x: abs(x - base_price))
                return nearest_zone
            elif indicator_result and indicator_result.ema_20:
                # Retracement to EMA20
                return indicator_result.ema_20
            else:
                # Break and retest - use current price
                return base_price
    
    def _calculate_stop_loss(
        self,
        signal_type: SignalType,
        entry_price: float,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> float:
        """Calculate stop loss using ATR, swing, and liquidity level."""
        atr = indicator_result.atr_14 if indicator_result else 0.0
        
        if signal_type == SignalType.BUY:
            # For BUY: SL below entry
            atr_sl = entry_price - (atr * 1.5) if atr > 0 else entry_price * 0.99
            
            # Check for swing lows
            swing_sl = atr_sl  # Default to ATR SL
            if structure_result and structure_result.swingLows and len(structure_result.swingLows) > 0:
                nearest_swing = min(structure_result.swingLows, key=lambda x: abs(x.price - entry_price))
                swing_sl = nearest_swing.price
            
            # Check for liquidity level
            liquidity_sl = atr_sl  # Default to ATR SL
            if structure_result and structure_result.support and len(structure_result.support) > 0:
                nearest_support = min(structure_result.support, key=lambda x: abs(x - entry_price))
                liquidity_sl = nearest_support
            
            # Choose safest (lowest) SL
            sl_candidates = [atr_sl]
            if structure_result and structure_result.swingLows and len(structure_result.swingLows) > 0:
                sl_candidates.append(swing_sl)
            if structure_result and structure_result.support and len(structure_result.support) > 0:
                sl_candidates.append(liquidity_sl)
            
            return min(sl_candidates)
        else:  # SELL
            # For SELL: SL above entry
            atr_sl = entry_price + (atr * 1.5) if atr > 0 else entry_price * 1.01
            
            # Check for swing highs
            swing_sl = atr_sl  # Default to ATR SL
            if structure_result and structure_result.swingHighs and len(structure_result.swingHighs) > 0:
                nearest_swing = min(structure_result.swingHighs, key=lambda x: abs(x.price - entry_price))
                swing_sl = nearest_swing.price
            
            # Check for liquidity level
            liquidity_sl = atr_sl  # Default to ATR SL
            if structure_result and structure_result.resistance and len(structure_result.resistance) > 0:
                nearest_resistance = min(structure_result.resistance, key=lambda x: abs(x - entry_price))
                liquidity_sl = nearest_resistance
            
            # Choose safest (highest) SL
            sl_candidates = [atr_sl]
            if structure_result and structure_result.swingHighs and len(structure_result.swingHighs) > 0:
                sl_candidates.append(swing_sl)
            if structure_result and structure_result.resistance and len(structure_result.resistance) > 0:
                sl_candidates.append(liquidity_sl)
            
            return max(sl_candidates)
    
    def _calculate_take_profits(
        self,
        signal_type: SignalType,
        entry_price: float,
        stop_loss: float,
        structure_result: Optional[MarketStructureResult],
        indicator_result: Optional[IndicatorResponse]
    ) -> tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate TP1, TP2, TP3 using resistance levels, liquidity targets, and ATR expansion."""
        atr = indicator_result.atr_14 if indicator_result else 0.0
        risk = abs(entry_price - stop_loss)
        
        if signal_type == SignalType.BUY:
            # For BUY: TPs above entry
            # TP1: 1.5x risk
            tp1 = entry_price + (risk * 1.5)
            
            # TP2: 2.5x risk or nearest resistance
            tp2 = entry_price + (risk * 2.5)
            if structure_result and structure_result.resistance:
                nearest_resistance = min(structure_result.resistance, key=lambda x: abs(x - entry_price))
                if nearest_resistance > entry_price:
                    tp2 = min(tp2, nearest_resistance)
            
            # TP3: 4x risk or ATR expansion
            tp3 = entry_price + (risk * 4.0)
            if atr > 0:
                atr_tp3 = entry_price + (atr * 3.0)
                tp3 = max(tp3, atr_tp3)
        else:  # SELL
            # For SELL: TPs below entry
            # TP1: 1.5x risk
            tp1 = entry_price - (risk * 1.5)
            
            # TP2: 2.5x risk or nearest support
            tp2 = entry_price - (risk * 2.5)
            if structure_result and structure_result.support:
                nearest_support = min(structure_result.support, key=lambda x: abs(x - entry_price))
                if nearest_support < entry_price:
                    tp2 = max(tp2, nearest_support)
            
            # TP3: 4x risk or ATR expansion
            tp3 = entry_price - (risk * 4.0)
            if atr > 0:
                atr_tp3 = entry_price - (atr * 3.0)
                tp3 = min(tp3, atr_tp3)
        
        return tp1, tp2, tp3
    
    def _calculate_risk_reward(
        self,
        entry_price: float,
        stop_loss: float,
        take_profit: Optional[float]
    ) -> float:
        """Calculate risk/reward ratio."""
        if not take_profit or take_profit == entry_price:
            return 0.0
        
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)
        
        if risk == 0:
            return 0.0
        
        return round(reward / risk, 2)
    
    def _calculate_hold_time(self, timeframe: str) -> str:
        """Calculate expected hold time based on timeframe."""
        hold_times = {
            "M1": "15 Minutes",
            "M5": "30 Minutes",
            "M15": "2 Hours",
            "M30": "4 Hours",
            "H1": "8 Hours",
            "H4": "2 Days",
            "D1": "7 Days"
        }
        return hold_times.get(timeframe, "4 Hours")
    
    def _calculate_expiration(self, timeframe: str) -> datetime:
        """Calculate signal expiration time."""
        expiration_hours = {
            "M1": 0.5,
            "M5": 2,
            "M15": 8,
            "M30": 12,
            "H1": 24,
            "H4": 48,
            "D1": 168
        }
        hours = expiration_hours.get(timeframe, 8)
        return datetime.now(timezone.utc) + timedelta(hours=hours)
    
    def _generate_trade_management(self) -> TradeManagement:
        """Generate trade management recommendations."""
        return TradeManagement(
            moveStopToBreakevenAt="TP1",
            partialCloseAtTP1=50,
            partialCloseAtTP2=30,
            leaveRunner=20
        )
    
    def get_statistics(self) -> dict:
        """Get generator statistics."""
        avg_confidence = (
            self._total_confidence / self._signals_generated
            if self._signals_generated > 0
            else 0.0
        )
        
        avg_rr = (
            self._total_rr / self._signals_generated
            if self._signals_generated > 0
            else 0.0
        )
        
        avg_generation_time = (
            self._total_generation_time / self._signals_generated
            if self._signals_generated > 0
            else 0.0
        )
        
        return {
            'signalsGenerated': self._signals_generated,
            'buySignals': self._buy_signals,
            'sellSignals': self._sell_signals,
            'waitSignals': self._wait_signals,
            'expiredSignals': self._expired_signals,
            'averageConfidence': round(avg_confidence, 2),
            'averageRR': round(avg_rr, 2),
            'averageGenerationTime': round(avg_generation_time, 2),
            'cacheHits': self._cache_hits,
            'cacheMisses': self._cache_misses
        }
    
    def reset_statistics(self) -> None:
        """Reset generator statistics."""
        self._signals_generated = 0
        self._buy_signals = 0
        self._sell_signals = 0
        self._wait_signals = 0
        self._expired_signals = 0
        self._total_confidence = 0.0
        self._total_rr = 0.0
        self._total_generation_time = 0.0
        self._cache_hits = 0
        self._cache_misses = 0
        self._signal_counter = 0
        self._cache.clear()
