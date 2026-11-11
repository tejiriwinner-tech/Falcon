"""
Falcon Quantitative Engine — Stage 1 & Stage 2 Institutional Order Flow, L2 DOM,
OANDA OrderBook/PositionBook Stop-Cluster X-Ray & CFTC COT Futures Positioning.

Implements microstructural & institutional volume analysis:
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
6. Stage 2 Real-Time L2 Order Book Depth (DOM) Imbalance:
   DOM Imbalance = (Sum Bid Liquidity - Sum Ask Liquidity) / (Sum Bid Liquidity + Sum Ask Liquidity)
7. Stage 2 OANDA OrderBook & PositionBook Stop-Cluster X-Ray:
   Detects concentrated retail stop-loss clusters and contrarian retail positioning skews.
8. Stage 2 CFTC COT (Commitment of Traders) Non-Commercial Futures Positioning:
   Tracks institutional leveraged-fund/non-commercial net positioning across CME FX & COMEX Gold.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.core.engines.candlestick_pattern_engine import CandleBar

logger = logging.getLogger("falcon.engines.order_flow")


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


@dataclass
class Stage2OrderFlowEvaluation:
    symbol: str
    direction: str  # "BUY" or "SELL"
    dom_imbalance: float
    dom_aligned: bool
    opposing_liquidity_wall: bool
    zero_lag_absorption: bool
    stop_cluster_swept: bool
    stop_cluster_level: Optional[float]
    retail_net_long_pct: float
    retail_contrarian_aligned: bool
    cot_net_ratio: float
    cot_bias: str
    cot_aligned: bool
    conviction_delta: int
    telemetry_tag: str


# Institutional CFTC COT baseline non-commercial net ratios (NonComm Long - Short) / (Long + Short)
# Used immediately while background CFTC Socrata refresh runs, or if CFTC endpoint is unreachable.
_COT_INSTITUTIONAL_BASELINE: Dict[str, Dict[str, Any]] = {
    "XAU": {"net_ratio": 0.34, "bias": "BULLISH", "contract": "GOLD - COMMODITY EXCHANGE INC."},
    "EUR": {"net_ratio": 0.12, "bias": "BULLISH", "contract": "EURO FX - CHICAGO MERCANTILE EXCHANGE"},
    "GBP": {"net_ratio": 0.16, "bias": "BULLISH", "contract": "BRITISH POUND - CHICAGO MERCANTILE EXCHANGE"},
    "JPY": {"net_ratio": -0.22, "bias": "BEARISH", "contract": "JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"},
    "AUD": {"net_ratio": -0.14, "bias": "BEARISH", "contract": "AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"},
    "USD": {"net_ratio": 0.08, "bias": "BULLISH", "contract": "U.S. DOLLAR INDEX - ICE FUTURES U.S."},
}


class OrderFlowEngine:
    def __init__(self):
        self.version = "2.0.0"
        self._cot_cache: Dict[str, Dict[str, Any]] = {}
        self._cot_last_refresh: float = 0.0
        self._cot_refreshing: bool = False
        self._cot_lock = threading.Lock()

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
            "is_increasing_volume": len(m15_sub_bars) >= 2
            and float(m15_sub_bars[-1].volume or 0) > float(m15_sub_bars[0].volume or 0),
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
        prior_vols = (
            [float(c.volume or 0.0) for c in candles[-21:-1]]
            if len(candles) >= 21
            else [vol]
        )
        avg_vol = sum(prior_vols) / max(len(prior_vols), 1)

        delta = self.calculate_bar_delta(curr)
        cvd_series = self.calculate_cvd(candles, window=20)
        cvd_val = cvd_series[-1] if cvd_series else delta
        ofi = round(delta / max(vol, 1.0), 3)

        u_ratio, l_ratio, is_u_abs, is_l_abs = self.detect_absorption_wicks(
            curr, avg_vol
        )

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

    # ──────────────────────────────────────────────────────────────────
    # Stage 2: CFTC COT Institutional Futures Positioning Engine
    # ──────────────────────────────────────────────────────────────────

    def _trigger_async_cot_refresh(self) -> None:
        """Asynchronously refresh CFTC COT Non-Commercial positioning (6-hour TTL)."""
        now_ts = time.time()
        with self._cot_lock:
            if self._cot_refreshing or (now_ts - self._cot_last_refresh) < 21600.0:
                return
            self._cot_refreshing = True

        def _worker() -> None:
            try:
                url = (
                    "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
                    "?$limit=40&$order=report_date_as_yyyy_mm_dd%20DESC"
                )
                resp = requests.get(url, timeout=3.5)
                if resp.status_code == 200:
                    rows = resp.json()
                    updated: Dict[str, Dict[str, Any]] = {}
                    keyword_map = {
                        "GOLD": "XAU",
                        "EURO FX": "EUR",
                        "BRITISH POUND": "GBP",
                        "JAPANESE YEN": "JPY",
                        "AUSTRALIAN DOLLAR": "AUD",
                        "U.S. DOLLAR INDEX": "USD",
                    }
                    for row in rows:
                        mkt_name = str(row.get("market_and_exchange_names", "")).upper()
                        for kw, ccy in keyword_map.items():
                            if kw in mkt_name and ccy not in updated:
                                nc_long = float(row.get("noncomm_positions_long_all", 0) or 0)
                                nc_short = float(row.get("noncomm_positions_short_all", 0) or 0)
                                total_nc = nc_long + nc_short
                                if total_nc > 0:
                                    ratio = round((nc_long - nc_short) / total_nc, 4)
                                    bias = (
                                        "BULLISH"
                                        if ratio >= 0.08
                                        else ("BEARISH" if ratio <= -0.08 else "NEUTRAL")
                                    )
                                    updated[ccy] = {
                                        "net_ratio": ratio,
                                        "bias": bias,
                                        "contract": mkt_name,
                                    }
                    with self._cot_lock:
                        self._cot_cache.update(updated)
                        self._cot_last_refresh = time.time()
            except Exception as ex:
                logger.debug("[OrderFlowEngine] CFTC COT background refresh skipped: %s", ex)
                with self._cot_lock:
                    self._cot_last_refresh = time.time()
            finally:
                with self._cot_lock:
                    self._cot_refreshing = False

        threading.Thread(target=_worker, daemon=True).start()

    def get_cot_institutional_bias(self, symbol: str) -> Dict[str, Any]:
        """
        Compute institutional CFTC COT Non-Commercial net positioning for a currency/metal pair.
        Returns net_ratio in [-1.0, +1.0] and bias ('BULLISH', 'BEARISH', 'NEUTRAL').
        Executes in <0.01ms from in-memory cache + async background refresh.
        """
        self._trigger_async_cot_refresh()
        clean = symbol.replace("/", "").replace("_", "").upper()
        base = clean[:3] if len(clean) >= 6 else "XAU"
        quote = clean[3:6] if len(clean) >= 6 else "USD"

        with self._cot_lock:
            base_info = self._cot_cache.get(base) or _COT_INSTITUTIONAL_BASELINE.get(
                base, {"net_ratio": 0.0, "bias": "NEUTRAL"}
            )
            quote_info = self._cot_cache.get(quote) or _COT_INSTITUTIONAL_BASELINE.get(
                quote, {"net_ratio": 0.0, "bias": "NEUTRAL"}
            )

        base_ratio = float(base_info.get("net_ratio", 0.0))
        quote_ratio = float(quote_info.get("net_ratio", 0.0))
        # Pair institutional net positioning = Base COT Net Ratio - Quote COT Net Ratio
        pair_net_ratio = round(max(-1.0, min(1.0, base_ratio - (quote_ratio * 0.65))), 4)

        if pair_net_ratio >= 0.08:
            pair_bias = "BULLISH"
        elif pair_net_ratio <= -0.08:
            pair_bias = "BEARISH"
        else:
            pair_bias = "NEUTRAL"

        return {
            "symbol": symbol,
            "netRatio": pair_net_ratio,
            "bias": pair_bias,
            "baseRatio": base_ratio,
            "quoteRatio": quote_ratio,
        }

    # ──────────────────────────────────────────────────────────────────
    # Stage 2: Combined DOM + OrderBook Stop-Cluster + COT + Absorption
    # ──────────────────────────────────────────────────────────────────

    def evaluate_dom_and_absorption(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        dom_imbalance: Optional[float] = None,
        order_book_snapshot: Optional[Dict[str, Any]] = None,
        decomp: Optional[IntraCandleDecomposition] = None,
    ) -> Stage2OrderFlowEvaluation:
        """
        Stage 2 Hedge-Fund Grade Order Flow Evaluation combining:
        1. Real-time L2 Order Book Depth (DOM) Bid/Ask Liquidity Imbalance
        2. OANDA OrderBook & PositionBook Retail Stop-Cluster X-Ray
        3. CFTC COT Non-Commercial Institutional Positioning
        4. Zero-Lag Passive Limit Absorption vs. Aggressive Delta Continuation
        """
        dir_up = direction.upper() == "BUY"
        dom_val = float(dom_imbalance) if dom_imbalance is not None else 0.0
        ob = order_book_snapshot or {}

        # 1. L2 DOM Imbalance alignment & opposing wall check
        dom_aligned = (dom_val >= 0.15) if dir_up else (dom_val <= -0.15)

        # 2. Zero-Lag Absorption detection (Passive limit absorption on sweep wick + Delta/DOM support)
        zero_lag_abs = False
        if decomp is not None:
            if dir_up and (decomp.is_lower_absorption or (decomp.lower_wick_ratio >= 0.35 and (decomp.bar_delta > 0 or dom_val >= 0.10))):
                zero_lag_abs = True
            elif not dir_up and (decomp.is_upper_absorption or (decomp.upper_wick_ratio >= 0.35 and (decomp.bar_delta < 0 or dom_val <= -0.10))):
                zero_lag_abs = True

        # Opposing L2 Liquidity Wall: >= 45% L2 liquidity stacked against trade direction without absorption
        opposing_wall = (
            (dir_up and dom_val <= -0.45 and not zero_lag_abs)
            or (not dir_up and dom_val >= 0.45 and not zero_lag_abs)
        )

        # 3. OANDA OrderBook Stop-Cluster X-Ray & Contrarian Retail PositionBook Skew
        stop_cluster_swept = False
        stop_cluster_level: Optional[float] = None
        if ob.get("available"):
            if dir_up:
                cluster_below = ob.get("stopLossClusterBelow")
                cluster_pct = float(ob.get("stopLossClusterBelowPct", 0.0) or 0.0)
                if cluster_below and cluster_pct >= 0.8:
                    stop_cluster_level = float(cluster_below)
                    if abs(entry_price - stop_cluster_level) / max(entry_price, 1e-6) <= 0.005:
                        stop_cluster_swept = True
            else:
                cluster_above = ob.get("stopLossClusterAbove")
                cluster_pct = float(ob.get("stopLossClusterAbovePct", 0.0) or 0.0)
                if cluster_above and cluster_pct >= 0.8:
                    stop_cluster_level = float(cluster_above)
                    if abs(entry_price - stop_cluster_level) / max(entry_price, 1e-6) <= 0.005:
                        stop_cluster_swept = True

        retail_net_long = float(ob.get("retailNetLongPct", 50.0) or 50.0)
        contrarian_bias = str(ob.get("contrarianBias", "NEUTRAL"))
        retail_contrarian_aligned = (
            (dir_up and contrarian_bias == "BULLISH")
            or (not dir_up and contrarian_bias == "BEARISH")
        )

        # 4. CFTC COT Institutional Futures Positioning
        cot = self.get_cot_institutional_bias(symbol)
        cot_net_ratio = float(cot.get("netRatio", 0.0))
        cot_bias = str(cot.get("bias", "NEUTRAL"))
        cot_aligned = (
            (dir_up and cot_bias == "BULLISH")
            or (not dir_up and cot_bias == "BEARISH")
        )

        # 5. Compute net conviction score adjustment [-4, +5]
        conviction_delta = 0
        tags: List[str] = []

        if opposing_wall:
            conviction_delta -= 4
            tags.append(f"⛔ Opposing L2 DOM Wall ({dom_val:+.2f})")
        elif dom_aligned:
            conviction_delta += 2
            tags.append(f"📘 L2 DOM Aligned ({dom_val:+.2f})")
        else:
            tags.append(f"📘 L2 DOM ({dom_val:+.2f})")

        if zero_lag_abs:
            conviction_delta += 2
            tags.append("🧲 Zero-Lag Limit Absorption")

        if stop_cluster_swept and stop_cluster_level is not None:
            conviction_delta += 1
            tags.append(f"🎯 OrderBook Stop-Cluster ({stop_cluster_level})")

        if retail_contrarian_aligned:
            conviction_delta += 1
            tags.append(f"🔄 Contrarian Retail Skew ({retail_net_long:.0f}% Long)")

        if cot_aligned:
            conviction_delta += 1
            tags.append(f"🏛️ CFTC COT {cot_bias} ({cot_net_ratio:+.2f})")
        elif (dir_up and cot_bias == "BEARISH" and cot_net_ratio <= -0.25) or (
            not dir_up and cot_bias == "BULLISH" and cot_net_ratio >= 0.25
        ):
            conviction_delta -= 1
            tags.append(f"⚠️ CFTC COT Headwind ({cot_net_ratio:+.2f})")

        conviction_delta = max(-4, min(5, conviction_delta))
        telemetry_tag = " | ".join(tags)

        return Stage2OrderFlowEvaluation(
            symbol=symbol,
            direction=direction.upper(),
            dom_imbalance=dom_val,
            dom_aligned=dom_aligned,
            opposing_liquidity_wall=opposing_wall,
            zero_lag_absorption=zero_lag_abs,
            stop_cluster_swept=stop_cluster_swept,
            stop_cluster_level=stop_cluster_level,
            retail_net_long_pct=retail_net_long,
            retail_contrarian_aligned=retail_contrarian_aligned,
            cot_net_ratio=cot_net_ratio,
            cot_bias=cot_bias,
            cot_aligned=cot_aligned,
            conviction_delta=conviction_delta,
            telemetry_tag=telemetry_tag,
        )


order_flow_engine = OrderFlowEngine()
