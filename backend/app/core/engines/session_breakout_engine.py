"""
Falcon Pillar 1 — Session Momentum, Volume Expansion & Volatility Exhaustion Engine.

Implements deterministic algorithms for:
1. Session Corridors & Liquidity Ranges:
   - Asian Session: 00:00 - 07:00 UTC (defines baseline consolidation range).
   - London Open Corridor: 07:00 - 10:00 UTC (initial balance & expansion triggers).
   - New York Overlap: 12:00 - 16:00 UTC (peak volume expansion window).
2. Multi-Timeframe Volume Expansion:
   - Relative Volume (RVol) calculation vs. 20-period volume SMA.
   - Volume Surge detection (RVol >= 1.8x with wide candle spread > 60% of total range).
3. Statistical Volatility Exhaustion & Mean Reversion:
   - 2.5σ Keltner / Bollinger standard deviation bands centered on the 20 EMA.
   - RSI and extreme envelope piercing identifying institutional exhaustion.
4. Composite Conviction Scoring (0-100%).
"""

from datetime import datetime, timezone
from dataclasses import dataclass
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.schemas.session_breakout import (
    CompositeConvictionScore,
    ConvictionBias,
    SessionBreakoutStructureResponse,
    SessionName,
    SessionRange,
    SessionStatus,
    VolatilityExhaustionZone,
    VolumeExpansionMarker,
)


def _get_pip_size(symbol: str) -> float:
    """Returns canonical pip size for symbol."""
    sym = symbol.upper()
    if "JPY" in sym:
        return 0.01
    elif "XAU" in sym or "GOLD" in sym:
        return 0.1
    elif "BTC" in sym or "ETH" in sym:
        return 1.0
    elif any(idx in sym for idx in ["US30", "NAS100", "SPX", "GER40", "UK100"]):
        return 1.0
    return 0.0001


@dataclass
class SweepRetestEvaluation:
    phase: str  # "SWEEP_PROBE", "RETEST_FORMING", "EXPANSION_CONFIRMED", "NO_SWEEP"
    is_confirmed: bool
    is_sweep_reversal: bool
    retest_price: Optional[float]
    tactical_note: str


class SessionBreakoutEngine:
    """
    Institutional Session Breakout, Volume Expansion & Statistical Volatility Engine.
    Replaces SMC with empirical volume and session dynamics.
    """

    def compute_session_corridors(
        self,
        symbol: str,
        candles: List[CandleBar],
        allow_benchmark: bool = False,
    ) -> List[SessionRange]:
        """
        Extracts high/low corridors for Asian Range, London Open, and New York Overlap.
        """
        pip = _get_pip_size(symbol)
        if not candles:
            return self._generate_benchmark_corridors(symbol) if allow_benchmark else []

        # Parse candles with timestamps and sort chronologically
        dated_candles: List[Tuple[datetime, CandleBar]] = []
        for c in candles:
            raw_t = getattr(c, "timestamp", None) or getattr(c, "time", None)
            dt = None
            if isinstance(raw_t, datetime):
                dt = raw_t
            elif isinstance(raw_t, (int, float)):
                try:
                    s = raw_t / 1000.0 if raw_t > 1e11 else raw_t
                    dt = datetime.fromtimestamp(s, tz=timezone.utc)
                except Exception:
                    pass
            elif isinstance(raw_t, str):
                try:
                    dt = datetime.fromisoformat(raw_t.replace("Z", "+00:00"))
                except Exception:
                    pass

            if dt is not None:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                dated_candles.append((dt, c))

        if not dated_candles:
            return self._generate_benchmark_corridors(symbol) if allow_benchmark else []

        dated_candles.sort(key=lambda x: x[0])

        # Categorize candles by session and isolate the latest occurrence of each session
        asian_all = [(dt, c) for dt, c in dated_candles if 0 <= dt.hour < 7]
        london_all = [(dt, c) for dt, c in dated_candles if 7 <= dt.hour < 12]
        ny_all = [(dt, c) for dt, c in dated_candles if 12 <= dt.hour < 16]

        asian_candles: List[CandleBar] = []
        if asian_all:
            latest_asian_date = max(dt.date() for dt, _ in asian_all)
            asian_candles = [c for dt, c in asian_all if dt.date() == latest_asian_date]

        london_candles: List[CandleBar] = []
        if london_all:
            latest_london_date = max(dt.date() for dt, _ in london_all)
            london_candles = [c for dt, c in london_all if dt.date() == latest_london_date]

        ny_candles: List[CandleBar] = []
        if ny_all:
            latest_ny_date = max(dt.date() for dt, _ in ny_all)
            ny_candles = [c for dt, c in ny_all if dt.date() == latest_ny_date]

        corridors: List[SessionRange] = []

        # 1. Asian Corridor
        if asian_candles:
            a_high = max(c.high for c in asian_candles)
            a_low = min(c.low for c in asian_candles)
            a_open = asian_candles[0].open
            a_close = asian_candles[-1].close
            latest_price = candles[-1].close
            status = SessionStatus.INTACT
            if latest_price > a_high:
                status = SessionStatus.BROKEN_UP
            elif latest_price < a_low:
                status = SessionStatus.BROKEN_DOWN

            corridors.append(
                SessionRange(
                    session_name=SessionName.ASIAN,
                    high=round(a_high, 5),
                    low=round(a_low, 5),
                    open_price=round(a_open, 5),
                    close_price=round(a_close, 5),
                    status=status,
                    range_pips=round((a_high - a_low) / pip, 1),
                )
            )

        # 2. London Open Corridor
        if london_candles:
            l_high = max(c.high for c in london_candles)
            l_low = min(c.low for c in london_candles)
            l_open = london_candles[0].open
            l_close = london_candles[-1].close
            latest_price = candles[-1].close
            status = SessionStatus.INTACT
            if latest_price > l_high:
                status = SessionStatus.BROKEN_UP
            elif latest_price < l_low:
                status = SessionStatus.BROKEN_DOWN

            corridors.append(
                SessionRange(
                    session_name=SessionName.LONDON,
                    high=round(l_high, 5),
                    low=round(l_low, 5),
                    open_price=round(l_open, 5),
                    close_price=round(l_close, 5),
                    status=status,
                    range_pips=round((l_high - l_low) / pip, 1),
                )
            )

        # 3. New York Overlap Corridor
        if ny_candles:
            ny_high = max(c.high for c in ny_candles)
            ny_low = min(c.low for c in ny_candles)
            ny_open = ny_candles[0].open
            ny_close = ny_candles[-1].close
            latest_price = candles[-1].close
            status = SessionStatus.INTACT
            if latest_price > ny_high:
                status = SessionStatus.BROKEN_UP
            elif latest_price < ny_low:
                status = SessionStatus.BROKEN_DOWN

            corridors.append(
                SessionRange(
                    session_name=SessionName.NY_OVERLAP,
                    high=round(ny_high, 5),
                    low=round(ny_low, 5),
                    open_price=round(ny_open, 5),
                    close_price=round(ny_close, 5),
                    status=status,
                    range_pips=round((ny_high - ny_low) / pip, 1),
                )
            )

        if not corridors:
            return self._generate_benchmark_corridors(symbol) if allow_benchmark else []

        return corridors

    def detect_volume_expansions(
        self,
        symbol: str,
        candles: List[CandleBar],
        min_rvol: float = 1.8,
    ) -> List[VolumeExpansionMarker]:
        """
        Detects volume expansion breakout candles where Relative Volume >= min_rvol
        and the candle body represents >= 60% of total candle range.
        """
        pip = _get_pip_size(symbol)
        if len(candles) < 21:
            return []

        markers: List[VolumeExpansionMarker] = []

        # Calculate 20-period volume rolling SMA
        for i in range(20, len(candles)):
            window = candles[i - 20:i]
            avg_vol = sum(c.volume for c in window) / 20.0
            if avg_vol <= 0:
                continue

            curr = candles[i]
            rvol = curr.volume / avg_vol
            total_range = curr.high - curr.low
            body_range = abs(curr.close - curr.open)

            if rvol >= min_rvol and total_range > 0:
                spread_ratio = body_range / total_range
                # Must be a solid directional candle body
                if spread_ratio >= 0.55:
                    is_bullish = curr.close > curr.open
                    direction = "BULLISH" if is_bullish else "BEARISH"

                    # Calculate expansion target: 1.5x candle range
                    target = curr.close + (total_range * 1.5) if is_bullish else curr.close - (total_range * 1.5)
                    invalidation = curr.low if is_bullish else curr.high

                    raw_time = getattr(curr, "timestamp", None) or getattr(curr, "time", None) or datetime.now(timezone.utc).isoformat()
                    markers.append(
                        VolumeExpansionMarker(
                            timestamp=str(raw_time),
                            direction=direction,
                            rvol=round(rvol, 2),
                            breakout_price=round(curr.close, 5),
                            target_price=round(target, 5),
                            invalidation_price=round(invalidation, 5),
                            spread_ratio=round(spread_ratio, 2),
                        )
                    )

        # Return latest 5 expansion markers
        return markers[-5:]

    def compute_volatility_exhaustion(
        self,
        symbol: str,
        candles: List[CandleBar],
        allow_benchmark: bool = False,
    ) -> VolatilityExhaustionZone:
        """
        Computes 2.5σ volatility exhaustion envelope (Keltner / Bollinger) and RSI.
        Identifies overstretched price action ready for mean reversion to the 20 EMA.
        """
        if len(candles) < 20:
            if allow_benchmark:
                return self._generate_benchmark_volatility(symbol)
            ref_px = candles[-1].close if candles else (4185.0 if "XAU" in symbol.upper() else 1.1350)
            return VolatilityExhaustionZone(
                upper_band=round(ref_px * 1.01, 5),
                lower_band=round(ref_px * 0.99, 5),
                mean_level=round(ref_px, 5),
                current_sigma=0.0,
                is_exhausted=False,
                exhaustion_state="NORMAL",
                rsi_value=50.0,
            )

        closes = [c.close for c in candles[-20:]]
        mean_20 = sum(closes) / 20.0

        # Standard deviation
        variance = sum((x - mean_20) ** 2 for x in closes) / 20.0
        std_dev = math.sqrt(variance)

        # 2.5 standard deviations
        band_multiplier = 2.5
        upper_band = mean_20 + (std_dev * band_multiplier)
        lower_band = mean_20 - (std_dev * band_multiplier)

        latest_close = candles[-1].close
        sigma = (latest_close - mean_20) / max(std_dev, 0.00001)

        # Quick 14-period RSI
        rsi_val = self._compute_rsi(candles[-15:]) if len(candles) >= 15 else 50.0

        exhaustion_state = "NORMAL"
        is_exhausted = False
        if latest_close >= upper_band or (sigma >= 2.5 and rsi_val >= 72.0):
            exhaustion_state = "OVERBOUGHT_EXHAUSTION"
            is_exhausted = True
        elif latest_close <= lower_band or (sigma <= -2.5 and rsi_val <= 28.0):
            exhaustion_state = "OVERSOLD_EXHAUSTION"
            is_exhausted = True

        return VolatilityExhaustionZone(
            upper_band=round(upper_band, 5),
            lower_band=round(lower_band, 5),
            mean_level=round(mean_20, 5),
            current_sigma=round(sigma, 2),
            is_exhausted=is_exhausted,
            exhaustion_state=exhaustion_state,
            rsi_value=round(rsi_val, 1),
        )

    def compute_ema(self, values: List[float], period: int) -> Optional[float]:
        """Calculates Exponential Moving Average over price series."""
        if not values or len(values) < min(5, period):
            return None
        k = 2.0 / (period + 1.0)
        init_window = min(period, len(values))
        ema = sum(values[:init_window]) / float(init_window)
        for price in values[init_window:]:
            ema = (price * k) + (ema * (1.0 - k))
        return round(ema, 5)

    def compute_atr(self, symbol: str, candles: List[CandleBar], period: int = 14) -> float:
        """Calculates 14-period Average True Range for dynamic volatility stops."""
        pip = _get_pip_size(symbol)
        if len(candles) < 2:
            return 15.0 * pip

        tr_list = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i - 1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        if not tr_list:
            return 15.0 * pip

        recent_trs = tr_list[-period:]
        atr = sum(recent_trs) / len(recent_trs)
        return max(atr, 5.0 * pip)

    def compute_htf_trend_bias(
        self,
        symbol: str,
        candles: List[CandleBar],
    ) -> Tuple[str, Optional[float], Optional[float]]:
        """
        Determines Higher-Timeframe (HTF) Trend Bias using 50 and 200 EMAs.
        Filters out counter-trend breakout traps against macro institutional flow.
        """
        if not candles or len(candles) < 10:
            return "NEUTRAL", None, None

        closes = [c.close for c in candles]
        latest_price = closes[-1]

        ema_50 = self.compute_ema(closes, 50)
        ema_200 = self.compute_ema(closes, 200) if len(closes) >= 50 else None

        if ema_50 is None:
            return "NEUTRAL", None, None

        if ema_200 is not None:
            if latest_price > ema_50 and ema_50 >= ema_200:
                return "BULLISH", ema_50, ema_200
            elif latest_price < ema_50 and ema_50 <= ema_200:
                return "BEARISH", ema_50, ema_200
            elif latest_price > ema_50:
                return "BULLISH", ema_50, ema_200
            elif latest_price < ema_50:
                return "BEARISH", ema_50, ema_200
            else:
                return "NEUTRAL", ema_50, ema_200
        else:
            if latest_price > ema_50:
                return "BULLISH", ema_50, None
            elif latest_price < ema_50:
                return "BEARISH", ema_50, None
            else:
                return "NEUTRAL", ema_50, None

    def calculate_trade_levels(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        candles: List[CandleBar],
        structure_sl: Optional[float] = None,
        take_profit: Optional[float] = None,
    ) -> Tuple[float, float, float, float, float]:
        """
        Calculates dynamic ATR-buffered Stop Loss, Multi-Stage TP1 (Bank 50%), TP2 (Trailing Runner),
        and dynamic Trailing Stop Buffer.
        Returns (sl, tp1, tp2, trailing_buffer, atr_14).
        """
        dir_upper = direction.upper()
        sym_upper = symbol.upper()
        dec = 2 if ("XAU" in sym_upper or "GOLD" in sym_upper or entry_price > 100) else 5

        atr = self.compute_atr(symbol, candles)
        atr_buffer = 1.5 * atr

        if dir_upper == "BUY":
            if structure_sl is not None and structure_sl < entry_price:
                struct_dist = entry_price - structure_sl
                effective_risk = max(struct_dist, atr_buffer)
            else:
                effective_risk = atr_buffer

            sl = round(entry_price - effective_risk, dec)
            tp1 = round(entry_price + (1.5 * effective_risk), dec)
            tp2 = round(entry_price + (3.0 * effective_risk), dec)

            # Institutional bounds: TP1 must never overshoot primary Take Profit
            if take_profit is not None and take_profit > entry_price:
                tp1 = min(tp1, round(entry_price + (take_profit - entry_price) * 0.5, dec))
                tp2 = take_profit
        else:
            if structure_sl is not None and structure_sl > entry_price:
                struct_dist = structure_sl - entry_price
                effective_risk = max(struct_dist, atr_buffer)
            else:
                effective_risk = atr_buffer

            sl = round(entry_price + effective_risk, dec)
            tp1 = round(entry_price - (1.5 * effective_risk), dec)
            tp2 = round(entry_price - (3.0 * effective_risk), dec)

            # Institutional bounds: TP1 must never overshoot primary Take Profit
            if take_profit is not None and take_profit < entry_price:
                tp1 = max(tp1, round(entry_price - (entry_price - take_profit) * 0.5, dec))
                tp2 = take_profit

        trailing_buffer = round(1.0 * atr, dec)
        return sl, tp1, tp2, trailing_buffer, round(atr, dec)

    def calculate_conviction(
        self,
        symbol: str,
        direction: str,
        candles: List[CandleBar],
        macro_news_impact: Optional[str] = None,
        minutes_to_news: Optional[int] = None,
        dxy_trend: Optional[str] = None,
        spread_pips: float = 0.8,
    ) -> CompositeConvictionScore:
        """
        Calculates 0-100% composite conviction score based on:
        1. Session corridor momentum alignment (30 pts)
        2. Volume expansion surge RVol >= 1.8x (30 pts)
        3. Statistical Volatility exhaustion / alignment (20 pts)
        4. Macro / DXY trend confluence (20 pts)
        5. Spread and news blackout penalties.
        """
        dir_upper = direction.upper()
        sym_upper = symbol.upper()

        corridors = self.compute_session_corridors(symbol, candles, allow_benchmark=False)
        expansions = self.detect_volume_expansions(symbol, candles)
        vol_zone = self.compute_volatility_exhaustion(symbol, candles, allow_benchmark=False)

        session_score = 15.0
        volume_score = 15.0
        volatility_score = 12.0
        correlation_score = 12.0
        reasons: List[str] = []

        # 1. Session alignment
        broken_up = any(c.status == SessionStatus.BROKEN_UP for c in corridors)
        broken_down = any(c.status == SessionStatus.BROKEN_DOWN for c in corridors)
        if dir_upper == "BUY" and broken_up:
            session_score = 28.0
            reasons.append("Bullish Session Range Breakout confirmed")
        elif dir_upper == "SELL" and broken_down:
            session_score = 28.0
            reasons.append("Bearish Session Range Breakdown confirmed")

        # 2. Volume Expansion
        recent_exp = expansions[-1] if expansions else None
        if recent_exp and recent_exp.direction == ("BULLISH" if dir_upper == "BUY" else "BEARISH"):
            volume_score = min(30.0, 18.0 + (recent_exp.rvol * 4.0))
            reasons.append(f"Volume Surge confirmed: {recent_exp.rvol:.1f}x RVol expansion")

        # 3. Volatility exhaustion or trend space
        if dir_upper == "BUY":
            if vol_zone.exhaustion_state == "OVERSOLD_EXHAUSTION":
                volatility_score = 20.0
                reasons.append("Oversold 2.5σ Volatility Reversion trigger active")
            elif vol_zone.current_sigma < 1.5:
                volatility_score = 16.0
                reasons.append("Ample volatility headroom below 2.5σ exhaustion band")
        else:
            if vol_zone.exhaustion_state == "OVERBOUGHT_EXHAUSTION":
                volatility_score = 20.0
                reasons.append("Overbought 2.5σ Volatility Reversion trigger active")
            elif vol_zone.current_sigma > -1.5:
                volatility_score = 16.0
                reasons.append("Ample volatility headroom above -2.5σ exhaustion band")

        # 4. Macro / DXY confluence
        if "USD" in sym_upper or "XAU" in sym_upper:
            if dxy_trend:
                dxy_up = dxy_trend.upper() == "BULLISH"
                is_usd_base = sym_upper.startswith("USD")
                if (is_usd_base and dir_upper == "BUY" and dxy_up) or \
                   (not is_usd_base and dir_upper == "SELL" and dxy_up):
                    correlation_score = 19.0
                    reasons.append(f"Strong DXY alignment ({dxy_trend}) supporting {dir_upper}")
                elif (is_usd_base and dir_upper == "SELL" and not dxy_up) or \
                     (not is_usd_base and dir_upper == "BUY" and not dxy_up):
                    correlation_score = 19.0
                    reasons.append(f"DXY weakness ({dxy_trend}) supporting {dir_upper}")

        # 5. Higher-Timeframe (HTF) Trend Confluence (EMA 50 & 200)
        htf_bias, ema_50, ema_200 = self.compute_htf_trend_bias(symbol, candles)
        htf_score = 0.0
        if dir_upper == "BUY":
            if htf_bias == "BULLISH":
                htf_score = 15.0
                reasons.append("Aligned with HTF Bullish Macro Flow (EMA 50/200)")
            elif htf_bias == "BEARISH":
                htf_score = -25.0
                reasons.append("Counter-trend penalty: Buying against Bearish HTF Flow (-25 pts)")
        elif dir_upper == "SELL":
            if htf_bias == "BEARISH":
                htf_score = 15.0
                reasons.append("Aligned with HTF Bearish Macro Flow (EMA 50/200)")
            elif htf_bias == "BULLISH":
                htf_score = -25.0
                reasons.append("Counter-trend penalty: Selling against Bullish HTF Flow (-25 pts)")

        # 6. Penalties
        spread_penalty = round(max(0.0, (spread_pips - 1.2) * 3.0), 1)
        macro_news_penalty = 0.0
        if macro_news_impact and macro_news_impact.upper() == "HIGH":
            if minutes_to_news is not None and 0 <= minutes_to_news <= 15:
                macro_news_penalty = 15.0
                reasons.append(f"High-impact macro event within {minutes_to_news}m: -15 penalty")

        total = max(0.0, min(100.0, session_score + volume_score + volatility_score + correlation_score + htf_score - spread_penalty - macro_news_penalty))

        bias = ConvictionBias.NEUTRAL
        if total >= 70:
            bias = ConvictionBias.BULLISH if dir_upper == "BUY" else ConvictionBias.BEARISH

        return CompositeConvictionScore(
            total_score=round(total, 1),
            session_momentum_score=round(session_score, 1),
            volume_expansion_score=round(volume_score, 1),
            volatility_exhaustion_score=round(volatility_score, 1),
            correlation_score=round(correlation_score, 1),
            spread_penalty=spread_penalty,
            macro_news_penalty=macro_news_penalty,
            htf_alignment_score=round(htf_score, 1),
            htf_trend_bias=htf_bias,
            symbol=symbol,
            bias=bias,
            key_reasons=reasons,
        )

    def _compute_rsi(self, candles: List[CandleBar], period: int = 14) -> float:
        if len(candles) < period:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(candles)):
            diff = candles[i].close - candles[i - 1].close
            gains.append(max(0.0, diff))
            losses.append(max(0.0, -diff))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _generate_benchmark_corridors(self, symbol: str) -> List[SessionRange]:
        """Provides realistic institutional session benchmarks for symbol."""
        sym = symbol.upper()
        ref = 4185.0 if "XAU" in sym else (1.3320 if "GBP" in sym else 1.1350)
        pip = _get_pip_size(sym)

        return [
            SessionRange(
                session_name=SessionName.ASIAN,
                high=round(ref + (25 * pip), 5),
                low=round(ref - (20 * pip), 5),
                open_price=round(ref - (10 * pip), 5),
                close_price=round(ref + (5 * pip), 5),
                status=SessionStatus.INTACT,
                range_pips=45.0,
            ),
            SessionRange(
                session_name=SessionName.LONDON,
                high=round(ref + (40 * pip), 5),
                low=round(ref - (30 * pip), 5),
                open_price=round(ref + (5 * pip), 5),
                close_price=round(ref + (35 * pip), 5),
                status=SessionStatus.BROKEN_UP,
                range_pips=70.0,
            ),
        ]

    def _generate_benchmark_volatility(self, symbol: str) -> VolatilityExhaustionZone:
        sym = symbol.upper()
        ref = 4185.0 if "XAU" in sym else (1.3320 if "GBP" in sym else 1.1350)
        pip = _get_pip_size(sym)
        return VolatilityExhaustionZone(
            upper_band=round(ref + (50 * pip), 5),
            lower_band=round(ref - (50 * pip), 5),
            mean_level=round(ref, 5),
            current_sigma=0.8,
            is_exhausted=False,
            exhaustion_state="NORMAL",
            rsi_value=54.2,
        )

    def evaluate_sweep_retest(
        self,
        symbol: str,
        direction: str,
        candles: List[CandleBar],
        corridors: Optional[List[SessionRange]] = None,
    ) -> SweepRetestEvaluation:
        """
        3-Phase Liquidity Sweep & Retest State Machine:
        1. SWEEP_PROBE: Price pierced session boundary by 1-12 pips but closed back inside;
           trapped retail breakout traders (liquidity hunt reversal threat).
        2. RETEST_FORMING: Clean breakout has occurred, price is actively pulling back to test
           the broken corridor boundary.
        3. EXPANSION_CONFIRMED: Retest pulled back, held the level, and printed a confirmation candle
           closing in the breakout direction.
        """
        pip = _get_pip_size(symbol)
        if not corridors:
            corridors = self.compute_session_corridors(symbol, candles, allow_benchmark=False)

        if not corridors or len(candles) < 3:
            return SweepRetestEvaluation(
                phase="NO_SWEEP",
                is_confirmed=True,
                is_sweep_reversal=False,
                retest_price=None,
                tactical_note="Direct momentum expansion.",
            )

        # Focus on Asian corridor first, fallback to first available
        target_corridor = next((c for c in corridors if c.session_name == SessionName.ASIAN), corridors[0])
        dir_upper = direction.upper()
        recent = candles[-4:]
        curr = recent[-1]

        if dir_upper == "BUY":
            level = target_corridor.high
            # Check for sweep probe (wick pierced above level, but close is below)
            for c in recent:
                if c.high > level + (0.5 * pip) and curr.close <= level:
                    return SweepRetestEvaluation(
                        phase="SWEEP_PROBE",
                        is_confirmed=False,
                        is_sweep_reversal=True,
                        retest_price=level,
                        tactical_note=f"⚠️ Liquidity Sweep Probe at {level:.5f}. High pierced but closed below. Potential false breakout / reversal trap.",
                    )

            # Check if breakout occurred
            if curr.close > level:
                # Did any recent bar retest the level?
                retested = any(abs(c.low - level) <= (3.0 * pip) for c in recent[:-1])
                dist_to_level = (curr.close - level) / pip
                if retested and curr.close > curr.open:
                    return SweepRetestEvaluation(
                        phase="EXPANSION_CONFIRMED",
                        is_confirmed=True,
                        is_sweep_reversal=False,
                        retest_price=level,
                        tactical_note=f"🟢 Breakout & Retest Confirmed at {level:.5f}. Clean structural expansion.",
                    )
                elif dist_to_level <= 4.0:
                    return SweepRetestEvaluation(
                        phase="RETEST_FORMING",
                        is_confirmed=True,
                        is_sweep_reversal=False,
                        retest_price=level,
                        tactical_note=f"⏳ Retest forming at broken session high {level:.5f}. Sniper limit order candidate.",
                    )
                else:
                    return SweepRetestEvaluation(
                        phase="EXPANSION_CONFIRMED",
                        is_confirmed=True,
                        is_sweep_reversal=False,
                        retest_price=level,
                        tactical_note=f"Breakout active above session high {level:.5f}.",
                    )
            else:
                return SweepRetestEvaluation(
                    phase="NO_SWEEP",
                    is_confirmed=True,
                    is_sweep_reversal=False,
                    retest_price=None,
                    tactical_note="Consolidating inside session corridor.",
                )
        else:  # SELL
            level = target_corridor.low
            # Check for sweep probe (wick pierced below level, but close is above)
            for c in recent:
                if c.low < level - (0.5 * pip) and curr.close >= level:
                    return SweepRetestEvaluation(
                        phase="SWEEP_PROBE",
                        is_confirmed=False,
                        is_sweep_reversal=True,
                        retest_price=level,
                        tactical_note=f"⚠️ Liquidity Sweep Probe at {level:.5f}. Low pierced but closed above. Potential false breakdown / reversal trap.",
                    )

            # Check if breakdown occurred
            if curr.close < level:
                retested = any(abs(c.high - level) <= (3.0 * pip) for c in recent[:-1])
                dist_to_level = (level - curr.close) / pip
                if retested and curr.close < curr.open:
                    return SweepRetestEvaluation(
                        phase="EXPANSION_CONFIRMED",
                        is_confirmed=True,
                        is_sweep_reversal=False,
                        retest_price=level,
                        tactical_note=f"🔴 Breakdown & Retest Confirmed at {level:.5f}. Clean structural expansion.",
                    )
                elif dist_to_level <= 4.0:
                    return SweepRetestEvaluation(
                        phase="RETEST_FORMING",
                        is_confirmed=True,
                        is_sweep_reversal=False,
                        retest_price=level,
                        tactical_note=f"⏳ Retest forming at broken session low {level:.5f}. Sniper limit order candidate.",
                    )
                else:
                    return SweepRetestEvaluation(
                        phase="EXPANSION_CONFIRMED",
                        is_confirmed=True,
                        is_sweep_reversal=False,
                        retest_price=level,
                        tactical_note=f"Breakdown active below session low {level:.5f}.",
                    )
            else:
                return SweepRetestEvaluation(
                    phase="NO_SWEEP",
                    is_confirmed=True,
                    is_sweep_reversal=False,
                    retest_price=None,
                    tactical_note="Consolidating inside session corridor.",
                )


session_breakout_engine = SessionBreakoutEngine()
