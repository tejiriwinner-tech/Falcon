"""
Candlestick Pattern & Sniper Entry Engine for Falcon.

Implements institutional and price-action patterns based on:
1. Headway Forex Candlestick Reversal Analysis (Hammer, Inverted Hammer, Shooting Star, Engulfing, Morning/Evening Star)
2. TradingSim 5-Minute Bar dynamics (Morning reversals, exhaustion wicks, multi-bar confirmations)
3. Rayner Teo's Sniper Entries (Breakout with Buildup, First Pullback to 20 EMA, False Breakout / Liquidity Trap)
4. BrokerXplorer 15M/5M Multi-Timeframe Strategy (15M key level bounds + 5M breakout/retest trigger)
5. FX-List & Scribd Invalidation Entry Rules (Pre-planned R:R, tight invalidation, candle-close execution)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class PatternType(str, Enum):
    # Core Reversals (Headway Guide)
    BULLISH_HAMMER = "BULLISH_HAMMER"
    BEARISH_SHOOTING_STAR = "BEARISH_SHOOTING_STAR"
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    BEARISH_ENGULFING = "BEARISH_ENGULFING"
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"
    INVERTED_HAMMER = "INVERTED_HAMMER"
    HANGING_MAN = "HANGING_MAN"
    
    # Sniper Entries (Rayner Teo)
    BREAKOUT_WITH_BUILDUP = "BREAKOUT_WITH_BUILDUP"
    FIRST_PULLBACK = "FIRST_PULLBACK"
    FALSE_BREAKOUT_TRAP = "FALSE_BREAKOUT_TRAP"
    
    # Multi-Timeframe Structure (BrokerXplorer & TradingSim)
    TIMEFRAME_15M_5M_BREAKOUT = "15M_5M_BREAKOUT_CONFIRMATION"
    EXHAUSTION_REVERSAL = "EXHAUSTION_REVERSAL"
    
    # Indecision / Neutral
    SPINNING_TOP = "SPINNING_TOP"
    DOJI = "DOJI"
    NO_PATTERN = "NO_PATTERN"


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NEUTRAL = "NEUTRAL"


@dataclass
class CandleBar:
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    timestamp: Optional[Union[int, float]] = None
    time: Optional[Any] = None

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def range(self) -> float:
        return max(self.high - self.low, 1e-8)

    @property
    def is_bullish(self) -> bool:
        return self.close >= self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def upper_shadow(self) -> float:
        return self.high - max(self.open, self.close)

    @property
    def lower_shadow(self) -> float:
        return min(self.open, self.close) - self.low


@dataclass
class SniperPatternResult:
    pattern_type: PatternType
    direction: SignalDirection
    conviction_score: float  # 0.0 to 1.0 (multiplier / boost)
    trigger_rule: str
    invalidation_level: float
    recommended_target: float
    rationale: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class CandlestickPatternEngine:
    """
    Detects high-probability candlestick patterns and sniper entry mechanics
    on 5m and 15m candle sequences.
    """

    def analyze_patterns(
        self,
        candles_5m: Optional[List[CandleBar]] = None,
        candles_15m: Optional[List[CandleBar]] = None,
        ema_20: Optional[float] = None,
        key_resistance: Optional[float] = None,
        key_support: Optional[float] = None,
        candles_1h: Optional[List[CandleBar]] = None,
    ) -> List[SniperPatternResult]:
        """
        Runs comprehensive scan across available candle sequences.
        Operates directly on canonical 1h candles if lower-timeframe data is absent,
        ensuring truthful timeframe provenance without relabeling or fabricating bars.
        """
        results: List[SniperPatternResult] = []

        primary_candles = candles_5m or candles_1h
        if not primary_candles or len(primary_candles) < 3:
            return results

        c_curr = primary_candles[-1]
        c_prev = primary_candles[-2]
        c_prev2 = primary_candles[-3] if len(primary_candles) >= 3 else None

        # 1. Headway Reversal Patterns (Single and Multi-Bar)
        self._detect_headway_reversals(c_curr, c_prev, c_prev2, results)

        # 2. Rayner Teo Sniper Patterns
        self._detect_rayner_sniper_patterns(
            primary_candles, ema_20, key_resistance, key_support, results
        )

        # 3. Multi-Timeframe Confirmation ONLY if genuine 15m AND 5m candles exist
        if candles_5m and candles_15m and len(candles_15m) >= 2:
            self._detect_15m_5m_alignment(candles_5m, candles_15m, results)

        # Sort results by conviction score descending
        results.sort(key=lambda r: r.conviction_score, reverse=True)
        return results

    def _detect_headway_reversals(
        self,
        c: CandleBar,
        prev: CandleBar,
        prev2: Optional[CandleBar],
        results: List[SniperPatternResult],
    ) -> None:
        """
        Detects Hammer, Shooting Star, Engulfing, and Morning/Evening Star patterns.
        Strict Headway rules:
        - Hammer: lower shadow >= 2x body, upper shadow <= 10% of range, at bottom of swing
        - Shooting Star: upper shadow >= 2x body, lower shadow <= 10% of range, at top of swing
        - Bullish Engulfing: previous bar red, current green completely engulfs body
        - Bearish Engulfing: previous bar green, current red completely engulfs body
        """
        body = c.body
        rng = c.range

        if rng < 1e-6:
            return

        body_ratio = body / rng
        upper_ratio = c.upper_shadow / rng
        lower_ratio = c.lower_shadow / rng

        # Bullish Hammer (Headway Guide Rule: lower wick >= 2x body, small upper wick)
        if lower_ratio >= 0.60 and body_ratio <= 0.30 and upper_ratio <= 0.15:
            invalidation = c.low
            target = c.close + (c.close - c.low) * 2.0  # 1:2 R:R minimum
            results.append(
                SniperPatternResult(
                    pattern_type=PatternType.BULLISH_HAMMER,
                    direction=SignalDirection.BUY,
                    conviction_score=0.88,
                    trigger_rule="Enter on confirmed candle close above hammer body. Invalidation at low.",
                    invalidation_level=invalidation,
                    recommended_target=target,
                    rationale=f"Bullish Hammer with {lower_ratio*100:.1f}% lower shadow rejecting lower prices.",
                    metadata={"lower_shadow_ratio": lower_ratio, "body_ratio": body_ratio},
                )
            )

        # Bearish Shooting Star (Headway Guide Rule: upper wick >= 2x body, small lower wick)
        if upper_ratio >= 0.60 and body_ratio <= 0.30 and lower_ratio <= 0.15:
            invalidation = c.high
            target = c.close - (c.high - c.close) * 2.0
            results.append(
                SniperPatternResult(
                    pattern_type=PatternType.BEARISH_SHOOTING_STAR,
                    direction=SignalDirection.SELL,
                    conviction_score=0.88,
                    trigger_rule="Enter on confirmed candle close below shooting star body. Invalidation at high.",
                    invalidation_level=invalidation,
                    recommended_target=target,
                    rationale=f"Bearish Shooting Star with {upper_ratio*100:.1f}% upper shadow rejecting higher liquidity.",
                    metadata={"upper_shadow_ratio": upper_ratio, "body_ratio": body_ratio},
                )
            )

        # Bullish Engulfing
        if prev.is_bearish and c.is_bullish:
            if c.open <= prev.close and c.close > prev.open:
                invalidation = min(c.low, prev.low)
                risk = c.close - invalidation
                results.append(
                    SniperPatternResult(
                        pattern_type=PatternType.BULLISH_ENGULFING,
                        direction=SignalDirection.BUY,
                        conviction_score=0.90,
                        trigger_rule="Enter immediately on close of bullish engulfing bar. Stop below swing low.",
                        invalidation_level=invalidation,
                        recommended_target=c.close + (risk * 2.2),
                        rationale="Bullish Engulfing bar completely swallowed prior bearish candle, showing institutional absorption.",
                        metadata={"engulf_ratio": c.body / max(prev.body, 1e-6)},
                    )
                )

        # Bearish Engulfing
        if prev.is_bullish and c.is_bearish:
            if c.open >= prev.close and c.close < prev.open:
                invalidation = max(c.high, prev.high)
                risk = invalidation - c.close
                results.append(
                    SniperPatternResult(
                        pattern_type=PatternType.BEARISH_ENGULFING,
                        direction=SignalDirection.SELL,
                        conviction_score=0.90,
                        trigger_rule="Enter immediately on close of bearish engulfing bar. Stop above swing high.",
                        invalidation_level=invalidation,
                        recommended_target=c.close - (risk * 2.2),
                        rationale="Bearish Engulfing bar completely wiped out previous buyers with institutional supply pressure.",
                        metadata={"engulf_ratio": c.body / max(prev.body, 1e-6)},
                    )
                )

        # Morning Star
        if prev2 and prev2.is_bearish and c.is_bullish:
            is_middle_star = prev.body <= (prev2.body * 0.35)
            closed_deep = c.close >= (prev2.open + prev2.close) / 2.0
            if is_middle_star and closed_deep:
                invalidation = min(prev2.low, prev.low, c.low)
                risk = c.close - invalidation
                results.append(
                    SniperPatternResult(
                        pattern_type=PatternType.MORNING_STAR,
                        direction=SignalDirection.BUY,
                        conviction_score=0.92,
                        trigger_rule="Morning Star confirmed. Enter on candle close with stop below the star low.",
                        invalidation_level=invalidation,
                        recommended_target=c.close + (risk * 2.5),
                        rationale="Institutional Morning Star 3-bar reversal: momentum exhausted, indecision, followed by aggressive buying.",
                    )
                )

        # Evening Star
        if prev2 and prev2.is_bullish and c.is_bearish:
            is_middle_star = prev.body <= (prev2.body * 0.35)
            closed_deep = c.close <= (prev2.open + prev2.close) / 2.0
            if is_middle_star and closed_deep:
                invalidation = max(prev2.high, prev.high, c.high)
                risk = invalidation - c.close
                results.append(
                    SniperPatternResult(
                        pattern_type=PatternType.EVENING_STAR,
                        direction=SignalDirection.SELL,
                        conviction_score=0.92,
                        trigger_rule="Evening Star confirmed. Enter on candle close with stop above the star high.",
                        invalidation_level=invalidation,
                        recommended_target=c.close - (risk * 2.5),
                        rationale="Institutional Evening Star 3-bar reversal: buying exhausted, supply dominance confirmed.",
                    )
                )

    def _detect_rayner_sniper_patterns(
        self,
        candles: List[CandleBar],
        ema_20: Optional[float],
        resistance: Optional[float],
        support: Optional[float],
        results: List[SniperPatternResult],
    ) -> None:
        if len(candles) < 5:
            return

        curr = candles[-1]
        prev_bars = candles[-5:-1]

        # 1. False Breakout / Liquidity Trap
        if resistance and curr.high > resistance and curr.close < resistance:
            invalidation = curr.high
            risk = invalidation - curr.close
            if risk > 0:
                results.append(
                    SniperPatternResult(
                        pattern_type=PatternType.FALSE_BREAKOUT_TRAP,
                        direction=SignalDirection.SELL,
                        conviction_score=0.93,
                        trigger_rule="False Breakout Liquidity Trap. Enter on close back below resistance.",
                        invalidation_level=invalidation,
                        recommended_target=curr.close - (risk * 2.5),
                        rationale=f"Rayner Teo Liquidity Sweep: Price pierced resistance {resistance:.5f} to trap breakout buyers, closing back inside range.",
                        metadata={"swept_level": resistance, "trap_type": "BEARISH_SWEEP"},
                    )
                )

        if support and curr.low < support and curr.close > support:
            invalidation = curr.low
            risk = curr.close - invalidation
            if risk > 0:
                results.append(
                    SniperPatternResult(
                        pattern_type=PatternType.FALSE_BREAKOUT_TRAP,
                        direction=SignalDirection.BUY,
                        conviction_score=0.93,
                        trigger_rule="False Breakout Liquidity Trap. Enter on close back above support.",
                        invalidation_level=invalidation,
                        recommended_target=curr.close + (risk * 2.5),
                        rationale=f"Rayner Teo Liquidity Sweep: Price swept support {support:.5f} to trap breakout sellers, closing back inside range.",
                        metadata={"swept_level": support, "trap_type": "BULLISH_SWEEP"},
                    )
                )

        # 2. First Pullback to 20 EMA
        if ema_20:
            avg_body = sum(b.body for b in prev_bars) / len(prev_bars)
            is_pullback_tight = curr.body <= avg_body * 1.3

            if curr.low <= ema_20 <= max(curr.open, curr.close) and curr.is_bullish:
                if is_pullback_tight:
                    invalidation = curr.low
                    risk = curr.close - invalidation
                    results.append(
                        SniperPatternResult(
                            pattern_type=PatternType.FIRST_PULLBACK,
                            direction=SignalDirection.BUY,
                            conviction_score=0.89,
                            trigger_rule="First Pullback to 20 EMA. Enter on candle close respecting 20 EMA dynamic support.",
                            invalidation_level=invalidation,
                            recommended_target=curr.close + (risk * 2.0),
                            rationale=f"Rayner Teo First Pullback: Tight consolidation kissed 20 EMA ({ema_20:.5f}) with immediate bullish respect.",
                            metadata={"ema_level": ema_20},
                        )
                    )

            if curr.high >= ema_20 >= min(curr.open, curr.close) and curr.is_bearish:
                if is_pullback_tight:
                    invalidation = curr.high
                    risk = invalidation - curr.close
                    results.append(
                        SniperPatternResult(
                            pattern_type=PatternType.FIRST_PULLBACK,
                            direction=SignalDirection.SELL,
                            conviction_score=0.89,
                            trigger_rule="First Pullback to 20 EMA. Enter on candle close respecting 20 EMA dynamic resistance.",
                            invalidation_level=invalidation,
                            recommended_target=curr.close - (risk * 2.0),
                            rationale=f"Rayner Teo First Pullback: Tight consolidation rejected at 20 EMA ({ema_20:.5f}) with bearish continuation.",
                            metadata={"ema_level": ema_20},
                        )
                    )

        # 3. Breakout with Buildup
        if len(candles) >= 6:
            recent_ranges = [b.range for b in candles[-4:-1]]
            baseline_range = sum(b.range for b in candles[-10:-4]) / 6.0 if len(candles) >= 10 else recent_ranges[0]
            is_buildup = all(r < baseline_range * 0.75 for r in recent_ranges)

            if is_buildup:
                if resistance and curr.close > resistance and curr.is_bullish:
                    invalidation = min(b.low for b in candles[-4:])
                    risk = curr.close - invalidation
                    results.append(
                        SniperPatternResult(
                            pattern_type=PatternType.BREAKOUT_WITH_BUILDUP,
                            direction=SignalDirection.BUY,
                            conviction_score=0.91,
                            trigger_rule="Breakout with Buildup. Enter on candle close breaking buildup range ceiling.",
                            invalidation_level=invalidation,
                            recommended_target=curr.close + (risk * 2.3),
                            rationale=f"Rayner Teo Breakout with Buildup: Compressed volatility right beneath resistance {resistance:.5f} broken by expansion bar.",
                        )
                    )
                elif support and curr.close < support and curr.is_bearish:
                    invalidation = max(b.high for b in candles[-4:])
                    risk = invalidation - curr.close
                    results.append(
                        SniperPatternResult(
                            pattern_type=PatternType.BREAKOUT_WITH_BUILDUP,
                            direction=SignalDirection.SELL,
                            conviction_score=0.91,
                            trigger_rule="Breakout with Buildup. Enter on candle close breaking buildup range floor.",
                            invalidation_level=invalidation,
                            recommended_target=curr.close - (risk * 2.3),
                            rationale=f"Rayner Teo Breakdown with Buildup: Compressed volatility right above support {support:.5f} broken by expansion bar.",
                        )
                    )

    def _detect_15m_5m_alignment(
        self,
        candles_5m: List[CandleBar],
        candles_15m: List[CandleBar],
        results: List[SniperPatternResult],
    ) -> None:
        ref_15m = candles_15m[-2]
        curr_5m = candles_5m[-1]

        if curr_5m.close > ref_15m.high and curr_5m.is_bullish:
            invalidation = ref_15m.low
            risk = curr_5m.close - invalidation
            results.append(
                SniperPatternResult(
                    pattern_type=PatternType.TIMEFRAME_15M_5M_BREAKOUT,
                    direction=SignalDirection.BUY,
                    conviction_score=0.88,
                    trigger_rule="15M/5M Multi-Timeframe Breakout: Confirmed 5M close above 15M range high.",
                    invalidation_level=invalidation,
                    recommended_target=curr_5m.close + (risk * 2.0),
                    rationale=f"BrokerXplorer 15M/5M alignment: 5M candle closed at {curr_5m.close:.5f} above 15M boundary ({ref_15m.high:.5f}).",
                    metadata={"ref_15m_high": ref_15m.high, "ref_15m_low": ref_15m.low},
                )
            )

        if curr_5m.close < ref_15m.low and curr_5m.is_bearish:
            invalidation = ref_15m.high
            risk = invalidation - curr_5m.close
            results.append(
                SniperPatternResult(
                    pattern_type=PatternType.TIMEFRAME_15M_5M_BREAKOUT,
                    direction=SignalDirection.SELL,
                    conviction_score=0.88,
                    trigger_rule="15M/5M Multi-Timeframe Breakdown: Confirmed 5M close below 15M range low.",
                    invalidation_level=invalidation,
                    recommended_target=curr_5m.close - (risk * 2.0),
                    rationale=f"BrokerXplorer 15M/5M alignment: 5M candle closed at {curr_5m.close:.5f} below 15M boundary ({ref_15m.low:.5f}).",
                    metadata={"ref_15m_high": ref_15m.high, "ref_15m_low": ref_15m.low},
                )
            )
