"""
Falcon Institutional Candlestick Pattern Recognition Engine
Implements deterministic, algorithmic pattern detection across single, double,
triple, and multi-candle formations with Smart Money Concepts (SMC) integration.
"""
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math


class PatternBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class PatternCategory(str, Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    CHART = "CHART"


@dataclass
class CandlestickPatternResult:
    """Detected candlestick pattern with analytical details."""
    pattern_name: str
    bias: PatternBias
    category: PatternCategory
    confidence: float  # 0.0 to 100.0
    quality_score: float  # 0.0 to 1.0
    description: str
    recommended_action: str  # "BUY", "SELL", "WAIT"
    suggested_entry: float
    suggested_stop_loss: float
    suggested_take_profit: float
    risk_reward_ratio: float
    candle_index: int
    timestamp: Optional[datetime] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)


class CandlestickPatternEngine:
    """
    High-precision Candlestick and Price Action Pattern Recognition Engine.
    Evaluates raw OHLCV candle streams and outputs deterministic pattern artifacts.
    """

    def __init__(self):
        self.version = "1.0.0"

    # ──────────────────────────────────────────────────────────────────
    # Core Public Detection Method
    # ──────────────────────────────────────────────────────────────────

    def analyze_patterns(
        self,
        candles: List[Any],
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        current_live_price: Optional[float] = None
    ) -> List[CandlestickPatternResult]:
        """
        Scan a list of OHLCV candles (ordered oldest to newest) for all reference patterns.
        Returns a list of detected patterns sorted by confidence descending.
        """
        if not candles or len(candles) < 3:
            return []

        detected_patterns: List[CandlestickPatternResult] = []

        # Extract latest 3-5 candles for recent pattern formation
        c_curr = candles[-1]
        c_prev = candles[-2]
        c_prev2 = candles[-3] if len(candles) >= 3 else None

        # 1. Single-Candle Patterns (on latest 3 candles)
        for i in range(max(0, len(candles) - 3), len(candles)):
            self._detect_single_candle_patterns(candles[i], i, symbol, detected_patterns, current_live_price)

        # 2. Two-Candle Patterns (check recent pairs)
        for i in range(max(1, len(candles) - 3), len(candles)):
            self._detect_two_candle_patterns(candles[i-1], candles[i], i, symbol, detected_patterns, current_live_price)

        # 3. Three-Candle Patterns (check recent triples)
        for i in range(max(2, len(candles) - 3), len(candles)):
            self._detect_three_candle_patterns(candles[i-2], candles[i-1], candles[i], i, symbol, detected_patterns, current_live_price)

        # 4. Multi-Candle / Classical Chart Formations
        if len(candles) >= 10:
            self._detect_chart_patterns(candles, symbol, detected_patterns, current_live_price)

        # Sort patterns by quality score / confidence
        detected_patterns.sort(key=lambda p: p.confidence, reverse=True)
        return detected_patterns

    # ──────────────────────────────────────────────────────────────────
    # Single-Candle Pattern Detectors
    # ──────────────────────────────────────────────────────────────────

    def _detect_single_candle_patterns(
        self,
        c: Any,
        idx: int,
        symbol: str,
        results: List[CandlestickPatternResult],
        live_price: Optional[float]
    ) -> None:
        o, h, l, cl = self._get_ohlc(c)
        rng = max(h - l, 1e-6)
        body = abs(cl - o)
        upper_wick = h - max(o, cl)
        lower_wick = min(o, cl) - l
        is_bullish = cl >= o

        # Doji (Dragonfly, Gravestone, Standard)
        if body / rng <= 0.08:
            if lower_wick / rng >= 0.65 and upper_wick / rng <= 0.15:
                results.append(self._build_result(
                    "Dragonfly Doji", PatternBias.BULLISH, PatternCategory.SINGLE,
                    confidence=82.0, quality=0.85,
                    desc="Bullish rejection of lower prices; strong buying demand pushed price back to open.",
                    action="BUY", entry=cl, sl=l - (0.1 * rng), tp=cl + (1.5 * rng),
                    idx=idx, symbol=symbol, live_price=live_price
                ))
            elif upper_wick / rng >= 0.65 and lower_wick / rng <= 0.15:
                results.append(self._build_result(
                    "Gravestone Doji", PatternBias.BEARISH, PatternCategory.SINGLE,
                    confidence=82.0, quality=0.85,
                    desc="Bearish rejection of higher prices; sellers overwhelmed buyers into close.",
                    action="SELL", entry=cl, sl=h + (0.1 * rng), tp=cl - (1.5 * rng),
                    idx=idx, symbol=symbol, live_price=live_price
                ))
            else:
                results.append(self._build_result(
                    "Doji", PatternBias.NEUTRAL, PatternCategory.SINGLE,
                    confidence=70.0, quality=0.70,
                    desc="Market equilibrium & indecision candle; high probability of impending breakout.",
                    action="WAIT", entry=cl, sl=l, tp=h,
                    idx=idx, symbol=symbol, live_price=live_price
                ))

        # Hammer / Hanging Man (Long lower shadow, small upper body)
        elif lower_wick >= (1.9 * body) and upper_wick <= (0.25 * rng):
            if is_bullish:
                results.append(self._build_result(
                    "Hammer", PatternBias.BULLISH, PatternCategory.SINGLE,
                    confidence=86.0, quality=0.88,
                    desc="Bullish pin bar / hammer rejecting key lows with aggressive buyback.",
                    action="BUY", entry=cl, sl=l - (0.05 * rng), tp=cl + (2.0 * rng),
                    idx=idx, symbol=symbol, live_price=live_price
                ))
            else:
                results.append(self._build_result(
                    "Hanging Man", PatternBias.BEARISH, PatternCategory.SINGLE,
                    confidence=78.0, quality=0.76,
                    desc="Bearish warning at highs; buyers failed to sustain the push after deep intra-candle dip.",
                    action="SELL", entry=cl, sl=h + (0.05 * rng), tp=cl - (2.0 * rng),
                    idx=idx, symbol=symbol, live_price=live_price
                ))

        # Inverted Hammer (Long upper shadow, small lower body)
        elif upper_wick >= (1.9 * body) and lower_wick <= (0.25 * rng):
            results.append(self._build_result(
                "Inverted Hammer", PatternBias.BULLISH, PatternCategory.SINGLE,
                confidence=79.0, quality=0.78,
                desc="Bullish bottom testing wick; upside liquidity probe anticipating trend shift.",
                action="BUY", entry=cl, sl=l - (0.05 * rng), tp=cl + (1.8 * rng),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # Marubozu (Huge body, near zero wicks)
        elif body / rng >= 0.88:
            if is_bullish:
                results.append(self._build_result(
                    "Bullish Marubozu", PatternBias.BULLISH, PatternCategory.SINGLE,
                    confidence=88.0, quality=0.90,
                    desc="Unrelenting institutional buying expansion with no upper/lower wick resistance.",
                    action="BUY", entry=cl, sl=o - (0.05 * rng), tp=cl + (2.0 * rng),
                    idx=idx, symbol=symbol, live_price=live_price
                ))
            else:
                results.append(self._build_result(
                    "Bearish Marubozu", PatternBias.BEARISH, PatternCategory.SINGLE,
                    confidence=88.0, quality=0.90,
                    desc="Dominant institutional selling expansion with no lower wick support.",
                    action="SELL", entry=cl, sl=o + (0.05 * rng), tp=cl - (2.0 * rng),
                    idx=idx, symbol=symbol, live_price=live_price
                ))

        # Spinning Top (Centered small body, symmetrical wicks)
        elif body / rng <= 0.35 and abs(upper_wick - lower_wick) / rng <= 0.25:
            pat_name = "Bullish Spinning Top" if is_bullish else "Bearish Spinning Top"
            bias = PatternBias.BULLISH if is_bullish else PatternBias.BEARISH
            results.append(self._build_result(
                pat_name, bias, PatternCategory.SINGLE,
                confidence=72.0, quality=0.72,
                desc="Volatility compression spinning top; precursor to directional expansion.",
                action="WAIT", entry=cl, sl=l, tp=h,
                idx=idx, symbol=symbol, live_price=live_price
            ))

    # ──────────────────────────────────────────────────────────────────
    # Two-Candle Pattern Detectors
    # ──────────────────────────────────────────────────────────────────

    def _detect_two_candle_patterns(
        self,
        c1: Any,
        c2: Any,
        idx: int,
        symbol: str,
        results: List[CandlestickPatternResult],
        live_price: Optional[float]
    ) -> None:
        o1, h1, l1, c1_val = self._get_ohlc(c1)
        o2, h2, l2, c2_val = self._get_ohlc(c2)

        rng1 = max(h1 - l1, 1e-6)
        rng2 = max(h2 - l2, 1e-6)
        body1 = abs(c1_val - o1)
        body2 = abs(c2_val - o2)

        is_c1_bearish = c1_val < o1
        is_c1_bullish = c1_val > o1
        is_c2_bullish = c2_val > o2
        is_c2_bearish = c2_val < o2

        # 1. Bullish Engulfing
        if is_c1_bearish and is_c2_bullish and o2 <= c1_val and c2_val >= o1:
            results.append(self._build_result(
                "Bullish Engulfing", PatternBias.BULLISH, PatternCategory.DOUBLE,
                confidence=91.0, quality=0.92,
                desc="Complete engulfment of prior bearish body by high-conviction bullish candle.",
                action="BUY", entry=c2_val, sl=min(l1, l2) - (0.1 * rng2), tp=c2_val + (2.0 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 2. Bearish Engulfing
        elif is_c1_bullish and is_c2_bearish and o2 >= c1_val and c2_val <= o1:
            results.append(self._build_result(
                "Bearish Engulfing", PatternBias.BEARISH, PatternCategory.DOUBLE,
                confidence=91.0, quality=0.92,
                desc="Complete engulfment of prior bullish body by dominant bearish candle.",
                action="SELL", entry=c2_val, sl=max(h1, h2) + (0.1 * rng2), tp=c2_val - (2.0 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 3. Bullish Kicker (Gap open & strong opposite direction)
        elif is_c1_bearish and is_c2_bullish and o2 >= o1 and c2_val > o2:
            results.append(self._build_result(
                "Bullish Kicker", PatternBias.BULLISH, PatternCategory.DOUBLE,
                confidence=89.0, quality=0.90,
                desc="Violent sentiment flip gap above prior open with sustained upward follow-through.",
                action="BUY", entry=c2_val, sl=l2, tp=c2_val + (2.5 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 4. Bearish Kicker
        elif is_c1_bullish and is_c2_bearish and o2 <= o1 and c2_val < o2:
            results.append(self._build_result(
                "Bearish Kicker", PatternBias.BEARISH, PatternCategory.DOUBLE,
                confidence=89.0, quality=0.90,
                desc="Violent sentiment flip gap below prior open with aggressive downward liquidation.",
                action="SELL", entry=c2_val, sl=h2, tp=c2_val - (2.5 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 5. Piercing Line (Bullish reversal into lower 50%+ of prior candle)
        elif is_c1_bearish and is_c2_bullish and o2 < l1 and c2_val >= (o1 + c1_val) / 2 and c2_val < o1:
            results.append(self._build_result(
                "Piercing Line", PatternBias.BULLISH, PatternCategory.DOUBLE,
                confidence=84.0, quality=0.85,
                desc="Bullish counter-attack penetrating more than 50% into prior bearish range.",
                action="BUY", entry=c2_val, sl=l2 - (0.05 * rng2), tp=c2_val + (1.8 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 6. Dark Cloud Cover (Bearish reversal into upper 50%+ of prior candle)
        elif is_c1_bullish and is_c2_bearish and o2 > h1 and c2_val <= (o1 + c1_val) / 2 and c2_val > o1:
            results.append(self._build_result(
                "Dark Cloud Cover", PatternBias.BEARISH, PatternCategory.DOUBLE,
                confidence=84.0, quality=0.85,
                desc="Bearish cloud cover driving deep below the 50% midpoint of the prior bullish candle.",
                action="SELL", entry=c2_val, sl=h2 + (0.05 * rng2), tp=c2_val - (1.8 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 7. Tweezer Bottom (Identical low rejections)
        elif abs(l1 - l2) / rng1 <= 0.05 and is_c1_bearish and is_c2_bullish:
            results.append(self._build_result(
                "Tweezer Bottom", PatternBias.BULLISH, PatternCategory.DOUBLE,
                confidence=85.0, quality=0.86,
                desc="Dual-candle precise low rejections confirming robust institutional support.",
                action="BUY", entry=c2_val, sl=min(l1, l2) - (0.05 * rng2), tp=c2_val + (1.9 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 8. Tweezer Top (Identical high rejections)
        elif abs(h1 - h2) / rng1 <= 0.05 and is_c1_bullish and is_c2_bearish:
            results.append(self._build_result(
                "Tweezer Top", PatternBias.BEARISH, PatternCategory.DOUBLE,
                confidence=85.0, quality=0.86,
                desc="Dual-candle precise high rejections confirming heavy supply wall.",
                action="SELL", entry=c2_val, sl=max(h1, h2) + (0.05 * rng2), tp=c2_val - (1.9 * rng2),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 9. Bullish Harami (Inside bar after down move)
        elif is_c1_bearish and is_c2_bullish and o2 > c1_val and c2_val < o1 and body2 < (0.6 * body1):
            results.append(self._build_result(
                "Bullish Harami", PatternBias.BULLISH, PatternCategory.DOUBLE,
                confidence=80.0, quality=0.80,
                desc="Bullish inside bar contraction; selling exhaustion preceding reversal push.",
                action="BUY", entry=c2_val, sl=l1 - (0.05 * rng1), tp=c2_val + (1.6 * rng1),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 10. Bearish Harami
        elif is_c1_bullish and is_c2_bearish and o2 < c1_val and c2_val > o1 and body2 < (0.6 * body1):
            results.append(self._build_result(
                "Bearish Harami", PatternBias.BEARISH, PatternCategory.DOUBLE,
                confidence=80.0, quality=0.80,
                desc="Bearish inside bar contraction; buying exhaustion at resistance.",
                action="SELL", entry=c2_val, sl=h1 + (0.05 * rng1), tp=c2_val - (1.6 * rng1),
                idx=idx, symbol=symbol, live_price=live_price
            ))

    # ──────────────────────────────────────────────────────────────────
    # Three-Candle Pattern Detectors
    # ──────────────────────────────────────────────────────────────────

    def _detect_three_candle_patterns(
        self,
        c1: Any,
        c2: Any,
        c3: Any,
        idx: int,
        symbol: str,
        results: List[CandlestickPatternResult],
        live_price: Optional[float]
    ) -> None:
        o1, h1, l1, c1_val = self._get_ohlc(c1)
        o2, h2, l2, c2_val = self._get_ohlc(c2)
        o3, h3, l3, c3_val = self._get_ohlc(c3)

        body1 = abs(c1_val - o1)
        body2 = abs(c2_val - o2)
        body3 = abs(c3_val - o3)
        rng3 = max(h3 - l3, 1e-6)

        is_c1_bear = c1_val < o1
        is_c1_bull = c1_val > o1
        is_c2_small = body2 < (0.35 * body1)
        is_c3_bull = c3_val > o3
        is_c3_bear = c3_val < o3

        # 1. Morning Star / Abandoned Baby
        if is_c1_bear and is_c2_small and is_c3_bull and c3_val >= (o1 + c1_val) / 2:
            is_abandoned = l2 < min(l1, l3) and body2 / max(h2 - l2, 1e-6) <= 0.1
            name = "Bullish Abandoned Baby" if is_abandoned else "Morning Star"
            conf = 93.0 if is_abandoned else 90.0
            results.append(self._build_result(
                name, PatternBias.BULLISH, PatternCategory.TRIPLE,
                confidence=conf, quality=0.92,
                desc="Three-bar reversal sequence: sharp drop -> base consolidation -> powerful upside surge.",
                action="BUY", entry=c3_val, sl=min(l1, l2, l3) - (0.05 * rng3), tp=c3_val + (2.2 * rng3),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 2. Evening Star / Bearish Abandoned Baby
        elif is_c1_bull and is_c2_small and is_c3_bear and c3_val <= (o1 + c1_val) / 2:
            is_abandoned = h2 > max(h1, h3) and body2 / max(h2 - l2, 1e-6) <= 0.1
            name = "Bearish Abandoned Baby" if is_abandoned else "Evening Star"
            conf = 93.0 if is_abandoned else 90.0
            results.append(self._build_result(
                name, PatternBias.BEARISH, PatternCategory.TRIPLE,
                confidence=conf, quality=0.92,
                desc="Three-bar reversal sequence: strong rally -> exhaustion top -> aggressive liquidation candle.",
                action="SELL", entry=c3_val, sl=max(h1, h2, h3) + (0.05 * rng3), tp=c3_val - (2.2 * rng3),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 3. Three White Soldiers (3 consecutive strong bull candles)
        elif is_c1_bull and c2_val > o2 and is_c3_bull and c3_val > c2_val > c1_val and o3 > o2 > o1:
            if body3 > (0.6 * (h3 - l3)) and body2 > (0.6 * (h2 - l2)):
                results.append(self._build_result(
                    "Three White Soldiers", PatternBias.BULLISH, PatternCategory.TRIPLE,
                    confidence=92.0, quality=0.93,
                    desc="Sustained institutional accumulation with three consecutive dominant green candles.",
                    action="BUY", entry=c3_val, sl=l1, tp=c3_val + (2.5 * rng3),
                    idx=idx, symbol=symbol, live_price=live_price
                ))

        # 4. Three Black Crows (3 consecutive strong bear candles)
        elif is_c1_bear and c2_val < o2 and is_c3_bear and c3_val < c2_val < c1_val and o3 < o2 < o1:
            if body3 > (0.6 * (h3 - l3)) and body2 > (0.6 * (h2 - l2)):
                results.append(self._build_result(
                    "Three Black Crows", PatternBias.BEARISH, PatternCategory.TRIPLE,
                    confidence=92.0, quality=0.93,
                    desc="Sustained institutional distribution with three consecutive dominant red candles.",
                    action="SELL", entry=c3_val, sl=h1, tp=c3_val - (2.5 * rng3),
                    idx=idx, symbol=symbol, live_price=live_price
                ))

        # 5. Three Line Strike (Bullish) - 3 down candles followed by 1 giant engulfing up candle
        elif is_c1_bear and c2_val < o2 and is_c3_bull and c3_val > max(o1, o2):
            results.append(self._build_result(
                "Three Line Strike", PatternBias.BULLISH, PatternCategory.TRIPLE,
                confidence=94.0, quality=0.95,
                desc="Three Line Strike: Single massive expansion candle engulfing 3 prior bear candles.",
                action="BUY", entry=c3_val, sl=l3, tp=c3_val + (2.5 * rng3),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 6. Three Inside Up (Harami + Confirmation Bullish Break)
        elif is_c1_bear and is_c2_small and c2_val > o2 and is_c3_bull and c3_val > o1:
            results.append(self._build_result(
                "Three Inside Up", PatternBias.BULLISH, PatternCategory.TRIPLE,
                confidence=87.0, quality=0.88,
                desc="Harami followed by confirmed breakout candle driving cleanly above the first bar's open.",
                action="BUY", entry=c3_val, sl=min(l1, l2), tp=c3_val + (2.0 * rng3),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 7. Three Inside Down (Harami + Confirmation Bearish Break)
        elif is_c1_bull and is_c2_small and c2_val < o2 and is_c3_bear and c3_val < o1:
            results.append(self._build_result(
                "Three Inside Down", PatternBias.BEARISH, PatternCategory.TRIPLE,
                confidence=87.0, quality=0.88,
                desc="Harami followed by confirmed breakdown candle driving cleanly below the first bar's open.",
                action="SELL", entry=c3_val, sl=max(h1, h2), tp=c3_val - (2.0 * rng3),
                idx=idx, symbol=symbol, live_price=live_price
            ))

        # 8. Rising Window / Falling Window (Fair Value Gaps / Windows)
        if l3 > h1:
            results.append(self._build_result(
                "Rising Window (FVG)", PatternBias.BULLISH, PatternCategory.TRIPLE,
                confidence=86.0, quality=0.87,
                desc="Bullish Fair Value Gap / Rising Window; price delivered with an unfilled liquidity imbalance.",
                action="BUY", entry=c3_val, sl=h1, tp=c3_val + (2.0 * rng3),
                idx=idx, symbol=symbol, live_price=live_price
            ))
        elif h3 < l1:
            results.append(self._build_result(
                "Falling Window (FVG)", PatternBias.BEARISH, PatternCategory.TRIPLE,
                confidence=86.0, quality=0.87,
                desc="Bearish Fair Value Gap / Falling Window; price liquidated leaving open overhead supply imbalance.",
                action="SELL", entry=c3_val, sl=l1, tp=c3_val - (2.0 * rng3),
                idx=idx, symbol=symbol, live_price=live_price
            ))

    # ──────────────────────────────────────────────────────────────────
    # Multi-Candle Classical Formations
    # ──────────────────────────────────────────────────────────────────

    def _detect_chart_patterns(
        self,
        candles: List[Any],
        symbol: str,
        results: List[CandlestickPatternResult],
        live_price: Optional[float]
    ) -> None:
        highs = [self._get_ohlc(c)[1] for c in candles[-20:]]
        lows = [self._get_ohlc(c)[2] for c in candles[-20:]]
        closes = [self._get_ohlc(c)[3] for c in candles[-20:]]
        latest_close = closes[-1]
        rng_total = max(max(highs) - min(lows), 1e-6)

        # Double Bottom (W-Pattern)
        min1 = min(lows[:10])
        min2 = min(lows[10:])
        if abs(min1 - min2) / rng_total <= 0.08 and latest_close > ((min1 + min2) / 2 + 0.3 * rng_total):
            results.append(self._build_result(
                "Double Bottom (W-Pattern)", PatternBias.BULLISH, PatternCategory.CHART,
                confidence=91.0, quality=0.92,
                desc="Institutional W-formation double rejection of structural support.",
                action="BUY", entry=latest_close, sl=min(min1, min2) - (0.05 * rng_total), tp=latest_close + (1.8 * rng_total),
                idx=len(candles) - 1, symbol=symbol, live_price=live_price
            ))

        # Double Top (M-Pattern)
        max1 = max(highs[:10])
        max2 = max(highs[10:])
        if abs(max1 - max2) / rng_total <= 0.08 and latest_close < ((max1 + max2) / 2 - 0.3 * rng_total):
            results.append(self._build_result(
                "Double Top (M-Pattern)", PatternBias.BEARISH, PatternCategory.CHART,
                confidence=91.0, quality=0.92,
                desc="Institutional M-formation double failure at major liquidity high.",
                action="SELL", entry=latest_close, sl=max(max1, max2) + (0.05 * rng_total), tp=latest_close - (1.8 * rng_total),
                idx=len(candles) - 1, symbol=symbol, live_price=live_price
            ))

    # ──────────────────────────────────────────────────────────────────
    # Helper Utilities
    # ──────────────────────────────────────────────────────────────────

    def _get_ohlc(self, candle: Any) -> Tuple[float, float, float, float]:
        if hasattr(candle, "open"):
            return float(candle.open), float(candle.high), float(candle.low), float(candle.close)
        elif isinstance(candle, dict):
            return float(candle.get("open", 0)), float(candle.get("high", 0)), float(candle.get("low", 0)), float(candle.get("close", 0))
        return 0.0, 0.0, 0.0, 0.0

    def _build_result(
        self,
        name: str,
        bias: PatternBias,
        cat: PatternCategory,
        confidence: float,
        quality: float,
        desc: str,
        action: str,
        entry: float,
        sl: float,
        tp: float,
        idx: int,
        symbol: str,
        live_price: Optional[float]
    ) -> CandlestickPatternResult:
        # If live price is provided from live market feed, anchor entry directly to real live market price
        final_entry = live_price if live_price and live_price > 0 else entry
        
        # Calculate real risk/reward ratio
        risk = max(abs(final_entry - sl), 1e-5)
        reward = max(abs(tp - final_entry), 1e-5)
        rr = round(reward / risk, 2)

        return CandlestickPatternResult(
            pattern_name=name,
            bias=bias,
            category=cat,
            confidence=confidence,
            quality_score=quality,
            description=desc,
            recommended_action=action,
            suggested_entry=round(final_entry, 5),
            suggested_stop_loss=round(sl, 5),
            suggested_take_profit=round(tp, 5),
            risk_reward_ratio=rr,
            candle_index=idx,
            timestamp=datetime.now(timezone.utc),
            extra_metadata={"symbol": symbol}
        )


candlestick_pattern_engine = CandlestickPatternEngine()
