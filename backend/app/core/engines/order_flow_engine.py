"""
Falcon Quantitative Engine — Intra-Candle Order Flow & Delta Footprint.

Implements microstructural volume analysis:
1. Intra-Bar Volume Delta Decomposition:
   Delta_i = Volume_i * (2 * Close_i - High_i - Low_i) / max(High_i - Low_i, epsilon)
2. Cumulative Volume Delta (CVD):
   20-period rolling sum of bar deltas.
3. Order Flow Imbalance (OFI):
   OFI = Delta / Volume in [-1.0, 1.0].
4. Absorption Wick Detection:
   Identifies aggressive exhaustion/absorption when rejection wicks >= 40% on RVol >= 1.5x.
5. Multi-Scale Sub-Bar Decomposition:
   Decomposes a 1-hour candle into its 15-minute constituent bars to analyze volume progression.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from app.core.engines.candlestick_pattern_engine import CandleBar


@dataclass
class IntraCandleDecomposition:
    symbol: str
    timeframe: str
    bar_delta: float
    cvd_20: float
    ofi: float
    is_bullish_delta: bool
    upper_wick_ratio: float
    lower_wick_ratio: float
    is_upper_absorption: bool
    is_lower_absorption: bool
    sub_bars_count: int
    volume_point_of_control: Optional[float] = None
    data_quality: str = "TICK_VOLUME"  # "TICK_VOLUME", "DECOMPOSED_M15", "NO_VOLUME"
    confluence_tag: Optional[str] = None


class OrderFlowEngine:
    def __init__(self):
        self.version = "1.0.0"

    def calculate_bar_delta(self, candle: CandleBar) -> float:
        """
        Calculates estimated intra-bar delta from price action location physics.
        Delta in [-Volume, +Volume].
        """
        total_range = candle.high - candle.low
        vol = float(candle.volume or 0.0)
        if total_range <= 1e-9 or vol <= 0.0:
            return 0.0
        
        # Intra-bar directional skew: (Close - Low) - (High - Close) = 2*Close - High - Low
        skew = (2.0 * candle.close - candle.high - candle.low) / total_range
        # Clamp skew to [-1.0, 1.0]
        skew = max(-1.0, min(1.0, skew))
        return round(vol * skew, 2)

    def calculate_cvd(self, candles: List[CandleBar], window: int = 20) -> List[float]:
        """
        Computes rolling Cumulative Volume Delta over a specified window.
        """
        deltas = [self.calculate_bar_delta(c) for c in candles]
        cvd_series: List[float] = []
        running = 0.0
        for i, d in enumerate(deltas):
            running += d
            if i >= window:
                running -= deltas[i - window]
            cvd_series.append(round(running, 2))
        return cvd_series

    def detect_absorption_wicks(
        self, candle: CandleBar, avg_volume: float = 0.0
    ) -> Tuple[float, float, bool, bool]:
        """
        Returns (upper_wick_ratio, lower_wick_ratio, is_upper_absorption, is_lower_absorption).
        Upper absorption = upper wick >= 40% on volume >= 1.5x average (institutional selling into buyers).
        Lower absorption = lower wick >= 40% on volume >= 1.5x average (institutional buying into sellers).
        """
        total_range = candle.high - candle.low
        if total_range <= 1e-9:
            return 0.0, 0.0, False, False

        body_top = max(candle.open, candle.close)
        body_bottom = min(candle.open, candle.close)

        upper_wick = candle.high - body_top
        lower_wick = body_bottom - candle.low

        upper_ratio = round(upper_wick / total_range, 3)
        lower_ratio = round(lower_wick / total_range, 3)

        vol = float(candle.volume or 0.0)
        is_high_volume = (vol >= 1.5 * avg_volume) if avg_volume > 0 else (vol > 100.0)

        is_upper_abs = (upper_ratio >= 0.40) and is_high_volume
        is_lower_abs = (lower_ratio >= 0.40) and is_high_volume

        return upper_ratio, lower_ratio, is_upper_abs, is_lower_abs

    def decompose_h1_with_m15(
        self, h1_candle: CandleBar, m15_sub_bars: List[CandleBar]
    ) -> Dict[str, Any]:
        """
        Reads inside a 1H candle by analyzing its constituent 15M sub-bars.
        Returns the volume distribution and intra-candle Point of Control (POC).
        """
        if not m15_sub_bars:
            return {
                "sub_bars_available": False,
                "poc_price": h1_candle.close,
                "delta_progression": [],
                "dominant_quarter": "UNKNOWN",
            }

        total_sub_vol = sum(float(b.volume or 0.0) for b in m15_sub_bars)
        quarter_deltas = [self.calculate_bar_delta(b) for b in m15_sub_bars]
        
        # Sub-bar with maximum volume is the primary liquidity node
        max_vol_bar = max(m15_sub_bars, key=lambda b: float(b.volume or 0.0))
        poc_price = (max_vol_bar.high + max_vol_bar.low + max_vol_bar.close) / 3.0

        return {
            "sub_bars_available": True,
            "poc_price": round(poc_price, 5),
            "delta_progression": quarter_deltas,
            "total_sub_volume": total_sub_vol,
            "is_increasing_volume": len(m15_sub_bars) >= 2 and float(m15_sub_bars[-1].volume or 0) > float(m15_sub_bars[0].volume or 0),
        }

    def analyze_order_flow(
        self,
        candles: List[CandleBar],
        m15_sub_bars: Optional[List[CandleBar]] = None,
        symbol: str = "XAUUSD",
        timeframe: str = "15m",
    ) -> IntraCandleDecomposition:
        """
        Analyzes the latest candle's order flow, reading inside the candle via physics
        and sub-bar decomposition.
        """
        if not candles:
            return IntraCandleDecomposition(
                symbol=symbol,
                timeframe=timeframe,
                bar_delta=0.0,
                cvd_20=0.0,
                ofi=0.0,
                is_bullish_delta=True,
                upper_wick_ratio=0.0,
                lower_wick_ratio=0.0,
                is_upper_absorption=False,
                is_lower_absorption=False,
                sub_bars_count=0,
                data_quality="NO_VOLUME",
                confluence_tag="Neutral Delta",
            )

        curr = candles[-1]
        vol = float(curr.volume or 0.0)
        if vol <= 0:
            return IntraCandleDecomposition(
                symbol=symbol,
                timeframe=timeframe,
                bar_delta=0.0,
                cvd_20=0.0,
                ofi=0.0,
                is_bullish_delta=True,
                upper_wick_ratio=0.0,
                lower_wick_ratio=0.0,
                is_upper_absorption=False,
                is_lower_absorption=False,
                sub_bars_count=0,
                data_quality="NO_VOLUME",
                confluence_tag="Price Action Verified (No Tick Volume)",
            )

        # Average volume of prior 20 bars
        prior_vols = [float(c.volume or 0.0) for c in candles[-21:-1]] if len(candles) >= 21 else [vol]
        avg_vol = sum(prior_vols) / max(len(prior_vols), 1)

        delta = self.calculate_bar_delta(curr)
        cvd_series = self.calculate_cvd(candles, window=20)
        cvd_val = cvd_series[-1] if cvd_series else delta
        ofi = round(delta / max(vol, 1.0), 3)

        u_ratio, l_ratio, is_u_abs, is_l_abs = self.detect_absorption_wicks(curr, avg_vol)

        poc = None
        data_quality = "TICK_VOLUME"
        sub_count = 0
        if m15_sub_bars and len(m15_sub_bars) > 0:
            decomp = self.decompose_h1_with_m15(curr, m15_sub_bars)
            poc = decomp.get("poc_price")
            sub_count = len(m15_sub_bars)
            data_quality = "DECOMPOSED_M15"
        else:
            poc = round(curr.close * 0.6 + curr.open * 0.4, 5)

        # Formulate non-blocking confluence tag
        if delta > 0 and ofi >= 0.25:
            confluence = f"🟢 Strong Buying Delta (+{abs(int(delta))})"
        elif delta < 0 and ofi <= -0.25:
            confluence = f"🔴 Strong Selling Delta (-{abs(int(delta))})"
        elif is_u_abs:
            confluence = "⚠️ Upper Absorption Wick (Trapped Buyers)"
        elif is_l_abs:
            confluence = "🟢 Lower Absorption Wick (Trapped Sellers Defended)"
        else:
            confluence = f"⚖️ Neutral Delta ({delta:+.0f})"

        return IntraCandleDecomposition(
            symbol=symbol,
            timeframe=timeframe,
            bar_delta=delta,
            cvd_20=cvd_val,
            ofi=ofi,
            is_bullish_delta=delta >= 0,
            upper_wick_ratio=u_ratio,
            lower_wick_ratio=l_ratio,
            is_upper_absorption=is_u_abs,
            is_lower_absorption=is_l_abs,
            sub_bars_count=sub_count,
            volume_point_of_control=poc,
            data_quality=data_quality,
            confluence_tag=confluence,
        )


order_flow_engine = OrderFlowEngine()
