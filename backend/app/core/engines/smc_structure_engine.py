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

from datetime import datetime
from typing import Any, List, Optional, Union

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

    def calculate_composite_conviction(
        self,
        smc_blocks: List[OrderBlock],
        fvgs: List[FairValueGap],
        sweeps: List[LiquiditySweep],
        pattern_direction: str,
        session: str,
        spread_pips: float,
        dxy_trend: Optional[str] = None,
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
        5. Spread Penalty (0-25 pts deduction):
           - Tight spread <= 1.2 pips: 0 deduction
           - Wider spreads scale penalty progressively
        
        Args:
            smc_blocks: List of detected OrderBlock objects.
            fvgs: List of detected FairValueGap objects.
            sweeps: List of detected LiquiditySweep objects.
            pattern_direction: 'BUY', 'SELL', 'BULLISH', 'BEARISH', or 'NEUTRAL'.
            session: Current session name (e.g. 'LONDON_OPEN', 'NEW_YORK', 'ASIAN').
            spread_pips: Current live spread in pips.
            dxy_trend: Optional trend of US Dollar Index ('BULLISH', 'BEARISH', 'NEUTRAL').
            
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
        correlation_score = 10.0  # default baseline
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

        # 7. Total Conviction Score & Directional Bias
        raw_total = smc_score + sniper_score + session_score + correlation_score - spread_penalty
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
            bias=bias,
            key_reasons=key_reasons,
        )


# Global singleton instance for easy import and reuse
smc_structure_engine = SMCStructureEngine()
