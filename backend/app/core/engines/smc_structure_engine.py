"""
Falcon Pillar 1 — SMC Institutional Perception Engine.

Implements deterministic algorithms for Smart Money Concepts (SMC) & Institutional Perception:
1. Bullish and Bearish Order Blocks (last opposing candle before aggressive displacement breaking structure)
   with mitigation tracking.
2. 3-bar Fair Value Gaps (FVGs / Imbalances) with mitigation tracking.
3. Session Liquidity Sweeps across Asian, London, and New York ranges (manipulation wicks sweeping extremes and closing inside).
4. Composite Conviction Score (0-100%) synthesizing SMC alignment, sniper patterns, session timing,
   DXY/macro correlation, and live spreads.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.schemas.smc_structure import (
    CompositeConvictionScore,
    ConvictionBias,
    FairValueGap,
    FairValueGapType,
    LiquiditySweep,
    OrderBlock,
    OrderBlockType,
    SessionLevels,
    SweepType,
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


class SMCStructureEngine:
    """
    Deterministic Smart Money Concepts (SMC) Structure Engine.
    
    Provides institutional perception across order blocks, fair value gaps,
    session liquidity sweeps, and composite conviction scoring.
    """

    def detect_order_blocks(
        self,
        candles: List[CandleBar],
        symbol: str,
        timeframe: str,
        swing_window: int = 1,
    ) -> List[OrderBlock]:
        """
        Identifies Bullish and Bearish Order Blocks and tracks mitigation state.
        
        Definition:
        - Bullish Order Block: The last opposing (bearish: close < open) candle
          prior to an upward displacement move that breaks a prior swing high.
          Mitigation: Subsequent price action re-enters the block (low <= block.high).
        - Bearish Order Block: The last opposing (bullish: close > open) candle
          prior to a downward displacement move that breaks a prior swing low.
          Mitigation: Subsequent price action re-enters the block (high >= block.low).
        
        Args:
            candles: List of sequential CandleBar objects.
            symbol: Financial instrument identifier (e.g. 'EURUSD', 'XAUUSD').
            timeframe: Chart timeframe (e.g. '5m', '15m', '1h').
            swing_window: Window size on each side to qualify a swing point. Default 1.
            
        Returns:
            List of detected OrderBlock instances.
        """
        order_blocks: List[OrderBlock] = []
        n = len(candles)
        if n < 3:
            return order_blocks

        # Keep track of identified block keys to prevent duplicates
        seen_blocks = set()

        for j in range(2, n):
            # 1. Check for Bullish Displacement breaking a prior swing high
            # A swing high occurred at k where k < j
            for k in range(max(0, j - 20), j - 1):
                # Check if k was a swing high
                is_swing_high = True
                if k > 0 and candles[k].high <= candles[k - 1].high:
                    is_swing_high = False
                if k < j - 1 and candles[k].high < candles[k + 1].high:
                    is_swing_high = False

                if not is_swing_high:
                    continue

                # Does candle j (or displacement ending at j) break swing high k?
                # Displacement criteria: candle j closes above swing high k
                if candles[j].close > candles[k].high and candles[j].is_bullish:
                    # Find the last opposing (bearish: close < open) candle before the displacement
                    ob_idx = None
                    for b in range(j - 1, max(-1, k - 1), -1):
                        if candles[b].is_bearish:
                            ob_idx = b
                            break

                    if ob_idx is not None:
                        ob_candle = candles[ob_idx]
                        block_key = (OrderBlockType.BULLISH, ob_idx, ob_candle.high, ob_candle.low)
                        if block_key not in seen_blocks:
                            seen_blocks.add(block_key)

                            # Check mitigation in subsequent candles after the break (index > j)
                            is_mitigated = False
                            for m in range(j + 1, n):
                                if candles[m].low <= ob_candle.high:
                                    is_mitigated = True
                                    break

                            order_blocks.append(
                                OrderBlock(
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    block_type=OrderBlockType.BULLISH,
                                    high=ob_candle.high,
                                    low=ob_candle.low,
                                    open_price=ob_candle.open,
                                    close_price=ob_candle.close,
                                    volume=ob_candle.volume,
                                    is_mitigated=is_mitigated,
                                    formed_at=ob_candle.timestamp,
                                )
                            )

            # 2. Check for Bearish Displacement breaking a prior swing low
            for k in range(max(0, j - 20), j - 1):
                is_swing_low = True
                if k > 0 and candles[k].low >= candles[k - 1].low:
                    is_swing_low = False
                if k < j - 1 and candles[k].low > candles[k + 1].low:
                    is_swing_low = False

                if not is_swing_low:
                    continue

                # Does candle j close below swing low k?
                if candles[j].close < candles[k].low and candles[j].is_bearish:
                    # Find the last opposing (bullish: close > open) candle before the displacement
                    ob_idx = None
                    for b in range(j - 1, max(-1, k - 1), -1):
                        if candles[b].is_bullish:
                            ob_idx = b
                            break

                    if ob_idx is not None:
                        ob_candle = candles[ob_idx]
                        block_key = (OrderBlockType.BEARISH, ob_idx, ob_candle.high, ob_candle.low)
                        if block_key not in seen_blocks:
                            seen_blocks.add(block_key)

                            # Check mitigation in subsequent candles after the break (index > j)
                            is_mitigated = False
                            for m in range(j + 1, n):
                                if candles[m].high >= ob_candle.low:
                                    is_mitigated = True
                                    break

                            order_blocks.append(
                                OrderBlock(
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    block_type=OrderBlockType.BEARISH,
                                    high=ob_candle.high,
                                    low=ob_candle.low,
                                    open_price=ob_candle.open,
                                    close_price=ob_candle.close,
                                    volume=ob_candle.volume,
                                    is_mitigated=is_mitigated,
                                    formed_at=ob_candle.timestamp,
                                )
                            )

        return order_blocks

    def detect_fair_value_gaps(
        self,
        candles: List[CandleBar],
        symbol: str,
        timeframe: str,
        pip_size: Optional[float] = None,
    ) -> List[FairValueGap]:
        """
        Identifies 3-bar Fair Value Gaps (FVGs) and tracks subsequent mitigation.
        
        Definition:
        - Bullish FVG: Bar 1 High < Bar 3 Low.
          Imbalance zone: [Bar 1 High, Bar 3 Low].
          Mitigation: Any subsequent candle retraces into the gap (low <= Bar 3 Low).
        - Bearish FVG: Bar 1 Low > Bar 3 High.
          Imbalance zone: [Bar 3 High, Bar 1 Low].
          Mitigation: Any subsequent candle retraces into the gap (high >= Bar 3 High).
        
        Args:
            candles: Sequential list of CandleBar objects.
            symbol: Instrument identifier.
            timeframe: Timeframe string.
            pip_size: Optional pip size; if omitted, automatically resolved.
            
        Returns:
            List of detected FairValueGap instances.
        """
        fvgs: List[FairValueGap] = []
        n = len(candles)
        if n < 3:
            return fvgs

        actual_pip_size = pip_size if pip_size is not None and pip_size > 0 else _get_pip_size(symbol)

        for i in range(2, n):
            bar1 = candles[i - 2]
            bar2 = candles[i - 1]
            bar3 = candles[i]

            # Bullish FVG: Bar 1 High < Bar 3 Low
            if bar1.high < bar3.low:
                top = bar3.low
                bottom = bar1.high
                size_pips = round((top - bottom) / actual_pip_size, 2)

                # Check mitigation in candles following bar 3
                is_mitigated = False
                for m in range(i + 1, n):
                    if candles[m].low <= top:
                        is_mitigated = True
                        break

                fvgs.append(
                    FairValueGap(
                        symbol=symbol,
                        timeframe=timeframe,
                        gap_type=FairValueGapType.BULLISH,
                        top=top,
                        bottom=bottom,
                        size_pips=size_pips,
                        is_mitigated=is_mitigated,
                        bar1_time=bar1.timestamp,
                        bar3_time=bar3.timestamp,
                    )
                )

            # Bearish FVG: Bar 1 Low > Bar 3 High
            elif bar1.low > bar3.high:
                top = bar1.low
                bottom = bar3.high
                size_pips = round((top - bottom) / actual_pip_size, 2)

                # Check mitigation in candles following bar 3
                is_mitigated = False
                for m in range(i + 1, n):
                    if candles[m].high >= bottom:
                        is_mitigated = True
                        break

                fvgs.append(
                    FairValueGap(
                        symbol=symbol,
                        timeframe=timeframe,
                        gap_type=FairValueGapType.BEARISH,
                        top=top,
                        bottom=bottom,
                        size_pips=size_pips,
                        is_mitigated=is_mitigated,
                        bar1_time=bar1.timestamp,
                        bar3_time=bar3.timestamp,
                    )
                )

        return fvgs

    def detect_session_liquidity_sweeps(
        self,
        candles: List[CandleBar],
        session_levels: SessionLevels,
        symbol: str,
    ) -> List[LiquiditySweep]:
        """
        Identifies manipulation wicks that pierce above/below session extremes
        and close back inside the session range.
        
        Definition:
        - High Sweep: Candle High > Session High, but Candle Close <= Session High
          and Candle Close >= Session Low.
        - Low Sweep: Candle Low < Session Low, but Candle Close >= Session Low
          and Candle Close <= Session High.
        
        Args:
            candles: Sequential list of CandleBar objects (e.g. London or NY session candles).
            session_levels: SessionLevels reference boundary (e.g. Asian session range).
            symbol: Instrument identifier.
            
        Returns:
            List of LiquiditySweep events detected.
        """
        sweeps: List[LiquiditySweep] = []
        if not candles or session_levels is None:
            return sweeps

        sess_high = session_levels.high
        sess_low = session_levels.low
        sess_name = session_levels.session_name

        for c in candles:
            # Check for High Sweep (Judas swing above Asian/London high)
            if c.high > sess_high and sess_low <= c.close <= sess_high:
                sweeps.append(
                    LiquiditySweep(
                        symbol=symbol,
                        session_name=sess_name,
                        sweep_type=SweepType.HIGH_SWEEP,
                        swept_level=sess_high,
                        sweep_wick_extreme=c.high,
                        candle_close_inside=True,
                        close_price=c.close,
                        timestamp=c.timestamp,
                    )
                )

            # Check for Low Sweep (Judas swing below Asian/London low)
            if c.low < sess_low and sess_low <= c.close <= sess_high:
                sweeps.append(
                    LiquiditySweep(
                        symbol=symbol,
                        session_name=sess_name,
                        sweep_type=SweepType.LOW_SWEEP,
                        swept_level=sess_low,
                        sweep_wick_extreme=c.low,
                        candle_close_inside=True,
                        close_price=c.close,
                        timestamp=c.timestamp,
                    )
                )

        return sweeps

    def compute_session_levels(
        self,
        candles: List[Any],
        session_name: Optional[str] = None,
    ) -> SessionLevels:
        """
        Extracts institutional Asian (00:00-07:00 UTC), London (07:00-12:00 UTC),
        and New York (12:00-20:00 UTC) session levels (high/low/open/close) from
        candle timestamps.
        
        Args:
            candles: List of PriceBar or CandleBar objects with timestamp/bar_time.
            session_name: Optional specific session to return as primary (e.g. 'ASIAN', 'LONDON', 'NEW_YORK').
            
        Returns:
            SessionLevels instance populated with Asian, London, and NY session bounds.
        """
        if not candles:
            return SessionLevels(session_name="NONE", high=0.0, low=0.0, open_price=0.0, close_price=0.0)

        def _get_ohlc_time(c):
            t = getattr(c, "bar_time", None) or getattr(c, "timestamp", None) or getattr(c, "time", None)
            if t is None and isinstance(c, dict):
                t = c.get("bar_time") or c.get("timestamp") or c.get("time")

            dt = None
            if isinstance(t, datetime):
                dt = t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc)
                dt = dt.astimezone(timezone.utc)
            elif isinstance(t, (int, float)):
                ts = t / 1000.0 if t > 1e11 else float(t)
                try:
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                except (ValueError, OSError):
                    dt = None
            elif isinstance(t, str):
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z"):
                    try:
                        parsed = datetime.strptime(t, fmt)
                        dt = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
                        dt = dt.astimezone(timezone.utc)
                        break
                    except ValueError:
                        continue
                if dt is None:
                    try:
                        parsed = datetime.fromisoformat(t)
                        dt = parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)
                        dt = dt.astimezone(timezone.utc)
                    except ValueError:
                        pass

            op = getattr(c, "open", None) if getattr(c, "open", None) is not None else getattr(c, "open_price", 0.0)
            hi = getattr(c, "high", None)
            hi_val = float(hi) if hi is not None else 0.0
            lo = getattr(c, "low", None)
            lo_val = float(lo) if lo is not None else 0.0
            cl = getattr(c, "close", None) if getattr(c, "close", None) is not None else getattr(c, "close_price", 0.0)
            if isinstance(c, dict):
                op = c.get("open", op)
                hi_dict = c.get("high")
                if hi_dict is not None:
                    hi_val = float(hi_dict)
                lo_dict = c.get("low")
                if lo_dict is not None:
                    lo_val = float(lo_dict)
                cl = c.get("close", cl)

            return dt, float(op if op is not None else 0.0), hi_val, lo_val, float(cl if cl is not None else 0.0)

        parsed_bars = []
        for c in candles:
            dt, op, hi, lo, cl = _get_ohlc_time(c)
            if dt is not None:
                parsed_bars.append((dt, op, hi, lo, cl))

        if not parsed_bars:
            first_c = candles[0]
            _, op, hi, lo, cl = _get_ohlc_time(first_c)
            all_hi = max(_get_ohlc_time(c)[2] for c in candles)
            all_lo = min(_get_ohlc_time(c)[3] for c in candles)
            return SessionLevels(
                session_name="ASIAN",
                high=all_hi,
                low=all_lo,
                open_price=op,
                close_price=_get_ohlc_time(candles[-1])[4],
            )

        parsed_bars.sort(key=lambda x: x[0])
        latest_date = parsed_bars[-1][0].date()

        asian_bars = [b for b in parsed_bars if b[0].date() == latest_date and 0 <= b[0].hour < 7]
        if not asian_bars:
            all_asian = [b for b in parsed_bars if 0 <= b[0].hour < 7]
            if all_asian:
                last_asian_date = all_asian[-1][0].date()
                asian_bars = [b for b in all_asian if b[0].date() == last_asian_date]

        london_bars = [b for b in parsed_bars if b[0].date() == latest_date and 7 <= b[0].hour < 12]
        if not london_bars:
            all_london = [b for b in parsed_bars if 7 <= b[0].hour < 12]
            if all_london:
                last_london_date = all_london[-1][0].date()
                london_bars = [b for b in all_london if b[0].date() == last_london_date]

        ny_bars = [b for b in parsed_bars if b[0].date() == latest_date and 12 <= b[0].hour < 20]
        if not ny_bars:
            all_ny = [b for b in parsed_bars if 12 <= b[0].hour < 20]
            if all_ny:
                last_ny_date = all_ny[-1][0].date()
                ny_bars = [b for b in all_ny if b[0].date() == last_ny_date]

        def _build_sub_level(name: str, bars):
            if not bars:
                return None
            hi = max(b[2] for b in bars)
            lo = min(b[3] for b in bars)
            op = bars[0][1]
            cl = bars[-1][4]
            st = bars[0][0]
            et = bars[-1][0]
            return SessionLevels(
                session_name=name,
                high=round(hi, 5),
                low=round(lo, 5),
                open_price=round(op, 5),
                close_price=round(cl, 5),
                start_time=st,
                end_time=et,
            )

        asian_level = _build_sub_level("ASIAN", asian_bars)
        london_level = _build_sub_level("LONDON", london_bars)
        ny_level = _build_sub_level("NEW_YORK", ny_bars)

        sessions_dict: Dict[str, Any] = {}
        if asian_level:
            sessions_dict["ASIAN"] = asian_level
        if london_level:
            sessions_dict["LONDON"] = london_level
        if ny_level:
            sessions_dict["NEW_YORK"] = ny_level

        primary = None
        if session_name:
            clean_name = session_name.strip().upper()
            if "LONDON" in clean_name and london_level:
                primary = london_level
            elif any(k in clean_name for k in ["NY", "NEW_YORK"]) and ny_level:
                primary = ny_level
            elif "ASIAN" in clean_name and asian_level:
                primary = asian_level

        if primary is None:
            primary = asian_level or london_level or ny_level

        if primary is None:
            all_hi = max(b[2] for b in parsed_bars)
            all_lo = min(b[3] for b in parsed_bars)
            all_op = parsed_bars[0][1]
            all_cl = parsed_bars[-1][4]
            primary = SessionLevels(
                session_name="ALL",
                high=round(all_hi, 5),
                low=round(all_lo, 5),
                open_price=round(all_op, 5),
                close_price=round(all_cl, 5),
                start_time=parsed_bars[0][0],
                end_time=parsed_bars[-1][0],
            )

        return SessionLevels(
            session_name=primary.session_name,
            high=primary.high,
            low=primary.low,
            open_price=primary.open_price,
            close_price=primary.close_price,
            start_time=primary.start_time,
            end_time=primary.end_time,
            asian_high=asian_level.high if asian_level else None,
            asian_low=asian_level.low if asian_level else None,
            london_high=london_level.high if london_level else None,
            london_low=london_level.low if london_level else None,
            ny_high=ny_level.high if ny_level else None,
            ny_low=ny_level.low if ny_level else None,
            sessions=sessions_dict,
        )

    def calculate_composite_conviction(
        self,
        smc_blocks: List[OrderBlock],
        fvgs: List[FairValueGap],
        sweeps: List[LiquiditySweep],
        pattern_direction: str,
        session: str,
        spread_pips: float,
        dxy_trend: Optional[str] = None,
        macro_news_impact: Optional[str] = None,
        minutes_to_news: Optional[int] = None,
        symbol: Optional[str] = None,
    ) -> CompositeConvictionScore:
        """
        Synthesizes a 0-100 Composite Conviction Score and directional bias.
        
        Components:
        1. SMC Alignment Score (0-35 pts):
           - Unmitigated Order Blocks aligned with direction (+15 pts)
           - Fair Value Gaps aligned with direction (+10 pts)
           - Liquidity sweeps in opposing direction providing manipulation fuel (+10 pts)
           - Contradicting structure penalties (-4 to -6 pts)
        2. Sniper Pattern Score (0-25 pts):
           - Active directional pattern trigger (+15 pts)
           - Confluence with liquidity sweep or unmitigated block (+5 to +10 pts)
        3. Session Timing Score (0-20 pts):
           - London Open / London Session (+20 pts)
           - New York Open / Overlap (+20 pts)
           - Asian Session (+10 pts)
           - Off-hours / Market close (+5 pts)
        4. Macro / DXY Correlation Score (0-20 pts):
           - DXY inversely confirming EUR/GBP/Gold (+20 pts)
           - Macro alignment or neutral (+10 pts)
           - Conflicting macro trend (0 pts)
           - Gold/DXY inverse correlation: Bullish DXY penalizes Long Gold by -10 pts or boosts Short Gold by +10 pts;
             Bearish DXY boosts Long Gold by +10 pts or penalizes Short Gold by -10 pts.
        5. Spread Penalty (0-25 pts deduction):
           - Tight spread <= 1.2 pips: 0 deduction
           - Wider spreads scale penalty progressively
        6. Macro News Blackout Penalty (0-15 pts deduction):
           - High-impact news within 15 min imposes -15 pts penalty.
        
        Args:
            smc_blocks: List of detected OrderBlock objects.
            fvgs: List of detected FairValueGap objects.
            sweeps: List of detected LiquiditySweep objects.
            pattern_direction: 'BUY', 'SELL', 'BULLISH', 'BEARISH', or 'NEUTRAL'.
            session: Current session name (e.g. 'LONDON_OPEN', 'NEW_YORK', 'ASIAN').
            spread_pips: Current live spread in pips.
            dxy_trend: Optional trend of US Dollar Index ('BULLISH', 'BEARISH', 'NEUTRAL').
            macro_news_impact: Optional macro news impact ('HIGH', 'MEDIUM', 'LOW').
            minutes_to_news: Optional minutes remaining to nearest economic news release.
            symbol: Optional instrument identifier (e.g. 'XAUUSD', 'EURUSD').
            
        Returns:
            CompositeConvictionScore instance.
        """
        key_reasons: List[str] = []

        # 1. Normalize pattern direction
        dir_clean = pattern_direction.strip().upper() if pattern_direction else "NEUTRAL"
        is_bullish = dir_clean in ["BUY", "BULLISH", "LONG"]
        is_bearish = dir_clean in ["SELL", "BEARISH", "SHORT"]

        # 2. SMC Alignment Score (0-35)
        smc_score = 0.0

        bullish_obs = [b for b in smc_blocks if b.block_type == OrderBlockType.BULLISH]
        bearish_obs = [b for b in smc_blocks if b.block_type == OrderBlockType.BEARISH]
        unmit_bull_obs = [b for b in bullish_obs if not b.is_mitigated]
        unmit_bear_obs = [b for b in bearish_obs if not b.is_mitigated]

        bullish_fvgs = [g for g in fvgs if g.gap_type == FairValueGapType.BULLISH]
        bearish_fvgs = [g for g in fvgs if g.gap_type == FairValueGapType.BEARISH]
        unmit_bull_fvgs = [g for g in bullish_fvgs if not g.is_mitigated]
        unmit_bear_fvgs = [g for g in bearish_fvgs if not g.is_mitigated]

        low_sweeps = [s for s in sweeps if s.sweep_type == SweepType.LOW_SWEEP]
        high_sweeps = [s for s in sweeps if s.sweep_type == SweepType.HIGH_SWEEP]

        if is_bullish:
            if unmit_bull_obs:
                smc_score += 15.0
                key_reasons.append(
                    f"Institutional Demand: {len(unmit_bull_obs)} unmitigated Bullish Order Block(s) present (+15 pts)"
                )
            elif bullish_obs:
                smc_score += 7.0
                key_reasons.append("Bullish Order Block mitigated but provides historical support (+7 pts)")

            if unmit_bull_fvgs:
                smc_score += 10.0
                key_reasons.append(
                    f"Imbalance Confluence: {len(unmit_bull_fvgs)} unmitigated Bullish FVG(s) supporting expansion (+10 pts)"
                )
            elif bullish_fvgs:
                smc_score += 5.0
                key_reasons.append("Bullish FVG retested/mitigated (+5 pts)")

            if low_sweeps:
                smc_score += 10.0
                key_reasons.append(
                    f"Liquidity Sweep Confluence: Sell-side liquidity swept ({low_sweeps[-1].session_name} low at {low_sweeps[-1].swept_level}) followed by rejection (+10 pts)"
                )

            # Contradicting structure penalty
            if unmit_bear_obs:
                smc_score -= 6.0
                key_reasons.append("Caution: Unmitigated Bearish Order Block overhead (-6 pts)")
            if unmit_bear_fvgs:
                smc_score -= 4.0
                key_reasons.append("Caution: Bearish FVG resistance zone overhead (-4 pts)")

        elif is_bearish:
            if unmit_bear_obs:
                smc_score += 15.0
                key_reasons.append(
                    f"Institutional Supply: {len(unmit_bear_obs)} unmitigated Bearish Order Block(s) present (+15 pts)"
                )
            elif bearish_obs:
                smc_score += 7.0
                key_reasons.append("Bearish Order Block mitigated but provides historical resistance (+7 pts)")

            if unmit_bear_fvgs:
                smc_score += 10.0
                key_reasons.append(
                    f"Imbalance Confluence: {len(unmit_bear_fvgs)} unmitigated Bearish FVG(s) supporting downward expansion (+10 pts)"
                )
            elif bearish_fvgs:
                smc_score += 5.0
                key_reasons.append("Bearish FVG retested/mitigated (+5 pts)")

            if high_sweeps:
                smc_score += 10.0
                key_reasons.append(
                    f"Liquidity Sweep Confluence: Buy-side liquidity swept ({high_sweeps[-1].session_name} high at {high_sweeps[-1].swept_level}) followed by rejection (+10 pts)"
                )

            # Contradicting structure penalty
            if unmit_bull_obs:
                smc_score -= 6.0
                key_reasons.append("Caution: Unmitigated Bullish Order Block support beneath (-6 pts)")
            if unmit_bull_fvgs:
                smc_score -= 4.0
                key_reasons.append("Caution: Bullish FVG demand zone beneath (-4 pts)")

        else:
            # Neutral direction: evaluate net clarity
            net_diff = (len(unmit_bull_obs) + len(unmit_bull_fvgs)) - (
                len(unmit_bear_obs) + len(unmit_bear_fvgs)
            )
            smc_score = min(15.0, abs(net_diff) * 5.0)
            key_reasons.append(f"Neutral market structure scan: net structural imbalance {net_diff}")

        smc_score = max(0.0, min(35.0, smc_score))

        # 3. Sniper Pattern Score (0-25)
        sniper_score = 0.0
        if is_bullish:
            sniper_score = 15.0
            if low_sweeps:
                sniper_score = 25.0
                key_reasons.append("Sniper Entry: Turtle Soup liquidity sweep pattern confirmed (+25 pts)")
            elif unmit_bull_obs or unmit_bull_fvgs:
                sniper_score = 20.0
                key_reasons.append("Sniper Entry: Direct OB/FVG institutional mitigation trigger (+20 pts)")
            else:
                key_reasons.append("Sniper Entry: Bullish breakout / price-action trigger (+15 pts)")
        elif is_bearish:
            sniper_score = 15.0
            if high_sweeps:
                sniper_score = 25.0
                key_reasons.append("Sniper Entry: Turtle Soup liquidity sweep pattern confirmed (+25 pts)")
            elif unmit_bear_obs or unmit_bear_fvgs:
                sniper_score = 20.0
                key_reasons.append("Sniper Entry: Direct OB/FVG institutional mitigation trigger (+20 pts)")
            else:
                key_reasons.append("Sniper Entry: Bearish breakdown / price-action trigger (+15 pts)")
        else:
            sniper_score = 0.0
            key_reasons.append("Sniper Entry: No active directional pattern trigger (0 pts)")

        sniper_score = max(0.0, min(25.0, sniper_score))

        # 4. Session Timing Score (0-20)
        sess_clean = session.strip().upper() if session else "OFF_HOURS"
        if any(s in sess_clean for s in ["LONDON", "LONDON_OPEN", "LONDON_SESSION"]):
            session_score = 20.0
            key_reasons.append(f"Prime Session Timing: London Killzone ({session}) (+20 pts)")
        elif any(s in sess_clean for s in ["NEW_YORK", "NY", "NY_OPEN", "OVERLAP"]):
            session_score = 20.0
            key_reasons.append(f"Prime Session Timing: New York / Overlap Killzone ({session}) (+20 pts)")
        elif any(s in sess_clean for s in ["ASIAN", "TOKYO", "ASIA"]):
            session_score = 10.0
            key_reasons.append(f"Session Timing: Asian Range Accumulation ({session}) (+10 pts)")
        else:
            session_score = 5.0
            key_reasons.append(f"Session Timing: Off-peak hours ({session}) (+5 pts)")

        # 5. Correlation Score (0-20)
        is_gold = False
        if symbol:
            sym_clean = symbol.strip().upper().replace("/", "").replace(" ", "")
            if sym_clean in ["XAUUSD", "GOLD"] or "XAU" in sym_clean or "GOLD" in sym_clean:
                is_gold = True

        correlation_score = 10.0  # default baseline
        if is_gold:
            if dxy_trend:
                dxy_clean = dxy_trend.strip().upper()
                if is_bullish:
                    if dxy_clean in ["BULLISH", "UP", "RISING", "STRONG"]:
                        correlation_score = 0.0
                        key_reasons.append(
                            "Gold/DXY Inverse Correlation: Bullish DXY penalizes Long Gold by -10 pts (0 pts)"
                        )
                    elif dxy_clean in ["BEARISH", "DOWN", "FALLING", "WEAK"]:
                        correlation_score = 20.0
                        key_reasons.append(
                            "Gold/DXY Inverse Correlation: Bearish DXY boosts Long Gold by +10 pts (+20 pts)"
                        )
                    else:
                        correlation_score = 10.0
                        key_reasons.append(f"Gold/DXY Correlation: DXY neutral/sideways ({dxy_trend}) (+10 pts)")
                elif is_bearish:
                    if dxy_clean in ["BULLISH", "UP", "RISING", "STRONG"]:
                        correlation_score = 20.0
                        key_reasons.append(
                            "Gold/DXY Inverse Correlation: Bullish DXY boosts Short Gold by +10 pts (+20 pts)"
                        )
                    elif dxy_clean in ["BEARISH", "DOWN", "FALLING", "WEAK"]:
                        correlation_score = 0.0
                        key_reasons.append(
                            "Gold/DXY Inverse Correlation: Bearish DXY penalizes Short Gold by -10 pts (0 pts)"
                        )
                    else:
                        correlation_score = 10.0
                        key_reasons.append(f"Gold/DXY Correlation: DXY neutral/sideways ({dxy_trend}) (+10 pts)")
                else:
                    correlation_score = 10.0
                    key_reasons.append(f"Gold/DXY Correlation: DXY trend {dxy_trend} (+10 pts)")
            else:
                correlation_score = 10.0
                key_reasons.append("Gold/DXY Correlation: DXY unassigned, neutral baseline (+10 pts)")
        else:
            if dxy_trend:
                dxy_clean = dxy_trend.strip().upper()
                if is_bullish:
                    if dxy_clean in ["BEARISH", "DOWN", "FALLING", "WEAK"]:
                        correlation_score = 20.0
                        key_reasons.append("Macro Correlation: Bearish DXY inversely reinforces EUR/Gold long (+20 pts)")
                    elif dxy_clean in ["BULLISH", "UP", "RISING", "STRONG"]:
                        correlation_score = 0.0
                        key_reasons.append("Macro Headwind: Bullish DXY opposes long position (0 pts)")
                    else:
                        correlation_score = 10.0
                        key_reasons.append(f"Macro Correlation: DXY neutral/sideways ({dxy_trend}) (+10 pts)")
                elif is_bearish:
                    if dxy_clean in ["BULLISH", "UP", "RISING", "STRONG"]:
                        correlation_score = 20.0
                        key_reasons.append("Macro Correlation: Bullish DXY reinforces EUR/Gold short (+20 pts)")
                    elif dxy_clean in ["BEARISH", "DOWN", "FALLING", "WEAK"]:
                        correlation_score = 0.0
                        key_reasons.append("Macro Headwind: Bearish DXY opposes short position (0 pts)")
                    else:
                        correlation_score = 10.0
                        key_reasons.append(f"Macro Correlation: DXY neutral/sideways ({dxy_trend}) (+10 pts)")
                else:
                    correlation_score = 10.0
                    key_reasons.append(f"Macro Correlation: DXY trend {dxy_trend} (+10 pts)")
            else:
                correlation_score = 10.0
                key_reasons.append("Macro Correlation: DXY unassigned, neutral baseline (+10 pts)")

        # 6. Live Spread Penalty (0-25 deduction)
        if spread_pips <= 1.2:
            spread_penalty = 0.0
            key_reasons.append(f"Execution Quality: Tight spread at {spread_pips:.1f} pips (0 penalty)")
        elif spread_pips <= 2.5:
            spread_penalty = round((spread_pips - 1.2) * 2.5, 1)
            key_reasons.append(f"Execution Quality: Moderate spread {spread_pips:.1f} pips (-{spread_penalty:.1f} pts)")
        elif spread_pips <= 4.0:
            spread_penalty = round(3.25 + (spread_pips - 2.5) * 4.5, 1)
            key_reasons.append(f"Execution Quality: Elevated spread {spread_pips:.1f} pips (-{spread_penalty:.1f} pts)")
        else:
            spread_penalty = round(min(25.0, 10.0 + (spread_pips - 4.0) * 5.0), 1)
            key_reasons.append(f"Execution Caution: Wide spread {spread_pips:.1f} pips (-{spread_penalty:.1f} pts)")

        # 7. Macro High-Impact News Blackout Penalty (0-15 deduction)
        macro_news_penalty = 0.0
        if macro_news_impact and macro_news_impact.strip().upper() == "HIGH":
            if minutes_to_news is not None and 0 <= minutes_to_news <= 15:
                macro_news_penalty = 15.0
                key_reasons.append(
                    f"Macro Event Risk: High-impact news in {minutes_to_news}m applies -15 pts news blackout penalty"
                )

        # 8. Total Conviction Score & Directional Bias
        raw_total = (
            smc_score
            + sniper_score
            + session_score
            + correlation_score
            - spread_penalty
            - macro_news_penalty
        )
        total_score = max(0.0, min(100.0, round(raw_total, 1)))

        if total_score >= 60.0:
            if is_bullish:
                bias = ConvictionBias.BULLISH
            elif is_bearish:
                bias = ConvictionBias.BEARISH
            else:
                bias = ConvictionBias.NEUTRAL
        elif 40.0 <= total_score < 60.0:
            if is_bullish and smc_score >= 12.0:
                bias = ConvictionBias.BULLISH
            elif is_bearish and smc_score >= 12.0:
                bias = ConvictionBias.BEARISH
            else:
                bias = ConvictionBias.NEUTRAL
        else:
            bias = ConvictionBias.NEUTRAL

        return CompositeConvictionScore(
            total_score=total_score,
            smc_alignment_score=round(smc_score, 1),
            sniper_pattern_score=round(sniper_score, 1),
            session_timing_score=round(session_score, 1),
            correlation_score=round(correlation_score, 1),
            spread_penalty=round(spread_penalty, 1),
            macro_news_penalty=round(macro_news_penalty, 1),
            symbol=symbol,
            bias=bias,
            key_reasons=key_reasons,
        )


# Global singleton instance for easy import and reuse
smc_structure_engine = SMCStructureEngine()
