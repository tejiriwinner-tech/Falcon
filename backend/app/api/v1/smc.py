"""
Falcon Pillar 1 — SMC Institutional Perception API Router.

Exposes read-only REST endpoints for Smart Money Concepts (SMC):
1. GET /api/v1/smc/structure — Order Blocks, Fair Value Gaps, and Session Levels
2. GET /api/v1/smc/sweeps — Session Liquidity Sweeps (Judas swings / manipulation wicks)
3. GET /api/v1/smc/conviction — Composite Conviction Score (0-100%) synthesizing structure,
   session timing, DXY/macro correlation, news blackout, and spreads.

Strictly preserves R4: Purely read-only GET endpoints, zero broker automation, no database mutations.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query

from app.core.engines.candlestick_pattern_engine import CandleBar
from app.core.engines.smc_structure_engine import smc_structure_engine
from app.core.services.market_history_service import market_history_service
from app.schemas.smc_structure import (
    CompositeConvictionScore,
    SMCStructureResponse,
    SMCSweepsResponse,
)

router = APIRouter(prefix="/smc", tags=["smc"])


@router.get("/structure", response_model=SMCStructureResponse)
def get_smc_structure(
    symbol: str = Query(default="EURUSD", description="Instrument identifier (e.g., EURUSD, GBPUSD, XAUUSD)"),
    timeframe: str = Query(default="15m", description="Timeframe (e.g., 5m, 15m, 1h)"),
    limit: int = Query(default=100, ge=10, le=500, description="Number of historical candles to analyze"),
) -> SMCStructureResponse:
    """
    Returns detected Order Blocks, Fair Value Gaps, and Session Levels for the instrument.
    Purely read-only query (R4).
    """
    try:
        bars = market_history_service.get_bars(symbol=symbol, timeframe=timeframe, limit=limit)
    except Exception:
        bars = []
    candles = [
        CandleBar(
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            timestamp=b.bar_time,
        )
        for b in bars
    ]

    order_blocks = smc_structure_engine.detect_order_blocks(
        candles=candles, symbol=symbol, timeframe=timeframe
    )
    fvgs = smc_structure_engine.detect_fair_value_gaps(
        candles=candles, symbol=symbol, timeframe=timeframe
    )
    session_levels = smc_structure_engine.compute_session_levels(bars) if bars else None

    unmit_obs = sum(1 for ob in order_blocks if not ob.is_mitigated)
    unmit_fvgs = sum(1 for fvg in fvgs if not fvg.is_mitigated)

    return SMCStructureResponse(
        symbol=symbol,
        timeframe=timeframe,
        order_blocks=order_blocks,
        fair_value_gaps=fvgs,
        session_levels=session_levels,
        total_order_blocks=len(order_blocks),
        total_fair_value_gaps=len(fvgs),
        unmitigated_order_blocks=unmit_obs,
        unmitigated_fair_value_gaps=unmit_fvgs,
    )


@router.get("/sweeps", response_model=SMCSweepsResponse)
def get_smc_sweeps(
    symbol: str = Query(default="EURUSD", description="Instrument identifier"),
    timeframe: str = Query(default="15m", description="Timeframe (e.g., 15m, 1h)"),
    limit: int = Query(default=100, ge=10, le=500, description="Number of historical candles to analyze"),
) -> SMCSweepsResponse:
    """
    Returns session liquidity sweeps (manipulation wicks that sweep session extremes and reverse).
    Purely read-only query (R4).
    """
    try:
        bars = market_history_service.get_bars(symbol=symbol, timeframe=timeframe, limit=limit)
    except Exception:
        bars = []
    session_levels = smc_structure_engine.compute_session_levels(bars) if bars else None

    candles = [
        CandleBar(
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            timestamp=b.bar_time,
        )
        for b in bars
    ]

    sweeps = (
        smc_structure_engine.detect_session_liquidity_sweeps(
            candles=candles, session_levels=session_levels, symbol=symbol
        )
        if session_levels and session_levels.high > 0.0
        else []
    )

    high_sweeps = sum(1 for s in sweeps if s.is_high_sweep)
    low_sweeps = sum(1 for s in sweeps if s.is_low_sweep)

    return SMCSweepsResponse(
        symbol=symbol,
        session_levels=session_levels,
        sweeps=sweeps,
        total_sweeps=len(sweeps),
        high_sweeps=high_sweeps,
        low_sweeps=low_sweeps,
    )


@router.get("/conviction", response_model=CompositeConvictionScore)
def get_composite_conviction(
    symbol: str = Query(default="EURUSD", description="Instrument identifier (e.g. EURUSD, XAUUSD)"),
    direction: str = Query(default="BUY", description="Directional pattern bias (BUY or SELL)"),
    timeframe: str = Query(default="15m", description="Timeframe"),
    session: Optional[str] = Query(default=None, description="Session override (e.g., LONDON_OPEN, NEW_YORK, ASIAN)"),
    spread_pips: Optional[float] = Query(default=1.0, description="Current live spread in pips"),
    dxy_trend: Optional[str] = Query(default=None, description="DXY trend (BULLISH, BEARISH, NEUTRAL)"),
    macro_news_impact: Optional[str] = Query(default=None, description="Macro news impact (HIGH, MEDIUM, LOW)"),
    minutes_to_news: Optional[int] = Query(default=None, ge=0, description="Minutes until high-impact release"),
) -> CompositeConvictionScore:
    """
    Synthesizes the 0-100% Composite Conviction Score across SMC structure, session timing,
    macro news blackout, DXY inverse correlation, and live spreads.
    Purely read-only query (R4).
    """
    if not session:
        utc_hour = datetime.now(timezone.utc).hour
        if 0 <= utc_hour < 7:
            session = "ASIAN"
        elif 7 <= utc_hour < 12:
            session = "LONDON_OPEN"
        elif 12 <= utc_hour < 20:
            session = "NEW_YORK"
        else:
            session = "OFF_HOURS"

    try:
        bars = market_history_service.get_bars(symbol=symbol, timeframe=timeframe, limit=100)
    except Exception:
        bars = []
    candles = [
        CandleBar(
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            timestamp=b.bar_time,
        )
        for b in bars
    ]

    obs = smc_structure_engine.detect_order_blocks(candles, symbol=symbol, timeframe=timeframe) if candles else []
    fvgs = smc_structure_engine.detect_fair_value_gaps(candles, symbol=symbol, timeframe=timeframe) if candles else []
    sess_levels = smc_structure_engine.compute_session_levels(bars) if bars else None
    sweeps = (
        smc_structure_engine.detect_session_liquidity_sweeps(candles, sess_levels, symbol=symbol)
        if sess_levels and sess_levels.high > 0.0
        else []
    )

    conviction = smc_structure_engine.calculate_composite_conviction(
        smc_blocks=obs,
        fvgs=fvgs,
        sweeps=sweeps,
        pattern_direction=direction,
        session=session,
        spread_pips=spread_pips if spread_pips is not None else 1.0,
        dxy_trend=dxy_trend,
        macro_news_impact=macro_news_impact,
        minutes_to_news=minutes_to_news,
        symbol=symbol,
    )

    return conviction
