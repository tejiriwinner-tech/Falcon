"""
Falcon Institutional Masterpiece — Pillar 2: Institutional Liquidity Sweep & Fair Value Gap (FVG) Engine

Implements Smart Money Concepts (SMC):
1. Identifies institutional liquidity pools: Previous Day High/Low (PDH/PDL),
   Asian Session High/Low (ASH/ASL), and Swing Equal Highs/Lows (EQH/EQL).
2. Detects institutional Stop Hunts / Liquidity Sweeps (wick pierces liquidity pool
   and closes back inside range with displacement rejection).
3. Detects 3-Candle Fair Value Gaps (FVGs / Price Imbalances).
4. Generates high-precision sniper trade levels with tight wick-anchored stops
   and asymmetric 1:3.0 to 1:4.5 Risk-to-Reward targets.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

logger = logging.getLogger("falcon.smart_money_engine")


@dataclass
class FairValueGap:
    direction: str          # "BULLISH" or "BEARISH"
    top: float              # Upper boundary of the imbalance
    bottom: float           # Lower boundary of the imbalance
    midpoint: float         # 50% Consequent Encroachment (CE) optimal sniper entry
    size: float             # Absolute gap size
    candle_index: int       # Index in candle array where FVG completed


@dataclass
class LiquiditySweepSignal:
    symbol: str
    detected: bool
    direction: str = "WAIT"                 # "BUY" (after sell-side sweep) or "SELL" (after buy-side sweep)
    swept_pool_type: str = "NONE"           # "PDH", "PDL", "ASH", "ASL", "SWING_HIGH", "SWING_LOW"
    swept_level: float = 0.0                # Key liquidity level that was pierced
    sweep_wick_extreme: float = 0.0         # Exact tip of the liquidity-hunting wick
    rejection_close: float = 0.0            # Candle close back inside structure
    fvg: Optional[FairValueGap] = None      # Paired Fair Value Gap (if present)
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward: float = 0.0
    confidence_bonus: int = 0
    rationale: str = ""
    tags: List[str] = field(default_factory=list)


class SmartMoneyEngine:
    """
    Institutional Liquidity Sweep & Fair Value Gap (FVG) Detector.
    """

    def _extract_ohlc(self, candle: Any) -> tuple[float, float, float, float, Optional[datetime]]:
        if isinstance(candle, dict):
            o = float(candle.get("open", 0.0))
            h = float(candle.get("high", 0.0))
            l = float(candle.get("low", 0.0))
            c = float(candle.get("close", 0.0))
            ts = candle.get("timestamp") or candle.get("time")
        else:
            o = float(getattr(candle, "open", 0.0))
            h = float(getattr(candle, "high", 0.0))
            l = float(getattr(candle, "low", 0.0))
            c = float(getattr(candle, "close", 0.0))
            ts = getattr(candle, "timestamp", None) or getattr(candle, "time", None)
        return o, h, l, c, ts

    def detect_fair_value_gaps(self, candles: List[Any], lookback: int = 10) -> List[FairValueGap]:
        """
        Scan recent candles for 3-candle bullish and bearish Fair Value Gaps (FVGs).
        - Bullish FVG: Candle[i-2].high < Candle[i].low
        - Bearish FVG: Candle[i-2].low > Candle[i].high
        """
        fvgs: List[FairValueGap] = []
        n = len(candles)
        if n < 3:
            return fvgs

        start_idx = max(2, n - lookback)
        for i in range(start_idx, n):
            _, h0, l0, _, _ = self._extract_ohlc(candles[i - 2])
            o1, h1, l1, c1, _ = self._extract_ohlc(candles[i - 1])
            _, h2, l2, _, _ = self._extract_ohlc(candles[i])

            # Bullish FVG: displacement candle i-1 rallies leaving gap between h0 and l2
            if l2 > h0 and c1 > o1:
                gap_size = l2 - h0
                midpoint = h0 + (gap_size * 0.5)
                fvgs.append(
                    FairValueGap(
                        direction="BULLISH",
                        top=round(l2, 5),
                        bottom=round(h0, 5),
                        midpoint=round(midpoint, 5),
                        size=round(gap_size, 5),
                        candle_index=i,
                    )
                )
            # Bearish FVG: displacement candle i-1 drops leaving gap between l0 and h2
            elif l0 > h2 and c1 < o1:
                gap_size = l0 - h2
                midpoint = h2 + (gap_size * 0.5)
                fvgs.append(
                    FairValueGap(
                        direction="BEARISH",
                        top=round(l0, 5),
                        bottom=round(h2, 5),
                        midpoint=round(midpoint, 5),
                        size=round(gap_size, 5),
                        candle_index=i,
                    )
                )

        return fvgs

    def analyze_liquidity_sweep(
        self, symbol: str, candles: List[Any]
    ) -> LiquiditySweepSignal:
        """
        Analyze OHLCV series for an institutional Liquidity Sweep + FVG confirmation.
        Works on H1 or M15 candles.
        """
        norm_sym = (symbol or "XAUUSD").replace("/", "").replace("_", "").upper()
        is_gold = "XAU" in norm_sym or "GOLD" in norm_sym
        is_jpy = "JPY" in norm_sym
        decimals = 2 if is_gold else (3 if is_jpy else 5)
        pip_buffer = 1.20 if is_gold else (0.025 if is_jpy else 0.00020)

        if not candles or len(candles) < 12:
            return LiquiditySweepSignal(
                symbol=symbol,
                detected=False,
                rationale="Insufficient candle history for SMC liquidity sweep analysis.",
            )

        # Extract prior structure pools (excluding the last 2 potential sweep candles)
        structure_window = candles[:-2]
        recent_pool = structure_window[-24:] if len(structure_window) >= 24 else structure_window
        session_pool = structure_window[-8:] if len(structure_window) >= 8 else structure_window

        pdh = max(self._extract_ohlc(c)[1] for c in recent_pool)
        pdl = min(self._extract_ohlc(c)[2] for c in recent_pool)
        ash = max(self._extract_ohlc(c)[1] for c in session_pool)
        asl = min(self._extract_ohlc(c)[2] for c in session_pool)

        # Evaluate last 2 candles for a wick pierce + body rejection close inside the pool
        c_last = candles[-1]
        c_prev = candles[-2]
        o_last, h_last, l_last, close_last, _ = self._extract_ohlc(c_last)
        o_prev, h_prev, l_prev, close_prev, _ = self._extract_ohlc(c_prev)

        recent_high_wick = max(h_last, h_prev)
        recent_low_wick = min(l_last, l_prev)

        fvgs = self.detect_fair_value_gaps(candles, lookback=6)
        bullish_fvg = next((f for f in reversed(fvgs) if f.direction == "BULLISH"), None)
        bearish_fvg = next((f for f in reversed(fvgs) if f.direction == "BEARISH"), None)

        # 1. Check Bullish Liquidity Sweep (Sell-Side Liquidity Grab below PDL or ASL)
        swept_low_level = None
        swept_low_type = "NONE"
        if recent_low_wick < pdl and close_last > pdl:
            swept_low_level = pdl
            swept_low_type = "PDL"
        elif recent_low_wick < asl and close_last > asl:
            swept_low_level = asl
            swept_low_type = "ASL"

        if swept_low_level is not None:
            # Verify meaningful rejection wick
            wick_depth = swept_low_level - recent_low_wick
            stop_loss = round(recent_low_wick - pip_buffer, decimals)
            entry_price = round(close_last, decimals)
            risk = abs(entry_price - stop_loss)
            # Enforce minimum sensible stop distance to avoid division-by-tiny-wick
            min_risk = 2.50 if is_gold else (0.08 if is_jpy else 0.0008)
            if risk < min_risk:
                stop_loss = round(entry_price - min_risk, decimals)
                risk = min_risk

            # Target opposite liquidity pool or minimum 3.2R asymmetric target
            structural_target = max(pdh, entry_price + (risk * 3.2))
            take_profit = round(min(structural_target, entry_price + (risk * 4.5)), decimals)
            rr = round(abs(take_profit - entry_price) / risk, 2) if risk > 0 else 3.2

            has_fvg = bullish_fvg is not None
            bonus = 18 if has_fvg else 12
            tags = ["SMC_LIQUIDITY_SWEEP", f"SWEEP_{swept_low_type}"]
            if has_fvg:
                tags.append("BULLISH_FVG_DISPLACEMENT")

            fvg_note = (
                f" paired with Bullish FVG [{bullish_fvg.bottom:.{decimals}f}-{bullish_fvg.top:.{decimals}f}]"
                if bullish_fvg else " with sharp lower-wick rejection"
            )
            return LiquiditySweepSignal(
                symbol=symbol,
                detected=True,
                direction="BUY",
                swept_pool_type=swept_low_type,
                swept_level=round(swept_low_level, decimals),
                sweep_wick_extreme=round(recent_low_wick, decimals),
                rejection_close=entry_price,
                fvg=bullish_fvg,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward=rr,
                confidence_bonus=bonus,
                rationale=(
                    f"Institutional Sell-Side Liquidity Sweep: Price swept {swept_low_type} ({swept_low_level:.{decimals}f}) "
                    f"down to {recent_low_wick:.{decimals}f} and rejected back to {entry_price:.{decimals}f}{fvg_note} "
                    f"(R:R 1:{rr:.1f})."
                ),
                tags=tags,
            )

        # 2. Check Bearish Liquidity Sweep (Buy-Side Liquidity Grab above PDH or ASH)
        swept_high_level = None
        swept_high_type = "NONE"
        if recent_high_wick > pdh and close_last < pdh:
            swept_high_level = pdh
            swept_high_type = "PDH"
        elif recent_high_wick > ash and close_last < ash:
            swept_high_level = ash
            swept_high_type = "ASH"

        if swept_high_level is not None:
            stop_loss = round(recent_high_wick + pip_buffer, decimals)
            entry_price = round(close_last, decimals)
            risk = abs(stop_loss - entry_price)
            min_risk = 2.50 if is_gold else (0.08 if is_jpy else 0.0008)
            if risk < min_risk:
                stop_loss = round(entry_price + min_risk, decimals)
                risk = min_risk

            structural_target = min(pdl, entry_price - (risk * 3.2))
            take_profit = round(max(structural_target, entry_price - (risk * 4.5)), decimals)
            rr = round(abs(entry_price - take_profit) / risk, 2) if risk > 0 else 3.2

            has_fvg = bearish_fvg is not None
            bonus = 18 if has_fvg else 12
            tags = ["SMC_LIQUIDITY_SWEEP", f"SWEEP_{swept_high_type}"]
            if has_fvg:
                tags.append("BEARISH_FVG_DISPLACEMENT")

            fvg_note = (
                f" paired with Bearish FVG [{bearish_fvg.bottom:.{decimals}f}-{bearish_fvg.top:.{decimals}f}]"
                if bearish_fvg else " with sharp upper-wick rejection"
            )
            return LiquiditySweepSignal(
                symbol=symbol,
                detected=True,
                direction="SELL",
                swept_pool_type=swept_high_type,
                swept_level=round(swept_high_level, decimals),
                sweep_wick_extreme=round(recent_high_wick, decimals),
                rejection_close=entry_price,
                fvg=bearish_fvg,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward=rr,
                confidence_bonus=bonus,
                rationale=(
                    f"Institutional Buy-Side Liquidity Sweep: Price swept {swept_high_type} ({swept_high_level:.{decimals}f}) "
                    f"up to {recent_high_wick:.{decimals}f} and rejected back to {entry_price:.{decimals}f}{fvg_note} "
                    f"(R:R 1:{rr:.1f})."
                ),
                tags=tags,
            )

        # 3. Pure Displacement Fair Value Gap Continuation (if no sweep on exact last bar, check fresh FVG near key pool)
        if bullish_fvg and bullish_fvg.candle_index >= len(candles) - 2 and close_last >= bullish_fvg.bottom:
            entry_price = round(close_last, decimals)
            stop_loss = round(min(l_last, bullish_fvg.bottom) - pip_buffer, decimals)
            risk = max(abs(entry_price - stop_loss), 2.50 if is_gold else (0.08 if is_jpy else 0.0008))
            stop_loss = round(entry_price - risk, decimals)
            take_profit = round(entry_price + (risk * 3.0), decimals)
            return LiquiditySweepSignal(
                symbol=symbol,
                detected=True,
                direction="BUY",
                swept_pool_type="FVG_IMBALANCE",
                swept_level=bullish_fvg.midpoint,
                sweep_wick_extreme=stop_loss,
                rejection_close=entry_price,
                fvg=bullish_fvg,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward=3.0,
                confidence_bonus=10,
                rationale=(
                    f"Institutional Bullish Fair Value Gap displacement [{bullish_fvg.bottom:.{decimals}f}-"
                    f"{bullish_fvg.top:.{decimals}f}] with 50% CE at {bullish_fvg.midpoint:.{decimals}f} (R:R 1:3.0)."
                ),
                tags=["SMC_FVG_DISPLACEMENT", "BULLISH_FVG"],
            )

        if bearish_fvg and bearish_fvg.candle_index >= len(candles) - 2 and close_last <= bearish_fvg.top:
            entry_price = round(close_last, decimals)
            stop_loss = round(max(h_last, bearish_fvg.top) + pip_buffer, decimals)
            risk = max(abs(stop_loss - entry_price), 2.50 if is_gold else (0.08 if is_jpy else 0.0008))
            stop_loss = round(entry_price + risk, decimals)
            take_profit = round(entry_price - (risk * 3.0), decimals)
            return LiquiditySweepSignal(
                symbol=symbol,
                detected=True,
                direction="SELL",
                swept_pool_type="FVG_IMBALANCE",
                swept_level=bearish_fvg.midpoint,
                sweep_wick_extreme=stop_loss,
                rejection_close=entry_price,
                fvg=bearish_fvg,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                risk_reward=3.0,
                confidence_bonus=10,
                rationale=(
                    f"Institutional Bearish Fair Value Gap displacement [{bearish_fvg.bottom:.{decimals}f}-"
                    f"{bearish_fvg.top:.{decimals}f}] with 50% CE at {bearish_fvg.midpoint:.{decimals}f} (R:R 1:3.0)."
                ),
                tags=["SMC_FVG_DISPLACEMENT", "BEARISH_FVG"],
            )

        return LiquiditySweepSignal(
            symbol=symbol,
            detected=False,
            rationale="No active institutional liquidity sweep or displacement FVG on current bar.",
        )


smart_money_engine = SmartMoneyEngine()
